"""Data contracts for deterministic retention evaluation and remediation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class RetentionAction(StrEnum):
    COMPLIANT = "compliant"
    REMEDIATION_REQUIRED = "remediation_required"
    PROTECTED = "protected"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class RetentionPolicy:
    retention_class: str
    retention_days: int
    grace_days: int
    lifecycle_tag_name: str = "RetentionClass"


@dataclass(frozen=True)
class RetentionRecord:
    """Metadata-only record; blob payloads are deliberately excluded."""

    record_id: str
    blob_name: str
    etag: str
    last_modified: datetime
    retention_class: str | None
    lifecycle_tag: str | None
    legal_hold: bool = False
    immutable: bool = False


@dataclass(frozen=True)
class RetentionDecision:
    decision_id: str
    control_id: str
    action: RetentionAction
    record_id: str
    blob_name: str
    etag: str
    retention_class: str | None
    retention_days: int | None
    grace_days: int | None
    age_days: int | None
    deadline: datetime | None
    lifecycle_covered: bool
    legal_hold: bool
    immutable: bool
    reason: str

    def safe_dict(self) -> dict[str, object]:
        """Return metadata safe for agent prompts, UI, logs, and evidence."""
        return {
            "decision_id": self.decision_id,
            "control_id": self.control_id,
            "action": self.action.value,
            "record_id": self.record_id,
            "retention_class": self.retention_class,
            "retention_days": self.retention_days,
            "grace_days": self.grace_days,
            "age_days": self.age_days,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "lifecycle_covered": self.lifecycle_covered,
            "legal_hold": self.legal_hold,
            "immutable": self.immutable,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class RemediationResult:
    decision_id: str
    record_id: str
    status: str
    verified_absent: bool
    evidence_id: str
    message: str
