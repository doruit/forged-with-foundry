"""Pure, deterministic PRI-PRE-001 DPIA-required-but-missing gate evaluation."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from .models import DpiaStatus, GateAction, GateDecision, ProjectRecord, RiskFactor

# Illustrative threshold only; not a legal determination. See EDPB/WP29 and
# ICO DPIA-screening guidance — real organizations must use DPO-approved criteria.
RISK_THRESHOLD = 2


def _decision_id(record: ProjectRecord, evaluated_at: datetime) -> str:
    material = f"{record.project_id}|{record.etag}|{evaluated_at.isoformat()}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def compute_risk_score(risk_factors: tuple[RiskFactor, ...]) -> int:
    return len(set(risk_factors))


def _evidence_complete(record: ProjectRecord) -> bool:
    return bool(
        record.dpia_status is DpiaStatus.COMPLETED
        and record.dpia_approver.strip()
        and record.dpia_date is not None
        and record.dpia_report_id.strip()
    )


def evaluate_dpia_gate(record: ProjectRecord, evaluated_at: datetime) -> GateDecision:
    """Evaluate one project record without model reasoning or business content access."""
    if evaluated_at.tzinfo is None:
        raise ValueError("evaluated_at must be timezone-aware")
    evaluated_at = evaluated_at.astimezone(UTC)
    decision_id = _decision_id(record, evaluated_at)

    if record.risk_factors is None:
        return GateDecision(
            decision_id=decision_id,
            control_id="PRI-PRE-001",
            action=GateAction.BLOCKED_UNKNOWN,
            project_id=record.project_id,
            etag=record.etag,
            risk_factor_count=None,
            dpia_required=False,
            evidence_complete=_evidence_complete(record),
            reason="Risk factors are missing or unrecognized; the gate cannot be evaluated.",
        )

    risk_score = compute_risk_score(record.risk_factors)
    dpia_required = risk_score >= RISK_THRESHOLD
    evidence_complete = _evidence_complete(record)

    if not dpia_required:
        return GateDecision(
            decision_id=decision_id,
            control_id="PRI-PRE-001",
            action=GateAction.ALLOWED,
            project_id=record.project_id,
            etag=record.etag,
            risk_factor_count=risk_score,
            dpia_required=False,
            evidence_complete=evidence_complete,
            reason=f"Risk score {risk_score} is below the DPIA threshold; go-live is allowed.",
        )

    if not evidence_complete:
        return GateDecision(
            decision_id=decision_id,
            control_id="PRI-PRE-001",
            action=GateAction.BLOCKED,
            project_id=record.project_id,
            etag=record.etag,
            risk_factor_count=risk_score,
            dpia_required=True,
            evidence_complete=False,
            reason=(
                f"Risk score {risk_score} requires a completed DPIA, but the status, "
                "approver, date, or report id is missing; go-live is blocked."
            ),
        )

    return GateDecision(
        decision_id=decision_id,
        control_id="PRI-PRE-001",
        action=GateAction.ALLOWED,
        project_id=record.project_id,
        etag=record.etag,
        risk_factor_count=risk_score,
        dpia_required=True,
        evidence_complete=True,
        reason=f"Risk score {risk_score} requires a DPIA, and complete evidence is on file.",
    )


def fail_closed(project_id: str, reason: str) -> GateDecision:
    return GateDecision(
        decision_id=hashlib.sha256(f"{project_id}|{reason}".encode()).hexdigest()[:16],
        control_id="PRI-PRE-001",
        action=GateAction.BLOCKED_UNKNOWN,
        project_id=project_id,
        etag="",
        risk_factor_count=None,
        dpia_required=False,
        evidence_complete=False,
        reason=reason,
    )
