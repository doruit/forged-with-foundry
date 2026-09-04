"""Data contracts for deterministic Purview sensitivity-label classification (DAT-PRE-002)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ClassificationAction(StrEnum):
    COMPLIANT = "compliant"
    FLAGGED = "flagged"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class DemoFile:
    """One synthetic file in the DAT-PRE-002 demo OneDrive folder."""

    name: str
    item_id: str
    content_category: str | None
    # Demo-only marker; skips calling extractSensitivityLabels for a simulated failure.
    extraction_failed: bool = False


@dataclass(frozen=True)
class ClassificationDecision:
    decision_id: str
    control_id: str
    action: ClassificationAction
    item_id: str
    file_name: str
    content_category: str | None
    current_label_ids: tuple[str, ...]
    required_label_id: str | None
    reason: str

    def safe_dict(self) -> dict[str, object]:
        """Return metadata safe for agent prompts, UI, logs, and evidence; never file content."""
        return {
            "decision_id": self.decision_id,
            "control_id": self.control_id,
            "action": self.action.value,
            "file_name": self.file_name,
            "content_category": self.content_category,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ClassifyApproval:
    token: str
    decision_id: str
    item_id: str
    required_label_id: str
    label_snapshot: tuple[str, ...]
    expires_at: datetime


@dataclass(frozen=True)
class ClassifyResult:
    decision_id: str
    item_id: str
    status: str  # "resolved" | "pending" | "blocked"
    operation_id: str | None
    evidence_id: str
    message: str
