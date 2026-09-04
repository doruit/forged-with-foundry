from datetime import UTC, datetime

from src.pri_pre_002.models import GateAction, ProjectRecord
from src.pri_pre_002.policy import evaluate_lawful_basis_gate

NOW = datetime(2026, 9, 4, tzinfo=UTC)


def record(
    *,
    environment: str = "production",
    processes_personal_data: bool = True,
    lawful_basis_raw: str = "",
    purpose_id: str = "",
):
    return ProjectRecord(
        project_id="synthetic-project",
        environment=environment,
        processes_personal_data=processes_personal_data,
        lawful_basis_raw=lawful_basis_raw,
        purpose_id=purpose_id,
        etag='"etag-1"',
    )


def test_non_personal_data_project_is_allowed():
    decision = evaluate_lawful_basis_gate(record(processes_personal_data=False), NOW)
    assert decision.action is GateAction.ALLOWED
    assert decision.processes_personal_data is False


def test_non_production_environment_is_always_allowed():
    decision = evaluate_lawful_basis_gate(
        record(environment="staging", lawful_basis_raw=""), NOW
    )
    assert decision.action is GateAction.ALLOWED


def test_missing_lawful_basis_is_flagged():
    decision = evaluate_lawful_basis_gate(
        record(lawful_basis_raw="", purpose_id="PURPOSE-2026-001"), NOW
    )
    assert decision.action is GateAction.FLAGGED
    assert decision.lawful_basis_valid is False


def test_unrecognized_lawful_basis_is_flagged_unknown():
    decision = evaluate_lawful_basis_gate(
        record(lawful_basis_raw="business_need", purpose_id="PURPOSE-2026-001"), NOW
    )
    assert decision.action is GateAction.FLAGGED_UNKNOWN


def test_valid_basis_without_purpose_is_flagged():
    decision = evaluate_lawful_basis_gate(
        record(lawful_basis_raw="contract", purpose_id=""), NOW
    )
    assert decision.action is GateAction.FLAGGED
    assert decision.lawful_basis_valid is True
    assert decision.purpose_documented is False


def test_valid_basis_and_purpose_is_compliant():
    decision = evaluate_lawful_basis_gate(
        record(lawful_basis_raw="contract", purpose_id="PURPOSE-2026-009"), NOW
    )
    assert decision.action is GateAction.COMPLIANT
    assert decision.lawful_basis_valid is True
    assert decision.purpose_documented is True


def test_naive_datetime_is_rejected():
    try:
        evaluate_lawful_basis_gate(record(), datetime(2026, 9, 4))
    except ValueError:
        return
    raise AssertionError("expected ValueError for naive evaluated_at")


def test_safe_dict_contains_no_raw_basis_or_purpose_string():
    decision = evaluate_lawful_basis_gate(
        record(lawful_basis_raw="contract", purpose_id="PURPOSE-2026-009"), NOW
    )
    safe = decision.safe_dict()
    assert "lawful_basis_raw" not in safe
    assert "purpose_id" not in safe
    assert safe["lawful_basis_valid"] is True
