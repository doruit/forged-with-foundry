"""Data contracts for deterministic DSR SLA evaluation and guarded extension grants."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class DSRRequestType(StrEnum):
    ACCESS = "access"
    RECTIFICATION = "rectification"
    ERASURE = "erasure"


class DSRStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    WITHDRAWN = "withdrawn"


class DSRAction(StrEnum):
    ON_TRACK = "on_track"
    AT_RISK = "at_risk"
    BREACHED = "breached"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class DSRPolicy:
    request_type: str
    sla_days: int
    extension_days: int
    extension_allowed: bool


@dataclass(frozen=True)
class DSRRecord:
    """Opaque, non-identifying record; no requester name, email, or content."""

    request_id: str
    request_type: str | None
    received_date: datetime
    status: DSRStatus
    etag: str
    extension_granted: bool = False


@dataclass(frozen=True)
class DSRDecision:
    decision_id: str
    control_id: str
    action: DSRAction
    request_id: str
    request_type: str | None
    etag: str
    due_date: datetime | None
    days_until_due: int | None
    resolved: bool
    extension_granted: bool
    reason: str

    def safe_dict(self) -> dict[str, object]:
        """Return metadata safe for agent prompts, UI, logs, and evidence."""
        return {
            "decision_id": self.decision_id,
            "control_id": self.control_id,
            "action": self.action.value,
            "request_id": self.request_id,
            "request_type": self.request_type,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "days_until_due": self.days_until_due,
            "resolved": self.resolved,
            "extension_granted": self.extension_granted,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class DSRExtensionResult:
    decision_id: str
    request_id: str
    status: str
    extension_granted: bool
    evidence_id: str
    message: str
