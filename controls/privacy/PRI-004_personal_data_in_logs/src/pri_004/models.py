"""Data contracts for deterministic log-PII evaluation and guarded remediation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class LogAction(StrEnum):
    CLEAN = "clean"
    PII_DETECTED = "pii_detected"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class LogRecord:
    """Opaque log row; the message is the only field that may carry personal data."""

    record_id: str
    field_name: str
    message: str
    source: str
    time_generated: datetime
    # Demo-only marker simulating a detector outage without breaking real infra.
    detector_unavailable: bool = False


@dataclass(frozen=True)
class LogDecision:
    decision_id: str
    control_id: str
    action: LogAction
    record_id: str
    field_name: str
    message_hash: str
    pii_categories: tuple[str, ...]
    reason: str

    def safe_dict(self) -> dict[str, object]:
        """Return metadata safe for agent prompts, UI, logs, and evidence; never the raw message."""
        return {
            "decision_id": self.decision_id,
            "control_id": self.control_id,
            "action": self.action.value,
            "record_id": self.record_id,
            "field_name": self.field_name,
            "pii_categories": list(self.pii_categories),
            "reason": self.reason,
        }


@dataclass(frozen=True)
class PurgeApproval:
    token: str
    decision_id: str
    record_id: str
    message_hash: str
    expires_at: datetime


@dataclass(frozen=True)
class FieldPolicyApproval:
    token: str
    decision_id: str
    field_name: str
    expires_at: datetime


@dataclass(frozen=True)
class LogRemediationResult:
    decision_id: str
    record_id: str
    status: str
    operation_id: str | None
    evidence_id: str
    message: str


@dataclass(frozen=True)
class PiiScanResult:
    """Raw Text PII output for one message; feeds evaluate_log_entry, not a decision itself."""

    categories: tuple[str, ...]
    redacted_text: str
