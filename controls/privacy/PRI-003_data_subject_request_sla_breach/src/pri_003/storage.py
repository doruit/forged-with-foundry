"""Azure Table Storage adapter for the isolated PRI-003 DSR register."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

from azure.core import MatchConditions
from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
from azure.data.tables import UpdateMode
from azure.data.tables.aio import TableServiceClient
from azure.identity.aio import DefaultAzureCredential

from .approval import ExtensionApprovalRegistry
from .evidence import blocked_result, record_evidence
from .models import (
    DSRAction,
    DSRDecision,
    DSRExtensionResult,
    DSRPolicy,
    DSRRecord,
    DSRStatus,
)
from .policy import evaluate_dsr, evaluate_extension_request, fail_closed

PARTITION_KEY = "pri003-demo"
POLICIES = {
    "access": DSRPolicy("access", sla_days=30, extension_days=60, extension_allowed=True),
    "rectification": DSRPolicy(
        "rectification", sla_days=30, extension_days=60, extension_allowed=True
    ),
    "erasure": DSRPolicy("erasure", sla_days=30, extension_days=0, extension_allowed=False),
}
WARNING_DAYS = int(os.getenv("PRI003_WARNING_DAYS", "7"))


class DSRControlError(RuntimeError):
    """Raised when PRI-003 cannot safely inspect or update its scope."""


def _entity_to_record(entity: dict) -> DSRRecord:
    request_type = entity.get("RequestType") or None
    if request_type is not None and request_type not in POLICIES:
        request_type = None  # unknown type; evaluate_dsr fails closed
    return DSRRecord(
        request_id=entity["RowKey"],
        request_type=request_type,
        received_date=entity["ReceivedDate"],
        status=DSRStatus(entity.get("Status", DSRStatus.OPEN.value)),
        etag=str(entity.metadata["etag"]),
        extension_granted=bool(entity.get("ExtensionGranted", False)),
    )


class DSRStore:
    def __init__(self, approvals: ExtensionApprovalRegistry | None = None) -> None:
        self.account_url = os.getenv("PRI003_TABLE_ENDPOINT", "").strip().rstrip("/")
        if not self.account_url:
            raise DSRControlError(
                "PRI-003 storage is not configured; deploy the control infrastructure."
            )
        self.table_name = os.getenv("PRI003_TABLE_NAME", "pri003dsrrequests").strip()
        self.approvals = approvals or ExtensionApprovalRegistry()

    def _client(self, credential: DefaultAzureCredential) -> TableServiceClient:
        return TableServiceClient(self.account_url, credential=credential)

    async def seed_scenarios(self) -> None:
        """Create five synthetic DSR records covering every decision outcome."""
        now = datetime.now(UTC)
        scenarios = [
            {
                "RowKey": "on-track-access",
                "RequestType": "access",
                "ReceivedDate": now - timedelta(days=5),
                "Status": DSRStatus.OPEN.value,
            },
            {
                "RowKey": "at-risk-rectification",
                "RequestType": "rectification",
                "ReceivedDate": now - timedelta(days=25),
                "Status": DSRStatus.IN_PROGRESS.value,
            },
            {
                "RowKey": "breached-erasure-open",
                "RequestType": "erasure",
                "ReceivedDate": now - timedelta(days=40),
                "Status": DSRStatus.OPEN.value,
            },
            {
                "RowKey": "breached-access-completed-late",
                "RequestType": "access",
                "ReceivedDate": now - timedelta(days=50),
                "Status": DSRStatus.COMPLETED.value,
            },
            {
                "RowKey": "blocked-unknown-type",
                "RequestType": "unknown",
                "ReceivedDate": now - timedelta(days=10),
                "Status": DSRStatus.OPEN.value,
            },
        ]
        async with DefaultAzureCredential() as credential:
            service = self._client(credential)
            table = service.get_table_client(self.table_name)
            try:
                await service.create_table_if_not_exists(self.table_name)
                async for entity in table.query_entities(
                    f"PartitionKey eq '{PARTITION_KEY}'"
                ):
                    await table.delete_entity(entity["PartitionKey"], entity["RowKey"])
                for scenario in scenarios:
                    await table.create_entity(
                        {
                            "PartitionKey": PARTITION_KEY,
                            "ExtensionGranted": False,
                            **scenario,
                        }
                    )
            except HttpResponseError as exc:
                raise DSRControlError("Seeding the PRI-003 demo register failed.") from exc
            finally:
                await service.close()

    async def scan(self, evaluated_at: datetime | None = None) -> list[DSRDecision]:
        """List entities and evaluate deterministic SLA outcomes."""
        evaluated_at = (evaluated_at or datetime.now(UTC)).astimezone(UTC)
        decisions: list[DSRDecision] = []
        async with DefaultAzureCredential() as credential:
            service = self._client(credential)
            table = service.get_table_client(self.table_name)
            try:
                async for entity in table.query_entities(
                    f"PartitionKey eq '{PARTITION_KEY}'"
                ):
                    try:
                        record = _entity_to_record(entity)
                    except (KeyError, ValueError):
                        decisions.append(
                            fail_closed(
                                entity.get("RowKey", "unknown-request"),
                                "Required DSR metadata is missing or invalid.",
                            )
                        )
                        continue
                    decisions.append(
                        evaluate_dsr(record, POLICIES, evaluated_at, WARNING_DAYS)
                    )
            except ResourceNotFoundError as exc:
                raise DSRControlError(
                    "PRI-003 table is missing; deploy infrastructure or seed the demo."
                ) from exc
            except HttpResponseError as exc:
                raise DSRControlError(
                    "DSR scan failed; no state change is allowed."
                ) from exc
            finally:
                await service.close()
        return decisions

    async def escalate(self, decision: DSRDecision) -> DSRExtensionResult:
        """Record a DPO escalation event; this never mutates the DSR record."""
        if decision.action not in (DSRAction.AT_RISK, DSRAction.BREACHED):
            raise DSRControlError("Only at-risk or breached decisions can be escalated.")
        evidence_id = record_evidence(decision, escalated=True, extension_granted=False)
        return DSRExtensionResult(
            decision_id=decision.decision_id,
            request_id=decision.request_id,
            status="escalated",
            extension_granted=False,
            evidence_id=evidence_id,
            message="Escalation recorded for the DPO. No DSR record was modified.",
        )

    def request_extension_approval(self, decision: DSRDecision) -> str:
        """Pre-check eligibility from the scanned decision before issuing a token."""
        policy = POLICIES.get(decision.request_type or "")
        if policy is None:
            raise DSRControlError(
                "DSR request type is missing or unknown; the extension is refused."
            )
        if decision.extension_granted:
            raise DSRControlError(
                "An extension was already granted; only one extension is permitted."
            )
        if not policy.extension_allowed:
            raise DSRControlError(f"{policy.request_type} requests do not permit an SLA extension.")
        if decision.action not in (DSRAction.AT_RISK, DSRAction.BREACHED):
            raise DSRControlError("Only at-risk or breached decisions require an extension.")
        return self.approvals.issue(decision).token

    async def grant_extension(
        self, decision: DSRDecision, approval_token: str
    ) -> DSRExtensionResult:
        """Apply an ETag-conditional extension grant after approval and re-validation."""
        self.approvals.consume(approval_token, decision)
        async with DefaultAzureCredential() as credential:
            service = self._client(credential)
            table = service.get_table_client(self.table_name)
            try:
                entity = await table.get_entity(PARTITION_KEY, decision.request_id)
                if str(entity.metadata["etag"]) != decision.etag:
                    return blocked_result(
                        decision,
                        "The DSR record changed after evaluation; extension was blocked. Rescan first.",
                    )
                record = _entity_to_record(entity)
                allowed, reason = evaluate_extension_request(record, POLICIES)
                if not allowed:
                    return blocked_result(decision, reason)

                entity["ExtensionGranted"] = True
                await table.update_entity(
                    entity,
                    mode=UpdateMode.MERGE,
                    etag=decision.etag,
                    match_condition=MatchConditions.IfNotModified,
                )
                evidence_id = record_evidence(decision, escalated=False, extension_granted=True)
                return DSRExtensionResult(
                    decision_id=decision.decision_id,
                    request_id=decision.request_id,
                    status="extended",
                    extension_granted=True,
                    evidence_id=evidence_id,
                    message="The SLA due date was extended and recorded.",
                )
            except ResourceNotFoundError:
                return blocked_result(decision, "The DSR record no longer exists.")
            except HttpResponseError as exc:
                raise DSRControlError(
                    "Guarded extension failed; the outcome is not claimed as granted."
                ) from exc
            finally:
                await service.close()

    async def cleanup(self) -> None:
        """Delete only synthetic PRI-003 demo entities."""
        async with DefaultAzureCredential() as credential:
            service = self._client(credential)
            table = service.get_table_client(self.table_name)
            try:
                async for entity in table.query_entities(
                    f"PartitionKey eq '{PARTITION_KEY}'"
                ):
                    await table.delete_entity(entity["PartitionKey"], entity["RowKey"])
            except ResourceNotFoundError:
                return
            finally:
                await service.close()
