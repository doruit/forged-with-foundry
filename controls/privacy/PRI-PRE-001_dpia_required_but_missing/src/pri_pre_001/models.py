"""Data contracts for deterministic DPIA-required-but-missing gate evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class RiskFactor(StrEnum):
    """Subset of GDPR Art. 35 / WP29 DPIA-screening criteria (illustrative, not legal advice)."""

    SPECIAL_CATEGORY_DATA = "special_category_data"
    AUTOMATED_DECISION_MAKING = "automated_decision_making"
    LARGE_SCALE_MONITORING = "large_scale_monitoring"
    VULNERABLE_SUBJECTS = "vulnerable_subjects"


class DpiaStatus(StrEnum):
    NOT_STARTED = "not_started"
    PENDING = "pending"
    COMPLETED = "completed"


class GateAction(StrEnum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    BLOCKED_UNKNOWN = "blocked_unknown"


@dataclass(frozen=True)
class ProjectRecord:
    """Opaque AI-system/project register entry; no project name or business content."""

    project_id: str
    risk_factors: tuple[RiskFactor, ...] | None
    dpia_status: DpiaStatus
    dpia_approver: str
    dpia_date: datetime | None
    dpia_report_id: str
    etag: str
    go_live_requested: bool = False


@dataclass(frozen=True)
class GateDecision:
    decision_id: str
    control_id: str
    action: GateAction
    project_id: str
    etag: str
    risk_factor_count: int | None
    dpia_required: bool
    evidence_complete: bool
    reason: str

    def safe_dict(self) -> dict[str, object]:
        """Return metadata safe for agent prompts, UI, logs, and evidence."""
        return {
            "decision_id": self.decision_id,
            "control_id": self.control_id,
            "action": self.action.value,
            "project_id": self.project_id,
            "risk_factor_count": self.risk_factor_count,
            "dpia_required": self.dpia_required,
            "evidence_complete": self.evidence_complete,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class GoLiveAttemptResult:
    decision_id: str
    project_id: str
    status: str
    azure_policy_denied: bool | None
    evidence_id: str
    message: str
