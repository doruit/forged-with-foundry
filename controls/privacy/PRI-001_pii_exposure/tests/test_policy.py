from src.pri_001.models import PiiFinding, PolicyAction
from src.pri_001.policy import evaluate_pii_policy, fail_closed


def test_one_occurrence_redacts_and_escalates() -> None:
    decision = evaluate_pii_policy([PiiFinding(category="Email", confidence=0.99)])

    assert decision.control_id == "PRI-001"
    assert decision.action is PolicyAction.REDACT_AND_ESCALATE
    assert decision.pii_count == 1
    assert decision.categories == ("Email",)
    assert decision.escalate is True
    assert decision.accountable_role == "Privacy Officer"


def test_no_occurrence_allows() -> None:
    decision = evaluate_pii_policy([])

    assert decision.action is PolicyAction.ALLOW
    assert decision.escalate is False


def test_service_failure_blocks() -> None:
    decision = fail_closed("PII service unavailable")

    assert decision.action is PolicyAction.BLOCK
    assert decision.escalate is False
