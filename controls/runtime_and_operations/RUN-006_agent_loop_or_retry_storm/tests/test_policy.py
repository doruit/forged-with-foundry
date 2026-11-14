"""Decision tests for the RUN-006 loop policy, evaluated through real ACS."""

from __future__ import annotations

import asyncio

import pytest
from agent_control_specification import InterventionPoint

from src.run_006.fingerprint import fingerprint
from src.run_006.policy import attempts_without_progress, get_control

RUN_ID = "run-1"
REFUND = fingerprint("issue_refund", {"order_id": "ORD-1003"})
LOOKUP = fingerprint("lookup_order", {"order_id": "ORD-1003"})


def _metadata(**overrides):
    metadata = {"control_id": "RUN-006", "run_id": RUN_ID, "threshold": 3, "contract_status": "valid"}
    metadata.update(overrides)
    return metadata


def _journal(*specs):
    entries = []
    for seq, (kind, action, extra) in enumerate(specs, start=1):
        entries.append({"seq": seq, "run_id": RUN_ID, "kind": kind, "tool_name": "x", "fingerprint": action, **extra})
    return entries


def admission(action=REFUND):
    return ("admission", action, {})


def outcome(verified, action=REFUND):
    return ("outcome", action, {"progress": verified})


def loop_denial(action=REFUND):
    return ("denial", action, {"reason": "run_006_loop_detected"})


def _evaluate(point, snapshot):
    result = asyncio.run(get_control().evaluate_intervention_point(point, snapshot))
    return result.verdict.decision.value, result.verdict.reason


def _refund_call(journal, metadata=None, args=None):
    return _evaluate(
        InterventionPoint.PRE_TOOL_CALL,
        {
            "metadata": metadata or _metadata(),
            "prior_decisions": journal,
            "tool_call": {"name": "issue_refund", "args": args or {"order_id": "ORD-1003"}},
        },
    )


def _model_call(journal):
    return _evaluate(
        InterventionPoint.PRE_MODEL_CALL,
        {"metadata": _metadata(), "prior_decisions": journal, "model_request": {"model": "m"}},
    )


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"threshold": None}, "run_006_threshold_undeclared"),
        ({"threshold": 1}, "run_006_threshold_invalid"),
        ({"threshold": 0}, "run_006_threshold_invalid"),
        ({"threshold": -2}, "run_006_threshold_invalid"),
        ({"threshold": 3.0}, "run_006_threshold_invalid"),
        ({"threshold": "3"}, "run_006_threshold_invalid"),
        ({"contract_status": "invalid"}, "run_006_contract_invalid"),
        ({"run_id": ""}, "run_006_run_id_missing"),
    ],
)
def test_startup_denies_missing_or_invalid_threshold(overrides, reason):
    assert _evaluate(InterventionPoint.AGENT_STARTUP, {"metadata": _metadata(**overrides)}) == ("deny", reason)


def test_startup_allows_valid_threshold():
    assert _evaluate(InterventionPoint.AGENT_STARTUP, {"metadata": _metadata()})[0] == "allow"


def test_counting_boundary_attempts_one_and_two_admitted_three_denied():
    assert _refund_call([]) == ("allow", "run_006_no_loop")
    assert _refund_call(_journal(admission(), outcome(False))) == ("allow", "run_006_no_loop")
    assert _refund_call(_journal(admission(), outcome(False), admission(), outcome(False))) == (
        "deny",
        "run_006_loop_detected",
    )


def test_success_on_a_different_tool_does_not_reset_the_count():
    journal = _journal(
        admission(), outcome(False), admission(LOOKUP), outcome(True, LOOKUP), admission(), outcome(False)
    )
    assert _refund_call(journal) == ("deny", "run_006_loop_detected")


def test_verified_progress_on_the_same_action_resets_the_count():
    journal = _journal(admission(), outcome(False), admission(), outcome(True))
    assert _refund_call(journal) == ("allow", "run_006_no_loop")


def test_admission_without_an_outcome_counts_as_no_progress():
    assert _refund_call(_journal(admission(), admission())) == ("deny", "run_006_loop_detected")


def test_different_arguments_are_a_different_action():
    journal = _journal(admission(), outcome(False), admission(), outcome(False))
    assert _refund_call(journal, args={"order_id": "ORD-1001"}) == ("allow", "run_006_no_loop")


def test_argument_key_order_does_not_change_the_fingerprint():
    assert fingerprint("t", {"a": 1, "b": 2}) == fingerprint("t", {"b": 2, "a": 1})


def test_after_a_loop_stop_every_model_and_tool_call_is_denied():
    journal = _journal(admission(), outcome(False), admission(), outcome(False), loop_denial())
    assert _model_call(journal) == ("deny", "run_006_run_stopped")
    assert _evaluate(
        InterventionPoint.PRE_TOOL_CALL,
        {
            "metadata": _metadata(),
            "prior_decisions": journal,
            "tool_call": {"name": "lookup_order", "args": {"order_id": "ORD-1001"}},
        },
    ) == ("deny", "run_006_run_stopped")


def test_model_calls_are_allowed_while_the_run_is_active():
    assert _model_call(_journal(admission(), outcome(False))) == ("allow", "run_006_run_active")


@pytest.mark.parametrize(
    ("journal", "reason"),
    [
        (None, "run_006_journal_missing"),
        ([{"seq": 2, "run_id": RUN_ID, "kind": "admission", "fingerprint": REFUND}], "run_006_journal_out_of_order"),
        ([{"seq": 1, "run_id": "other", "kind": "admission", "fingerprint": REFUND}], "run_006_journal_foreign_run"),
        ([{"seq": 1, "run_id": RUN_ID, "kind": "guess", "fingerprint": REFUND}], "run_006_journal_malformed"),
        ([{"seq": 1, "run_id": RUN_ID, "kind": "outcome", "fingerprint": REFUND}], "run_006_journal_malformed"),
    ],
)
def test_detectable_journal_defects_fail_closed(journal, reason):
    snapshot = {"metadata": _metadata(), "tool_call": {"name": "issue_refund", "args": {"order_id": "ORD-1003"}}}
    if journal is not None:
        snapshot["prior_decisions"] = journal
    assert _evaluate(InterventionPoint.PRE_TOOL_CALL, snapshot) == ("deny", reason)


def test_attempt_counter_helper_matches_policy_semantics():
    journal = _journal(admission(), outcome(False), admission(LOOKUP), outcome(True, LOOKUP), admission())
    assert attempts_without_progress(journal, REFUND) == 2
