"""Data contracts for deterministic lawful-basis/purpose gate evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class LawfulBasis(StrEnum):
    """GDPR Article 6(1) lawful bases for processing (illustrative, not legal advice)."""

    CONSENT = "consent"
    CONTRACT = "contract"
    LEGAL_OBLIGATION = "legal_obligation"
    VITAL_INTERESTS = "vital_interests"
    PUBLIC_TASK = "public_task"
    LEGITIMATE_INTERESTS = "legitimate_interests"


class GateAction(StrEnum):
    ALLOWED = "allowed"
    COMPLIANT = "compliant"
    FLAGGED = "flagged"
    FLAGGED_UNKNOWN = "flagged_unknown"


@dataclass(frozen=True)
class ProjectRecord:
    """Opaque AI-system/project register entry; no project name or business content."""

    project_id: str
    environment: str
    processes_personal_data: bool
    lawful_basis_raw: str
    purpose_id: str
    etag: str


@dataclass(frozen=True)
class GateDecision:
    decision_id: str
    control_id: str
    action: GateAction
    project_id: str
    etag: str
    processes_personal_data: bool
    lawful_basis_valid: bool
    purpose_documented: bool
    reason: str

    def safe_dict(self) -> dict[str, object]:
        """Return metadata safe for agent prompts, UI, logs, and evidence."""
        return {
            "decision_id": self.decision_id,
            "control_id": self.control_id,
            "action": self.action.value,
            "project_id": self.project_id,
            "processes_personal_data": self.processes_personal_data,
            "lawful_basis_valid": self.lawful_basis_valid,
            "purpose_documented": self.purpose_documented,
            "reason": self.reason,
        }
