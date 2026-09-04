"""Real Azure Policy validate-time go-live check for PRI-PRE-001.

No resource is ever actually created here: `validate` genuinely triggers
Azure Policy's real deny evaluation without provisioning anything. Uses a
direct REST call (no clean SDK method exists for validate-only checks,
matching PRI-004's precedent for the same reason).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
from azure.identity.aio import AzureCliCredential

from .evidence import blocked_result, record_evidence
from .models import GateAction, GateDecision, GoLiveAttemptResult, ProjectRecord
from .policy import evaluate_dpia_gate

DEPLOYMENTS_API_VERSION = "2022-09-01"
MANAGEMENT_SCOPE = "https://management.azure.com/.default"

_PLACEHOLDER_TEMPLATE = {
    "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
    "contentVersion": "1.0.0.0",
    "parameters": {
        "actionGroupName": {"type": "string"},
        "tags": {"type": "object"},
    },
    "resources": [
        {
            "type": "Microsoft.Insights/actionGroups",
            "apiVersion": "2023-01-01",
            "name": "[parameters('actionGroupName')]",
            "location": "Global",
            "tags": "[parameters('tags')]",
            "properties": {"groupShortName": "pripre001", "enabled": True},
        }
    ],
}


class GoLiveGateError(RuntimeError):
    """Raised when the go-live attempt cannot safely complete."""


def _tags_for(record: ProjectRecord, high_risk: bool) -> dict[str, str]:
    tags = {"aiSystemHighRisk": "true" if high_risk else "false", "dpiaStatus": record.dpia_status.value}
    if record.dpia_approver:
        tags["dpiaApprover"] = record.dpia_approver
    if record.dpia_date is not None:
        tags["dpiaDate"] = record.dpia_date.date().isoformat()
    if record.dpia_report_id:
        tags["dpiaReportId"] = record.dpia_report_id
    return tags


async def attempt_go_live(
    decision: GateDecision,
    current_record: ProjectRecord,
    subscription_id: str,
    resource_group: str,
) -> GoLiveAttemptResult:
    """Re-verify the deterministic decision, then ask Azure Policy for a real answer."""
    fresh_decision = evaluate_dpia_gate(current_record, datetime.now(UTC))
    if fresh_decision.etag != decision.etag:
        return blocked_result(decision, "The project record changed after evaluation; rescan first.")
    if fresh_decision.action is GateAction.BLOCKED_UNKNOWN:
        return blocked_result(
            fresh_decision, "Risk factors are unknown; the gate refuses to attempt go-live at all."
        )

    tags = _tags_for(current_record, high_risk=fresh_decision.dpia_required)
    deployment_name = f"pripre001-golive-{uuid.uuid4().hex[:8]}"
    url = (
        f"https://management.azure.com/subscriptions/{subscription_id}"
        f"/resourceGroups/{resource_group}/providers/Microsoft.Resources"
        f"/deployments/{deployment_name}/validate?api-version={DEPLOYMENTS_API_VERSION}"
    )
    body = {
        "properties": {
            "mode": "Incremental",
            "template": _PLACEHOLDER_TEMPLATE,
            "parameters": {
                "actionGroupName": {"value": f"pripre001demo{uuid.uuid4().hex[:8]}"},
                "tags": {"value": tags},
            },
        }
    }

    async with AzureCliCredential() as credential:
        token = await credential.get_token(MANAGEMENT_SCOPE)
        async with httpx.AsyncClient() as http_client:
            response = await http_client.post(
                url, json=body, headers={"Authorization": f"Bearer {token.token}"}
            )

    if response.status_code not in (200, 400):
        raise GoLiveGateError(f"Validate call failed unexpectedly ({response.status_code}).")

    response_text = response.text
    if response.status_code == 400 and "RequestDisallowedByPolicy" not in response_text:
        raise GoLiveGateError(f"Validate call failed unexpectedly: {response_text}")

    denied = response.status_code == 400
    evidence_id = record_evidence(fresh_decision, azure_policy_denied=denied)
    if denied:
        message = (
            "Azure Policy independently refused this go-live request "
            "(RequestDisallowedByPolicy) — the deterministic decision and the "
            "real platform enforcement agree."
        )
    else:
        message = "Azure Policy validated this go-live request without objection."

    return GoLiveAttemptResult(
        decision_id=fresh_decision.decision_id,
        project_id=fresh_decision.project_id,
        status=fresh_decision.action.value,
        azure_policy_denied=denied,
        evidence_id=evidence_id,
        message=message,
    )

