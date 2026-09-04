"""Pure, deterministic PRI-PRE-002 lawful-basis/purpose gate evaluation."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from .models import GateAction, GateDecision, LawfulBasis, ProjectRecord

PRODUCTION_ENVIRONMENT = "production"

_VALID_BASES = {basis.value for basis in LawfulBasis}


def _decision_id(record: ProjectRecord, evaluated_at: datetime) -> str:
    material = f"{record.project_id}|{record.etag}|{evaluated_at.isoformat()}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def evaluate_lawful_basis_gate(record: ProjectRecord, evaluated_at: datetime) -> GateDecision:
    """Evaluate one project record without model reasoning or business content access."""
    if evaluated_at.tzinfo is None:
        raise ValueError("evaluated_at must be timezone-aware")
    evaluated_at = evaluated_at.astimezone(UTC)
    decision_id = _decision_id(record, evaluated_at)
    purpose_documented = bool(record.purpose_id.strip())

    if record.environment != PRODUCTION_ENVIRONMENT:
        return GateDecision(
            decision_id=decision_id,
            control_id="PRI-PRE-002",
            action=GateAction.ALLOWED,
            project_id=record.project_id,
            etag=record.etag,
            processes_personal_data=record.processes_personal_data,
            lawful_basis_valid=False,
            purpose_documented=purpose_documented,
            reason=(
                f"Environment '{record.environment}' is not production; "
                "the lawful-basis gate only applies to production deployments."
            ),
        )

    if not record.processes_personal_data:
        return GateDecision(
            decision_id=decision_id,
            control_id="PRI-PRE-002",
            action=GateAction.ALLOWED,
            project_id=record.project_id,
            etag=record.etag,
            processes_personal_data=False,
            lawful_basis_valid=False,
            purpose_documented=purpose_documented,
            reason="This project does not process personal data; the gate does not apply.",
        )

    raw_basis = record.lawful_basis_raw.strip()

    if not raw_basis:
        return GateDecision(
            decision_id=decision_id,
            control_id="PRI-PRE-002",
            action=GateAction.FLAGGED,
            project_id=record.project_id,
            etag=record.etag,
            processes_personal_data=True,
            lawful_basis_valid=False,
            purpose_documented=purpose_documented,
            reason="No lawful basis is on file for a project that processes personal data.",
        )

    if raw_basis not in _VALID_BASES:
        return GateDecision(
            decision_id=decision_id,
            control_id="PRI-PRE-002",
            action=GateAction.FLAGGED_UNKNOWN,
            project_id=record.project_id,
            etag=record.etag,
            processes_personal_data=True,
            lawful_basis_valid=False,
            purpose_documented=purpose_documented,
            reason=(
                f"Declared lawful basis '{raw_basis}' does not match a recognized "
                "GDPR Article 6(1) category; the gate cannot assess it and fails closed."
            ),
        )

    if not purpose_documented:
        return GateDecision(
            decision_id=decision_id,
            control_id="PRI-PRE-002",
            action=GateAction.FLAGGED,
            project_id=record.project_id,
            etag=record.etag,
            processes_personal_data=True,
            lawful_basis_valid=True,
            purpose_documented=False,
            reason="A valid lawful basis is on file, but no processing purpose is documented.",
        )

    return GateDecision(
        decision_id=decision_id,
        control_id="PRI-PRE-002",
        action=GateAction.COMPLIANT,
        project_id=record.project_id,
        etag=record.etag,
        processes_personal_data=True,
        lawful_basis_valid=True,
        purpose_documented=True,
        reason=f"Lawful basis '{raw_basis}' and a documented purpose are both on file.",
    )


def fail_closed(project_id: str, reason: str) -> GateDecision:
    return GateDecision(
        decision_id=hashlib.sha256(f"{project_id}|{reason}".encode()).hexdigest()[:16],
        control_id="PRI-PRE-002",
        action=GateAction.FLAGGED_UNKNOWN,
        project_id=project_id,
        etag="",
        processes_personal_data=False,
        lawful_basis_valid=False,
        purpose_documented=False,
        reason=reason,
    )
