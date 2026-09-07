"""Azure Blob adapter for the isolated PRI-002 demo container."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

from azure.core import MatchConditions
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob.aio import BlobServiceClient

from .acs_gate import ApprovalTicket, get_control, resolver_for
from .evidence import blocked_result, record_evidence
from .models import (
    RemediationResult,
    RetentionAction,
    RetentionDecision,
    RetentionPolicy,
    RetentionRecord,
)
from .policy import evaluate_retention, fail_closed

CONTAINER_PREFIX = "pri-002-"
BLOB_PREFIX = "records/"
RETENTION_CLASS = os.getenv(
    "PRI002_LIFECYCLE_CLASS", "customer-conversation-30d"
).strip()
RETENTION_DAYS = int(os.getenv("PRI002_RETENTION_DAYS", "30"))
POLICIES = {
    RETENTION_CLASS: RetentionPolicy(
        retention_class=RETENTION_CLASS,
        retention_days=RETENTION_DAYS,
        grace_days=2,
        lifecycle_tag_name="LifecycleClass",
    )
}


class RetentionControlError(RuntimeError):
    """Raised when PRI-002 cannot safely inspect or remediate its scope."""


class RetentionStore:
    def __init__(self) -> None:
        self.account_url = (
            os.getenv("PRI002_STORAGE_BLOB_ENDPOINT", "").strip().rstrip("/")
        )
        if not self.account_url:
            raise RetentionControlError(
                "PRI-002 storage is not configured; deploy the control infrastructure."
            )
        self.container_name = os.getenv(
            "PRI002_CONTAINER", "pri-002-retention-demo"
        ).strip()
        self._validate_container()

    def _validate_container(self) -> None:
        if not self.container_name.startswith(CONTAINER_PREFIX):
            raise RetentionControlError(
                "PRI-002 refuses to operate outside a pri-002-* container."
            )

    @staticmethod
    def _validate_blob_name(blob_name: str) -> None:
        if not blob_name.startswith(BLOB_PREFIX) or ".." in blob_name:
            raise RetentionControlError(
                "PRI-002 refuses to operate outside its records/ prefix."
            )

    def _client(self, credential: DefaultAzureCredential) -> BlobServiceClient:
        return BlobServiceClient(self.account_url, credential=credential)

    async def seed_scenarios(self) -> None:
        """Create three content-free synthetic scenarios with safe index tags."""
        scenarios = {
            "compliant": {
                "RetentionClass": RETENTION_CLASS,
                "LifecycleClass": RETENTION_CLASS,
                "DemoAgeDays": "10",
                "DemoLegalHold": "false",
            },
            "overdue-mistagged": {
                "RetentionClass": RETENTION_CLASS,
                "DemoAgeDays": "45",
                "DemoLegalHold": "false",
            },
            "protected": {
                "RetentionClass": RETENTION_CLASS,
                "LifecycleClass": RETENTION_CLASS,
                "DemoAgeDays": "45",
                "DemoLegalHold": "true",
            },
        }
        async with DefaultAzureCredential() as credential:
            service = self._client(credential)
            container = service.get_container_client(self.container_name)
            try:
                await container.create_container()
            except ResourceExistsError:
                pass

            async for blob in container.list_blobs(name_starts_with=BLOB_PREFIX):
                await container.delete_blob(blob.name, delete_snapshots="include")

            for record_id, tags in scenarios.items():
                blob_name = f"{BLOB_PREFIX}{record_id}.json"
                await container.upload_blob(
                    name=blob_name,
                    data=b'{"synthetic":true}',
                    overwrite=False,
                    tags={"DemoRecordId": record_id, **tags},
                )
            await service.close()

    async def scan(self, evaluated_at: datetime | None = None) -> list[RetentionDecision]:
        """List metadata/tags only and evaluate projected lifecycle outcomes."""
        evaluated_at = (evaluated_at or datetime.now(UTC)).astimezone(UTC)
        decisions: list[RetentionDecision] = []
        async with DefaultAzureCredential() as credential:
            service = self._client(credential)
            container = service.get_container_client(self.container_name)
            try:
                async for blob in container.list_blobs(
                    name_starts_with=BLOB_PREFIX,
                    include=["tags", "legalhold", "immutabilitypolicy"],
                ):
                    self._validate_blob_name(blob.name)
                    tags = dict(blob.tags or {})
                    record_id = tags.get("DemoRecordId", "unknown-record")
                    try:
                        demo_age_days = int(tags["DemoAgeDays"])
                        projected_modified = evaluated_at - timedelta(
                            days=demo_age_days
                        )
                    except (KeyError, TypeError, ValueError):
                        decisions.append(
                            fail_closed(
                                record_id,
                                "Required retention metadata is missing or invalid.",
                            )
                        )
                        continue

                    record = RetentionRecord(
                        record_id=record_id,
                        blob_name=blob.name,
                        etag=str(blob.etag),
                        last_modified=projected_modified,
                        retention_class=tags.get("RetentionClass"),
                        lifecycle_tag=tags.get("LifecycleClass"),
                        legal_hold=(
                            tags.get("DemoLegalHold", "false").lower() == "true"
                            or bool(getattr(blob, "has_legal_hold", False))
                        ),
                        immutable=bool(getattr(blob, "immutability_policy", None)),
                    )
                    decisions.append(evaluate_retention(record, POLICIES, evaluated_at))
            except ResourceNotFoundError as exc:
                raise RetentionControlError(
                    "PRI-002 container is missing; deploy infrastructure or seed the demo."
                ) from exc
            except RetentionControlError:
                raise
            except Exception as exc:
                raise RetentionControlError(
                    "Retention scan failed; no destructive action is allowed."
                ) from exc
            finally:
                await service.close()
        return decisions

    async def remediate(
        self, decision: RetentionDecision, approval: ApprovalTicket | None
    ) -> RemediationResult:
        """Delete only the approved, still-noncompliant Blob and verify active absence.

        Agent Control Specification is the real gate here: `run_tool` escalates
        `pre_tool_call` for every guarded delete, and the caller-supplied
        `approval` ticket is the only thing that can resolve that escalation --
        a missing, rejected, expired, or already-used ticket fails closed.
        Blob index tags are a separate index from blob properties and are not
        reflected in the blob's ETag, so an ETag match alone cannot prove the
        retention-relevant tags (legal hold, retention class) are unchanged since
        the scan. `execute` re-fetches the current tags and re-runs the
        deterministic policy immediately before deleting, and refuses if the
        record is no longer `REMEDIATION_REQUIRED`.
        """
        if decision.action is not RetentionAction.REMEDIATION_REQUIRED:
            return blocked_result(decision, "The deterministic policy did not authorize deletion.")
        self._validate_blob_name(decision.blob_name)
        if approval is None or not approval.claim():
            # Absent or already-used approval fails closed before any Azure
            # call is made; approval is never assumed just because this
            # method was called.
            return blocked_result(
                decision, "No valid, single-use approval was provided for this deletion."
            )

        async def execute(args: dict[str, str]) -> dict[str, object]:
            async with DefaultAzureCredential() as credential:
                service = self._client(credential)
                blob = service.get_blob_client(self.container_name, args["blob_name"])
                try:
                    properties = await blob.get_blob_properties()
                    if str(properties.etag) != args["etag"]:
                        return {"blocked": True, "reason": "etag_changed"}

                    current_tags = await blob.get_blob_tags() or {}
                    try:
                        demo_age_days = int(current_tags["DemoAgeDays"])
                    except (KeyError, TypeError, ValueError):
                        return {"blocked": True, "reason": "metadata_changed"}
                    now = datetime.now(UTC)
                    current_record = RetentionRecord(
                        record_id=decision.record_id,
                        blob_name=args["blob_name"],
                        etag=args["etag"],
                        last_modified=now - timedelta(days=demo_age_days),
                        retention_class=current_tags.get("RetentionClass"),
                        lifecycle_tag=current_tags.get("LifecycleClass"),
                        legal_hold=(
                            current_tags.get("DemoLegalHold", "false").lower() == "true"
                            or bool(getattr(properties, "has_legal_hold", False))
                        ),
                        immutable=bool(getattr(properties, "immutability_policy", None)),
                    )
                    fresh = evaluate_retention(current_record, POLICIES, now)
                    if fresh.action is not RetentionAction.REMEDIATION_REQUIRED:
                        return {
                            "blocked": True,
                            "reason": "policy_changed",
                            "current_action": fresh.action.value,
                        }

                    await blob.delete_blob(
                        delete_snapshots="include",
                        etag=args["etag"],
                        match_condition=MatchConditions.IfNotModified,
                    )
                    try:
                        await blob.get_blob_properties()
                        verified_absent = False
                    except ResourceNotFoundError:
                        verified_absent = True
                    return {"blocked": False, "verified_absent": verified_absent}
                except ResourceNotFoundError:
                    return {"blocked": True, "reason": "blob_missing"}
                finally:
                    await service.close()

        control = get_control()
        try:
            tool_result = await control.run_tool(
                "delete_expired_blob",
                {
                    "blob_name": decision.blob_name,
                    "etag": decision.etag,
                    # Binding the scanned retention inputs (not just
                    # blob_name/etag) into the tool_call args means ACS's
                    # action_identity changes if these inputs change, so a
                    # stale approval cannot be replayed against new state.
                    "retention_class": decision.retention_class or "",
                    "lifecycle_covered": str(decision.lifecycle_covered),
                    "legal_hold": str(decision.legal_hold),
                },
                execute,
                approval_resolver=resolver_for(approval),
            )
        except Exception as exc:
            raise RetentionControlError(
                "Guarded remediation failed; the outcome is not claimed as compliant."
            ) from exc

        outcome = tool_result.value
        if not isinstance(outcome, dict) or outcome.get("blocked"):
            reason = outcome.get("reason") if isinstance(outcome, dict) else None
            if reason == "etag_changed":
                return blocked_result(
                    decision,
                    "The Blob changed after evaluation; deletion was blocked. Rescan first.",
                )
            if reason == "metadata_changed":
                return blocked_result(
                    decision,
                    "The Blob's retention metadata is missing or invalid; deletion was blocked. Rescan first.",
                )
            if reason == "policy_changed":
                current_action = outcome.get("current_action", "unknown")
                return blocked_result(
                    decision,
                    "The Blob's retention tags changed since the scan and no longer "
                    f"authorize deletion (current outcome: {current_action}). Rescan first.",
                )
            if reason == "blob_missing":
                return blocked_result(
                    decision,
                    "The Blob no longer exists; remediation was not repeated.",
                )
            return blocked_result(decision, "Guarded remediation was blocked by ACS.")

        verified_absent = bool(outcome["verified_absent"])
        status = "deleted_from_active_namespace" if verified_absent else "verification_failed"
        evidence_id = record_evidence(decision, status, verified_absent, True)
        return RemediationResult(
            decision_id=decision.decision_id,
            record_id=decision.record_id,
            status=status,
            verified_absent=verified_absent,
            evidence_id=evidence_id,
            message=(
                "The expired record was removed from the active namespace and verified."
                if verified_absent
                else "Deletion could not be verified; escalation is required."
            ),
        )

    async def cleanup(self) -> None:
        """Delete only synthetic blobs; retain the control-owned container."""
        async with DefaultAzureCredential() as credential:
            service = self._client(credential)
            container = service.get_container_client(self.container_name)
            try:
                async for blob in container.list_blobs(name_starts_with=BLOB_PREFIX):
                    self._validate_blob_name(blob.name)
                    await container.delete_blob(blob.name, delete_snapshots="include")
            except ResourceNotFoundError:
                return
            finally:
                await service.close()
