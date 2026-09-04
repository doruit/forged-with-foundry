from datetime import UTC, datetime

from src.pri_pre_001.models import DpiaStatus, GateAction, ProjectRecord, RiskFactor
from src.pri_pre_001.policy import compute_risk_score, evaluate_dpia_gate

NOW = datetime(2026, 9, 4, tzinfo=UTC)


def record(
    *,
    risk_factors: tuple[RiskFactor, ...] | None = (),
    dpia_status: DpiaStatus = DpiaStatus.NOT_STARTED,
    dpia_approver: str = "",
    dpia_date=None,
    dpia_report_id: str = "",
):
    return ProjectRecord(
        project_id="synthetic-project",
        risk_factors=risk_factors,
        dpia_status=dpia_status,
        dpia_approver=dpia_approver,
        dpia_date=dpia_date,
        dpia_report_id=dpia_report_id,
        etag='"etag-1"',
    )


def test_low_risk_project_is_allowed_without_dpia():
    decision = evaluate_dpia_gate(record(risk_factors=(RiskFactor.SPECIAL_CATEGORY_DATA,)), NOW)
    assert decision.action is GateAction.ALLOWED
    assert decision.dpia_required is False


def test_high_risk_project_with_complete_evidence_is_allowed():
    decision = evaluate_dpia_gate(
        record(
            risk_factors=(RiskFactor.SPECIAL_CATEGORY_DATA, RiskFactor.AUTOMATED_DECISION_MAKING),
            dpia_status=DpiaStatus.COMPLETED,
            dpia_approver="dpo@example.com",
            dpia_date=NOW,
            dpia_report_id="DPIA-2026-001",
        ),
        NOW,
    )
    assert decision.action is GateAction.ALLOWED
    assert decision.dpia_required is True
    assert decision.evidence_complete is True


def test_high_risk_project_with_missing_dpia_is_blocked():
    decision = evaluate_dpia_gate(
        record(
            risk_factors=(RiskFactor.SPECIAL_CATEGORY_DATA, RiskFactor.AUTOMATED_DECISION_MAKING),
        ),
        NOW,
    )
    assert decision.action is GateAction.BLOCKED
    assert decision.dpia_required is True


def test_high_risk_project_with_incomplete_evidence_is_blocked():
    decision = evaluate_dpia_gate(
        record(
            risk_factors=(RiskFactor.SPECIAL_CATEGORY_DATA, RiskFactor.AUTOMATED_DECISION_MAKING),
            dpia_status=DpiaStatus.COMPLETED,
            dpia_approver="dpo@example.com",
            dpia_date=NOW,
            dpia_report_id="",  # missing report id
        ),
        NOW,
    )
    assert decision.action is GateAction.BLOCKED
    assert decision.evidence_complete is False


def test_unknown_risk_factors_fail_closed():
    decision = evaluate_dpia_gate(record(risk_factors=None), NOW)
    assert decision.action is GateAction.BLOCKED_UNKNOWN
    assert decision.risk_factor_count is None


def test_naive_datetime_is_rejected():
    try:
        evaluate_dpia_gate(record(), datetime(2026, 9, 4))
    except ValueError:
        return
    raise AssertionError("expected ValueError for naive evaluated_at")


def test_compute_risk_score_deduplicates_factors():
    score = compute_risk_score(
        (RiskFactor.SPECIAL_CATEGORY_DATA, RiskFactor.SPECIAL_CATEGORY_DATA)
    )
    assert score == 1


def test_safe_dict_excludes_approver_and_report_id():
    decision = evaluate_dpia_gate(
        record(
            risk_factors=(RiskFactor.SPECIAL_CATEGORY_DATA, RiskFactor.AUTOMATED_DECISION_MAKING),
            dpia_status=DpiaStatus.COMPLETED,
            dpia_approver="dpo@example.com",
            dpia_date=NOW,
            dpia_report_id="DPIA-2026-001",
        ),
        NOW,
    )
    safe = decision.safe_dict()
    assert "dpia_approver" not in safe
    assert "dpia_report_id" not in safe
    assert safe["risk_factor_count"] == 2
