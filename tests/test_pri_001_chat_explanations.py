from pri_001.chat import _banner, _processing_banner
from pri_001.models import PiiFinding, PolicyAction
from pri_001.policy import evaluate_pii_policy, fail_closed


def test_detected_and_redacted_are_explained_as_separate_stages() -> None:
    decision = evaluate_pii_policy([PiiFinding(category="Email", confidence=0.99)])

    banner = _banner(decision, "chat_input", "safe-event-reference")

    assert "`DETECTED`" in banner
    assert "`COMPLETED`" in banner
    assert "governance signal" in banner
    assert "transformed output" in banner
    assert "alex@example.com" not in banner


def test_no_detection_marks_redaction_as_not_required() -> None:
    banner = _banner(evaluate_pii_policy([]), "chat_input")

    assert "`NOT_DETECTED`" in banner
    assert "`NOT_REQUIRED`" in banner
    assert "`ALLOW`" in banner


def test_failure_explains_fail_closed_boundary() -> None:
    decision = fail_closed("PII service unavailable")

    banner = _banner(decision, "native_document")

    assert decision.action is PolicyAction.BLOCK
    assert "not safely completed" in banner
    assert "nothing was sent to Agent Framework and GPT-5" in banner


def test_processing_banner_says_no_agent_handoff_has_occurred() -> None:
    banner = _processing_banner("agent_output")

    assert "detection in progress" in banner
    assert "Nothing has been sent to GPT-5" in banner