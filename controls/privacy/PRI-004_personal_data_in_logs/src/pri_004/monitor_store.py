"""Azure Monitor Logs adapter: ingest, query, and guarded purge for PRI-004."""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta

import httpx
from azure.core.exceptions import HttpResponseError
from azure.identity.aio import AzureCliCredential
from azure.monitor.ingestion.aio import LogsIngestionClient
from azure.monitor.query import LogsQueryStatus
from azure.monitor.query.aio import LogsQueryClient

from .acs_gate import ApprovalTicket, get_control, resolver_for
from .evidence import blocked_result, record_evidence
from .models import LogDecision, LogRecord, LogRemediationResult
from .policy import (
    compute_message_hash,
    evaluate_field_policy_change,
    evaluate_log_entry,
    evaluate_purge_request,
)
from .text_pii import PiiDetectionError, scan_message

RECORD_PREFIX = "pri004-demo-"
# Demo-only sentinel; treated as a detector outage without calling the real Language API.
DETECTOR_UNAVAILABLE_MARKER = "[[pri004-simulated-detector-outage]]"
PURGE_API_VERSION = "2025-07-01"
MANAGEMENT_SCOPE = "https://management.azure.com/.default"


class LogControlError(RuntimeError):
    """Raised when PRI-004 cannot safely inspect or remediate its scope."""


class MonitorLogStore:
    def __init__(self) -> None:
        self.dcr_endpoint = os.getenv("PRI004_DCR_ENDPOINT", "").strip().rstrip("/")
        self.dcr_immutable_id = os.getenv("PRI004_DCR_IMMUTABLE_ID", "").strip()
        self.stream_name = os.getenv("PRI004_STREAM_NAME", "Custom-PRI004AppLogs").strip()
        self.workspace_customer_id = os.getenv("PRI004_WORKSPACE_CUSTOMER_ID", "").strip()
        self.workspace_name = os.getenv("PRI004_WORKSPACE_NAME", "").strip()
        self.table_name = os.getenv("PRI004_TABLE_NAME", "PRI004AppLogs_CL").strip()
        self.subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID", "").strip()
        self.resource_group = os.getenv("AZURE_RESOURCE_GROUP", "").strip()
        if not all(
            [
                self.dcr_endpoint,
                self.dcr_immutable_id,
                self.workspace_customer_id,
                self.workspace_name,
                self.subscription_id,
                self.resource_group,
            ]
        ):
            raise LogControlError(
                "PRI-004 storage is not configured; deploy the control infrastructure."
            )
        self._suppressed_fields: set[str] = set()

    def _redact_if_suppressed(self, field_name: str, message: str) -> str:
        return "[REDACTED-BY-POLICY]" if field_name in self._suppressed_fields else message

    async def seed_scenarios(self) -> None:
        """Ingest three synthetic log records covering every decision outcome."""
        now = datetime.now(UTC).isoformat()
        rows = [
            {
                "TimeGenerated": now,
                "RecordId": f"{RECORD_PREFIX}clean",
                "FieldName": "Message",
                "Message": self._redact_if_suppressed(
                    "Message", "background job completed successfully"
                ),
                "Source": "checkout-service",
            },
            {
                "TimeGenerated": now,
                "RecordId": f"{RECORD_PREFIX}pii-detected",
                "FieldName": "Message",
                "Message": self._redact_if_suppressed(
                    "Message", "order confirmation sent to jane.doe@example.com"
                ),
                "Source": "checkout-service",
            },
            {
                "TimeGenerated": now,
                "RecordId": f"{RECORD_PREFIX}blocked",
                "FieldName": "Message",
                "Message": DETECTOR_UNAVAILABLE_MARKER,
                "Source": "checkout-service",
            },
        ]
        try:
            async with AzureCliCredential() as credential:
                async with LogsIngestionClient(self.dcr_endpoint, credential=credential) as client:
                    await client.upload(
                        rule_id=self.dcr_immutable_id, stream_name=self.stream_name, logs=rows
                    )
        except HttpResponseError as exc:
            raise LogControlError("Seeding the PRI-004 demo log entries failed.") from exc

    async def _query(self, kql_filter: str) -> list[dict]:
        query = (
            f"{self.table_name} | {kql_filter} "
            "| project TimeGenerated, RecordId, FieldName, Message, Source"
        )
        async with AzureCliCredential() as credential:
            async with LogsQueryClient(credential) as client:
                response = await client.query_workspace(
                    workspace_id=self.workspace_customer_id,
                    query=query,
                    timespan=timedelta(hours=1),
                )
        if response.status != LogsQueryStatus.SUCCESS:
            raise LogControlError("PRI-004 log query failed; no state change is allowed.")
        table = response.tables[0]
        columns = [column if isinstance(column, str) else column.name for column in table.columns]
        return [dict(zip(columns, row, strict=True)) for row in table.rows]

    async def _query_single(self, record_id: str) -> dict | None:
        rows = await self._query(
            f"where RecordId == '{record_id}' | order by TimeGenerated desc | take 1"
        )
        return rows[0] if rows else None

    async def _query_distinct_record_ids(self, prefix: str) -> list[str]:
        query = f"{self.table_name} | where RecordId startswith '{prefix}' | distinct RecordId"
        async with AzureCliCredential() as credential:
            async with LogsQueryClient(credential) as client:
                response = await client.query_workspace(
                    workspace_id=self.workspace_customer_id,
                    query=query,
                    timespan=timedelta(hours=1),
                )
        if response.status != LogsQueryStatus.SUCCESS:
            raise LogControlError("PRI-004 log query failed; no state change is allowed.")
        return [row[0] for row in response.tables[0].rows]

    async def scan(
        self,
        evaluated_at: datetime | None = None,
        max_attempts: int = 5,
        retry_seconds: float = 15.0,
    ) -> tuple[list[LogDecision], bool]:
        """Evaluate recently ingested rows; second return value is True while ingestion is still catching up."""
        evaluated_at = (evaluated_at or datetime.now(UTC)).astimezone(UTC)
        rows: list[dict] = []
        for attempt in range(max_attempts):
            rows = await self._query(f"where RecordId startswith '{RECORD_PREFIX}'")
            if rows:
                break
            if attempt < max_attempts - 1:
                await asyncio.sleep(retry_seconds)
        if not rows:
            return [], True

        decisions: list[LogDecision] = []
        for row in rows:
            record_id = row.get("RecordId", "unknown-record")
            field_name = row.get("FieldName", "Message")
            message = row.get("Message", "") or ""
            source = row.get("Source", "unknown")
            time_generated = row.get("TimeGenerated") or evaluated_at
            detector_unavailable = message == DETECTOR_UNAVAILABLE_MARKER
            record = LogRecord(
                record_id=record_id,
                field_name=field_name,
                message=message,
                source=source,
                time_generated=time_generated,
                detector_unavailable=detector_unavailable,
            )
            if detector_unavailable:
                decisions.append(evaluate_log_entry(record, None, evaluated_at))
                continue
            try:
                scan_result = await scan_message(message)
            except PiiDetectionError:
                decisions.append(evaluate_log_entry(record, None, evaluated_at))
                continue
            decisions.append(evaluate_log_entry(record, scan_result.categories, evaluated_at))
        return decisions, False

    async def mask_preview(self, decision: LogDecision) -> str:
        """Non-destructive redacted preview; Log Analytics rows cannot be mutated in place."""
        row = await self._query_single(decision.record_id)
        if row is None:
            raise LogControlError("The log record no longer exists; rescan first.")
        try:
            scan_result = await scan_message(row.get("Message", "") or "")
        except PiiDetectionError as exc:
            raise LogControlError("Preview unavailable; PII detection failed.") from exc
        return scan_result.redacted_text

    def request_purge_approval(self, decision: LogDecision) -> None:
        allowed, reason = evaluate_purge_request(decision, decision.message_hash)
        if not allowed:
            raise LogControlError(reason)

    async def _submit_purge(self, table_filters: list[dict]) -> str:
        url = (
            f"https://management.azure.com/subscriptions/{self.subscription_id}"
            f"/resourceGroups/{self.resource_group}/providers/Microsoft.OperationalInsights"
            f"/workspaces/{self.workspace_name}/purge?api-version={PURGE_API_VERSION}"
        )
        async with AzureCliCredential() as credential:
            token = await credential.get_token(MANAGEMENT_SCOPE)
            async with httpx.AsyncClient() as http_client:
                response = await http_client.post(
                    url,
                    json={"table": self.table_name, "filters": table_filters},
                    headers={"Authorization": f"Bearer {token.token}"},
                )
        if response.status_code != 202:
            raise LogControlError(
                f"Purge request failed ({response.status_code}); no deletion was submitted."
            )
        return response.json()["operationId"]

    async def execute_purge(
        self, decision: LogDecision, approval: ApprovalTicket | None
    ) -> LogRemediationResult:
        """Submit a real, guarded Azure Monitor Data Purge request after re-verification.

        Agent Control Specification is the real gate here: `run_tool` escalates
        `pre_tool_call` for every guarded purge, and the caller-supplied
        `approval` ticket is the only thing that can resolve that escalation --
        a missing, rejected, expired, or already-used ticket fails closed
        before any purge is submitted. ACS's `action_identity` binds the
        approval to this exact record_id/message_hash pair, so a log record
        that changed after the scan is blocked even if the human already
        clicked approve.
        """
        if approval is None or not approval.claim():
            return blocked_result(
                decision, "No valid, single-use approval was provided for this purge."
            )
        row = await self._query_single(decision.record_id)
        if row is None:
            return blocked_result(decision, "The log record no longer exists; rescan first.")
        current_hash = compute_message_hash(row.get("Message", "") or "")
        allowed, reason = evaluate_purge_request(decision, current_hash)
        if not allowed:
            return blocked_result(decision, reason)

        async def execute(args: dict[str, str]) -> dict[str, object]:
            operation_id = await self._submit_purge(
                [{"column": "RecordId", "operator": "==", "value": args["record_id"]}]
            )
            return {"operation_id": operation_id}

        control = get_control()
        tool_result = await control.run_tool(
            "submit_data_purge",
            {"record_id": decision.record_id, "message_hash": current_hash},
            execute,
            approval_resolver=resolver_for(approval),
        )
        operation_id = tool_result.value["operation_id"]
        evidence_id = record_evidence(decision, "purge_requested", operation_id)
        return LogRemediationResult(
            decision_id=decision.decision_id,
            record_id=decision.record_id,
            status="purge_requested",
            operation_id=operation_id,
            evidence_id=evidence_id,
            message=(
                "A real Azure Monitor Data Purge request was submitted. Completion is "
                "asynchronous and can take up to 30 days per Microsoft's documented SLA."
            ),
        )

    async def check_purge_status(self, operation_id: str) -> str:
        # operation_id returned by the current API version already includes any prefix.
        url = (
            f"https://management.azure.com/subscriptions/{self.subscription_id}"
            f"/resourceGroups/{self.resource_group}/providers/Microsoft.OperationalInsights"
            f"/workspaces/{self.workspace_name}/operations/{operation_id}"
            f"?api-version={PURGE_API_VERSION}"
        )
        async with AzureCliCredential() as credential:
            token = await credential.get_token(MANAGEMENT_SCOPE)
            async with httpx.AsyncClient() as http_client:
                response = await http_client.get(
                    url, headers={"Authorization": f"Bearer {token.token}"}
                )
        if response.status_code != 200:
            raise LogControlError(f"Purge status lookup failed ({response.status_code}).")
        return response.json().get("status", "unknown")

    def request_field_policy_approval(self, decision: LogDecision) -> None:
        allowed, reason = evaluate_field_policy_change(
            decision.field_name, decision.field_name in self._suppressed_fields
        )
        if not allowed:
            raise LogControlError(reason)

    async def apply_field_policy(
        self, decision: LogDecision, approval: ApprovalTicket | None
    ) -> LogRemediationResult:
        """Suppress a field after ACS approval and re-verification.

        The same ACS `pre_tool_call`/`post_tool_call` gate as `execute_purge`
        protects this state change; the approval is bound to the exact field
        name ACS evaluated, and a missing, rejected, expired, or already-used
        ticket fails closed before any state changes.
        """
        if approval is None or not approval.claim():
            return blocked_result(
                decision, "No valid, single-use approval was provided for this field policy change."
            )
        field_name = decision.field_name
        allowed, reason = evaluate_field_policy_change(
            field_name, field_name in self._suppressed_fields
        )
        if not allowed:
            return blocked_result(decision, reason)

        async def execute(args: dict[str, str]) -> dict[str, object]:
            self._suppressed_fields.add(args["field_name"])
            return {"suppressed": True}

        control = get_control()
        await control.run_tool(
            "apply_field_policy",
            {"field_name": field_name},
            execute,
            approval_resolver=resolver_for(approval),
        )
        evidence_id = record_evidence(decision, "field_suppressed")
        return LogRemediationResult(
            decision_id=decision.decision_id,
            record_id=decision.record_id,
            status="field_suppressed",
            operation_id=None,
            evidence_id=evidence_id,
            message=(
                f"Field '{field_name}' will be redacted client-side before future demo "
                "ingestion. Existing ingested rows are unchanged; seed a follow-up record "
                "to see the effect."
            ),
        )

    async def seed_followup_for_field(self, field_name: str) -> None:
        """Seed one more record for a field to demonstrate the update-logging fix going forward."""
        row = {
            "TimeGenerated": datetime.now(UTC).isoformat(),
            "RecordId": f"{RECORD_PREFIX}followup-{uuid.uuid4().hex[:8]}",
            "FieldName": field_name,
            "Message": self._redact_if_suppressed(
                field_name, "order confirmation sent to jane.doe@example.com"
            ),
            "Source": "checkout-service",
        }
        try:
            async with AzureCliCredential() as credential:
                async with LogsIngestionClient(self.dcr_endpoint, credential=credential) as client:
                    await client.upload(
                        rule_id=self.dcr_immutable_id, stream_name=self.stream_name, logs=[row]
                    )
        except HttpResponseError as exc:
            raise LogControlError("Seeding the follow-up record failed.") from exc

    async def cleanup(self) -> LogRemediationResult:
        """Submit a broad guarded purge covering only PRI-004 synthetic records."""
        # The Purge API only supports ==, =~, in, in~, >, >=, <, <=, between — no prefix
        # match — so the demo record ids are resolved first and purged with "in".
        record_ids = await self._query_distinct_record_ids(RECORD_PREFIX)
        if not record_ids:
            return LogRemediationResult(
                decision_id="cleanup",
                record_id=RECORD_PREFIX,
                status="nothing_to_purge",
                operation_id=None,
                evidence_id="",
                message="No PRI-004 synthetic records were found; nothing to purge.",
            )
        operation_id = await self._submit_purge(
            [{"column": "RecordId", "operator": "in", "value": record_ids}]
        )
        return LogRemediationResult(
            decision_id="cleanup",
            record_id=RECORD_PREFIX,
            status="purge_requested",
            operation_id=operation_id,
            evidence_id="",
            message=(
                "A broad Data Purge request for all PRI-004 synthetic records was submitted. "
                "Completion is asynchronous per Microsoft's documented SLA (up to 30 days)."
            ),
        )
