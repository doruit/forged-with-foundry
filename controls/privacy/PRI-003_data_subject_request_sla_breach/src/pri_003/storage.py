"""Azure Table Storage adapter for the isolated PRI-003 DSR register."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

from azure.core import MatchConditions
from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
from azure.data.tables import UpdateMode
from azure.data.tables.aio import TableServiceClient
from azure.identity.aio import DefaultAzureCredential

from .acs_gate import ApprovalTicket, get_control, resolver_for
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
        completed_date=entity.get("CompletedDate"),
    )


class DSRStore:
    def __init__(self) -> None:
        self.account_url = os.getenv("PRI003_TABLE_ENDPOINT", "").strip().rstrip("/")
        if not self.account_url:
            raise DSRControlError(
                "PRI-003 storage is not configured; deploy the control infrastructure."
            )
        self.table_name = os.getenv("PRI003_TABLE_NAME", "pri003dsrrequests").strip()

    def _client(self, credential: DefaultAzureCredential) -> TableServiceClient:
        return TableServiceClient(self.account_url, credential=credential)

    async def seed_scenarios(self) -> None:
        """Create synthetic DSR records covering every decision outcome."""
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
                # Received 50 days ago (30-day SLA, due 20 days ago) and closed
                # 15 days after the deadline: breached regardless of scan time.
                "RowKey": "breached-access-completed-late",
                "RequestType": "access",
                "ReceivedDate": now - timedelta(days=50),
                "Status": DSRStatus.COMPLETED.value,
                "CompletedDate": now - timedelta(days=15),
            },
            {
                # Received 50 days ago but closed 25 days ago, before the
                # 30-day deadline: on track regardless of scan time.
                "RowKey": "on-track-access-completed",
                "RequestType": "access",
                "ReceivedDate": now - timedelta(days=50),
                "Status": DSRStatus.COMPLETED.value,
                "CompletedDate": now - timedelta(days=25),
            },
            {
                # Closed with no CompletedDate recorded: the outcome cannot be
                # judged, so this must fail closed rather than guess from
                # scan time.
                "RowKey": "blocked-completed-missing-evidence",
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
        if decision.resolved:
            raise DSRControlError("The request is already closed; no escalation is needed.")
        evidence_id = record_evidence(decision, escalated=True, extension_granted=False)
        return DSRExtensionResult(
            decision_id=decision.decision_id,
            request_id=decision.request_id,
            status="escalated",
            extension_granted=False,
            evidence_id=evidence_id,
            message="Escalation recorded for the DPO. No DSR record was modified.",
        )

    def request_extension_approval(self, decision: DSRDecision) -> None:
        """Validate eligibility from the scanned decision before granting an extension."""
        policy = POLICIES.get(decision.request_type or "")
        if policy is None:
            raise DSRControlError(
                "DSR request type is missing or unknown; the extension is refused."
            )
        if decision.resolved:
            raise DSRControlError(
                "The request is already closed; extending its due date is refused."
            )
        if decision.extension_granted:
            raise DSRControlError(
                "An extension was already granted; only one extension is permitted."
            )
        if not policy.extension_allowed:
            raise DSRControlError(f"{policy.request_type} requests do not permit an SLA extension.")
        if decision.action not in (DSRAction.AT_RISK, DSRAction.BREACHED):
            raise DSRControlError("Only at-risk or breached decisions require an extension.")

    async def grant_extension(
        self, decision: DSRDecision, approval: ApprovalTicket | None
    ) -> DSRExtensionResult:
        """Apply an ETag-conditional extension grant after ACS approval and re-validation.

        Agent Control Specification is the real gate here: `run_tool` escalates
        `pre_tool_call` for every guarded extension, and the caller-supplied
        `approval` ticket is the only thing that can resolve that escalation --
        a missing, rejected, expired, or already-used ticket fails closed
        before any Table call is made. ACS's `action_identity` binds the
        approval to this exact request_id/etag pair, so a record that changed
        after the scan is blocked even if the human already clicked approve.
        """
        if approval is None or not approval.claim():
            return blocked_result(
                decision, "No valid, single-use approval was provided for this extension."
            )

        async def execute(args: dict[str, str]) -> dict[str, object]:
            async with DefaultAzureCredential() as credential:
                service = self._client(credential)
                table = service.get_table_client(self.table_name)
                try:
                    entity = await table.get_entity(PARTITION_KEY, args["request_id"])
                    if str(entity.metadata["etag"]) != args["etag"]:
                        return {"blocked": True, "reason": "etag_changed"}
                    record = _entity_to_record(entity)
                    allowed, reason = evaluate_extension_request(record, POLICIES)
                    if not allowed:
                        return {"blocked": True, "reason": "policy_refused", "message": reason}

                    entity["ExtensionGranted"] = True
                    await table.update_entity(
                        entity,
                        mode=UpdateMode.MERGE,
                        etag=args["etag"],
                        match_condition=MatchConditions.IfNotModified,
                    )
                    return {"blocked": False}
                except ResourceNotFoundError:
                    return {"blocked": True, "reason": "record_missing"}
                finally:
                    await service.close()

        control = get_control()
        try:
            tool_result = await control.run_tool(
                "extend_dsr_due_date",
                {"request_id": decision.request_id, "etag": decision.etag},
                execute,
                approval_resolver=resolver_for(approval),
            )
        except HttpResponseError as exc:
            raise DSRControlError(
                "Guarded extension failed; the outcome is not claimed as granted."
            ) from exc

        outcome = tool_result.value
        if not isinstance(outcome, dict) or outcome.get("blocked"):
            reason = outcome.get("reason") if isinstance(outcome, dict) else None
            if reason == "etag_changed":
                return blocked_result(
                    decision,
                    "The DSR record changed after evaluation; extension was blocked. Rescan first.",
                )
            if reason == "record_missing":
                return blocked_result(decision, "The DSR record no longer exists.")
            if reason == "policy_refused":
                return blocked_result(decision, str(outcome.get("message")))
            return blocked_result(decision, "Guarded extension was blocked by ACS.")

        evidence_id = record_evidence(decision, escalated=False, extension_granted=True)
        return DSRExtensionResult(
            decision_id=decision.decision_id,
            request_id=decision.request_id,
            status="extended",
            extension_granted=True,
            evidence_id=evidence_id,
            message="The SLA due date was extended and recorded.",
        )

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
