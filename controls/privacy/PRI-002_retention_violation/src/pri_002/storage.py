"""Azure Blob adapter for the isolated PRI-002 demo container."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

from azure.core import MatchConditions
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob.aio import BlobServiceClient

from .approval import ApprovalRegistry
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
    def __init__(self, approvals: ApprovalRegistry | None = None) -> None:
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
        self.approvals = approvals or ApprovalRegistry()
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

    def approve(self, decision: RetentionDecision) -> str:
        if decision.action is not RetentionAction.REMEDIATION_REQUIRED:
            raise RetentionControlError("Only confirmed retention violations can be approved.")
        return self.approvals.issue(decision).token

    async def remediate(
        self,
        decision: RetentionDecision,
        approval_token: str,
    ) -> RemediationResult:
        """Delete only the approved, unchanged Blob and verify active absence."""
        if decision.action is not RetentionAction.REMEDIATION_REQUIRED:
            return blocked_result(decision, "The deterministic policy did not authorize deletion.")
        self._validate_blob_name(decision.blob_name)
        self.approvals.consume(approval_token, decision)

        async with DefaultAzureCredential() as credential:
            service = self._client(credential)
            blob = service.get_blob_client(self.container_name, decision.blob_name)
            try:
                properties = await blob.get_blob_properties()
                if str(properties.etag) != decision.etag:
                    return blocked_result(
                        decision,
                        "The Blob changed after evaluation; deletion was blocked. Rescan first.",
                    )
                await blob.delete_blob(
                    delete_snapshots="include",
                    etag=decision.etag,
                    match_condition=MatchConditions.IfNotModified,
                )
                try:
                    await blob.get_blob_properties()
                    verified_absent = False
                except ResourceNotFoundError:
                    verified_absent = True

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
            except ResourceNotFoundError:
                return blocked_result(
                    decision,
                    "The Blob no longer exists; remediation was not repeated.",
                )
            except Exception as exc:
                raise RetentionControlError(
                    "Guarded remediation failed; the outcome is not claimed as compliant."
                ) from exc
            finally:
                await service.close()

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
