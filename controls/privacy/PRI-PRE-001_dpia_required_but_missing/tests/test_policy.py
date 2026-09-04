from datetime import UTC, datetime

from src.pri_pre_001.models import GateAction, ProjectRecord, RiskFactor
from src.pri_pre_001.policy import compute_risk_score, evaluate_dpia_gate

NOW = datetime(2026, 9, 4, tzinfo=UTC)


def record(
    *,
    environment: str = "production",
    risk_factors: tuple[RiskFactor, ...] | None = (),
    dpia_required_declared: bool = False,
    requestor_email: str = "",
    dpia_approver: str = "",
    dpia_case_id: str = "",
):
    return ProjectRecord(
        project_id="synthetic-project",
        environment=environment,
        risk_factors=risk_factors,
        dpia_required_declared=dpia_required_declared,
        requestor_email=requestor_email,
        dpia_approver=dpia_approver,
        dpia_case_id=dpia_case_id,
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
            requestor_email="workload-owner@example.com",
            dpia_approver="dpo@example.com",
            dpia_case_id="DPIA-2026-001",
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
            requestor_email="workload-owner@example.com",
            dpia_approver="dpo@example.com",
            dpia_case_id="",  # missing case id
        ),
        NOW,
    )
    assert decision.action is GateAction.BLOCKED
    assert decision.evidence_complete is False


def test_unknown_risk_factors_fail_closed():
    decision = evaluate_dpia_gate(record(risk_factors=None), NOW)
    assert decision.action is GateAction.BLOCKED_UNKNOWN
    assert decision.risk_factor_count is None


def test_non_production_environment_is_always_allowed():
    decision = evaluate_dpia_gate(
        record(
            environment="staging",
            risk_factors=(RiskFactor.SPECIAL_CATEGORY_DATA, RiskFactor.AUTOMATED_DECISION_MAKING),
        ),
        NOW,
    )
    assert decision.action is GateAction.ALLOWED


def test_declared_not_required_overrides_computed_risk_score():
    decision = evaluate_dpia_gate(
        record(
            risk_factors=(RiskFactor.SPECIAL_CATEGORY_DATA, RiskFactor.AUTOMATED_DECISION_MAKING),
            dpia_required_declared=True,
        ),
        NOW,
    )
    assert decision.action is GateAction.ALLOWED
    assert decision.dpia_required is True  # computed risk is still reported


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


def test_safe_dict_excludes_pii_fields():
    decision = evaluate_dpia_gate(
        record(
            risk_factors=(RiskFactor.SPECIAL_CATEGORY_DATA, RiskFactor.AUTOMATED_DECISION_MAKING),
            requestor_email="workload-owner@example.com",
            dpia_approver="dpo@example.com",
            dpia_case_id="DPIA-2026-001",
        ),
        NOW,
    )
    safe = decision.safe_dict()
    assert "requestor_email" not in safe
    assert "dpia_approver" not in safe
    assert "dpia_case_id" not in safe
    assert safe["risk_factor_count"] == 2
