"""Decision tests for the TOOL-003 ACS budget policy, evaluated through real ACS."""

from __future__ import annotations

import asyncio

import pytest
from agent_control_specification import InterventionPoint

from src.tool_003.policy import get_control

RUN_ID = "run-1"


def _metadata(**overrides):
    metadata = {
        "control_id": "TOOL-003",
        "run_id": RUN_ID,
        "task_type": "single_refund",
        "budget": 2,
        "contract_status": "valid",
    }
    metadata.update(overrides)
    return metadata


def _entry(seq, decision="allow", run_id=RUN_ID):
    return {"seq": seq, "run_id": run_id, "point": "pre_tool_call", "decision": decision, "tool_name": "lookup_order"}


def _evaluate(point, snapshot):
    result = asyncio.run(get_control().evaluate_intervention_point(point, snapshot))
    return result.verdict.decision.value, result.verdict.reason


def _pre_tool(metadata, journal):
    snapshot = {
        "metadata": metadata,
        "tool_call": {"name": "lookup_order", "args": {"order_id": "ORD-1001"}},
    }
    if journal is not None:
        snapshot["prior_decisions"] = journal
    return _evaluate(InterventionPoint.PRE_TOOL_CALL, snapshot)


def test_startup_allows_declared_budget():
    assert _evaluate(InterventionPoint.AGENT_STARTUP, {"metadata": _metadata()}) == ("allow", "tool_003_budget_declared")


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"budget": None}, "tool_003_budget_undeclared"),
        ({"budget": 0}, "tool_003_budget_invalid"),
        ({"budget": -1}, "tool_003_budget_invalid"),
        ({"budget": 2.0}, "tool_003_budget_invalid"),
        ({"budget": "2"}, "tool_003_budget_invalid"),
        ({"budget": True}, "tool_003_budget_invalid"),
        ({"task_type": ""}, "tool_003_task_type_missing"),
        ({"contract_status": "invalid"}, "tool_003_contract_invalid"),
        ({"contract_status": "unreadable"}, "tool_003_contract_invalid"),
        ({"run_id": ""}, "tool_003_run_id_missing"),
    ],
)
def test_startup_denies_missing_or_invalid_declaration(overrides, reason):
    assert _evaluate(InterventionPoint.AGENT_STARTUP, {"metadata": _metadata(**overrides)}) == ("deny", reason)


def test_startup_without_metadata_fails_closed_in_acs():
    decision, reason = _evaluate(InterventionPoint.AGENT_STARTUP, {})
    assert decision == "deny"
    assert reason == "runtime_error:path_missing"


def test_budget_boundary_admits_b_calls_and_denies_call_b_plus_one():
    assert _pre_tool(_metadata(), []) == ("allow", "tool_003_within_budget")
    assert _pre_tool(_metadata(), [_entry(1)]) == ("allow", "tool_003_within_budget")
    assert _pre_tool(_metadata(), [_entry(1), _entry(2)]) == ("deny", "tool_003_budget_exceeded")


def test_denied_calls_do_not_consume_budget():
    assert _pre_tool(_metadata(), [_entry(1), _entry(2, "deny")]) == ("allow", "tool_003_within_budget")


@pytest.mark.parametrize(
    ("journal", "reason"),
    [
        (None, "tool_003_journal_missing"),
        ({"seq": 1}, "tool_003_journal_missing"),
        ([_entry(2)], "tool_003_journal_out_of_order"),
        ([_entry(1), _entry(1)], "tool_003_journal_out_of_order"),
        ([_entry(1, run_id="other-run")], "tool_003_journal_foreign_run"),
        ([_entry(1, decision="escalate")], "tool_003_journal_malformed"),
        (["not-an-entry"], "tool_003_journal_malformed"),
    ],
)
def test_detectable_journal_defects_fail_closed(journal, reason):
    assert _pre_tool(_metadata(), journal) == ("deny", reason)


def test_pre_tool_call_rechecks_the_declaration():
    assert _pre_tool(_metadata(budget=None), []) == ("deny", "tool_003_budget_undeclared")


EXTENSION = {"max_extra": 2, "ttl_seconds": 300}


def _future(seconds=300):
    from datetime import UTC, datetime, timedelta

    return (datetime.now(UTC) + timedelta(seconds=seconds)).isoformat()


def _grant(**overrides):
    grant = {"run_id": RUN_ID, "extra": 2, "expires_at": _future()}
    grant.update(overrides)
    return grant


FULL = [_entry(1), _entry(2)]


def test_budget_reached_escalates_only_when_an_extension_is_declared():
    assert _pre_tool(_metadata(), FULL) == ("deny", "tool_003_budget_exceeded")
    assert _pre_tool(_metadata(extension=EXTENSION), FULL) == ("escalate", "tool_003_budget_extension_required")


def test_declined_or_unanswered_request_is_never_asked_again_in_the_run():
    metadata = _metadata(extension=EXTENSION, extension_requested=True)
    assert _pre_tool(metadata, FULL) == ("deny", "tool_003_extension_not_approved")


def test_approved_extension_admits_exactly_the_extra_calls():
    metadata = _metadata(extension=EXTENSION, extension_requested=True, extension_grant=_grant())
    assert _pre_tool(metadata, FULL) == ("allow", "tool_003_within_approved_extension")
    assert _pre_tool(metadata, FULL + [_entry(3)]) == ("allow", "tool_003_within_approved_extension")
    assert _pre_tool(metadata, FULL + [_entry(3), _entry(4)]) == ("deny", "tool_003_extension_exhausted")


@pytest.mark.parametrize(
    ("grant", "reason"),
    [
        (_grant(run_id="another-run"), "tool_003_extension_invalid"),
        (_grant(extra=5), "tool_003_extension_invalid"),
        (_grant(extra="2"), "tool_003_extension_invalid"),
        (_grant(expires_at="not-a-date"), "tool_003_extension_invalid"),
        (_grant(expires_at=_future(-1)), "tool_003_extension_expired"),
    ],
    ids=["foreign-run", "more-than-declared", "string-extra", "bad-expiry", "expired"],
)
def test_grants_that_do_not_match_this_run_and_declaration_fail_closed(grant, reason):
    metadata = _metadata(extension=EXTENSION, extension_requested=True, extension_grant=grant)
    assert _pre_tool(metadata, FULL) == ("deny", reason)


def test_malformed_extension_declaration_fails_closed():
    assert _pre_tool(_metadata(extension={"max_extra": 0, "ttl_seconds": 300}), FULL) == ("deny", "tool_003_extension_invalid")
