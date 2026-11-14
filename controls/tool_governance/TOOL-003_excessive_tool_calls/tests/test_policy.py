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
