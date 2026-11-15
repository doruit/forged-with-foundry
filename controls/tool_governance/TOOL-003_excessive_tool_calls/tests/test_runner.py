"""End-to-end runner behaviour on scripted call sequences (no cloud access)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from src.tool_003.agent import ScriptedSession, parse_function_call
from src.tool_003.approval import ScriptedApprover
from src.tool_003.runner import SCENARIOS, RunAborted, run_scenario


def _run(name: str, session=None, **kwargs):
    scenario = SCENARIOS[name]
    session = session or ScriptedSession(scenario.replay)
    return asyncio.run(run_scenario(scenario, session, **kwargs)), session


def test_healthy_run_completes_within_budget():
    evidence, _ = _run("healthy")
    assert evidence["outcome"] == "completed"
    assert evidence["admitted_calls"] == evidence["executed_calls"] == 3
    assert all(entry["reason"] == "tool_003_within_budget" for entry in evidence["decisions"])


def test_over_budget_without_an_approver_is_denied_before_execution():
    evidence, _ = _run("over-budget")
    assert evidence["outcome"] == "handed_off"
    assert evidence["approved_budget"] == 4
    assert evidence["admitted_calls"] == evidence["executed_calls"] == 4
    assert evidence["decisions"][-1] == {
        "seq": 5,
        "point": "pre_tool_call",
        "decision": "deny",
        "tool_name": "lookup_order",
        "reason": "tool_003_extension_no_approver",
    }
    assert evidence["budget_extension"]["status"] == "no_approver"


def test_declined_extension_denies_the_call_and_never_asks_twice():
    approver = ScriptedApprover(approve=False)
    evidence, _ = _run("over-budget", approver=approver)
    assert len(approver.requests) == 1
    assert evidence["outcome"] == "handed_off"
    assert evidence["executed_calls"] == 4
    assert evidence["decisions"][-1]["reason"] == "tool_003_extension_declined"
    assert evidence["governance_action"].endswith("extension_not_approved")


def test_approved_extension_admits_the_escalated_call_and_the_rest_within_the_limit():
    approver = ScriptedApprover(approve=True)
    evidence, _ = _run("over-budget", approver=approver)
    [request] = approver.requests
    assert (request["approved_budget"], request["extra_calls_requested"], request["admitted_calls"]) == (4, 3, 4)
    assert evidence["outcome"] == "completed"
    assert evidence["admitted_calls"] == evidence["executed_calls"] == 6
    assert evidence["decisions"][4]["reason"] == "tool_003_extension_approved"
    assert evidence["budget_extension"]["extra_calls_granted"] == 3
    assert evidence["governance_action"] == "over_budget_extension_approved_by_accountable_role"


def test_approved_extension_is_bounded():
    eleven = [[("lookup_order", {"order_id": f"ORD-100{index % 6 + 1}"}) for index in range(11)]]
    evidence, _ = _run("over-budget", session=ScriptedSession(eleven), approver=ScriptedApprover(approve=True))
    assert evidence["admitted_calls"] == evidence["executed_calls"] == 7
    assert evidence["decisions"][-1]["reason"] == "tool_003_extension_exhausted"


def test_failing_approval_channel_fails_closed():
    def broken(_request):
        raise OSError("approval channel unavailable")

    evidence, _ = _run("over-budget", approver=broken)
    assert evidence["outcome"] == "handed_off"
    assert evidence["executed_calls"] == 4
    assert evidence["decisions"][-1]["reason"] == "runtime_error:approval_resolver_failed"
    assert evidence["budget_extension"]["status"] == "channel_failed"


def test_undeclared_task_type_never_reaches_the_model():
    evidence, session = _run("undeclared-task")
    assert evidence["outcome"] == "not_started"
    assert evidence["agent_startup"]["reason"] == "tool_003_budget_undeclared"
    assert session.model_calls == 0
    assert evidence["executed_calls"] == 0


def test_unreadable_contract_never_reaches_the_model(tmp_path):
    evidence, session = _run("healthy", contract_path=tmp_path / "missing.yaml")
    assert evidence["agent_startup"] == {"decision": "deny", "reason": "tool_003_contract_invalid"}
    assert session.model_calls == 0


def test_admission_is_journaled_before_the_tool_runs(monkeypatch):
    from src.tool_003 import runner

    journals: list[runner.RunJournal] = []
    entries_seen_at_execution: list[int] = []

    class RecordingJournal(runner.RunJournal):
        def __init__(self, run_id):
            super().__init__(run_id)
            journals.append(self)

    original = runner.SyntheticSupportSystem.execute

    def spy(self, tool_name, args):
        entries_seen_at_execution.append(len(journals[0].snapshot()))
        return original(self, tool_name, args)

    monkeypatch.setattr(runner, "RunJournal", RecordingJournal)
    monkeypatch.setattr(runner.SyntheticSupportSystem, "execute", spy)
    _run("healthy")
    assert entries_seen_at_execution == [1, 2, 3]


def test_evidence_contains_no_tool_arguments_or_prompt(tmp_path):
    evidence, _ = _run("healthy", evidence_dir=tmp_path)
    text = next(Path(tmp_path).glob("healthy-*.json")).read_text()
    assert "ORD-1001" not in text
    assert "damaged" not in text
    assert json.loads(text)["accountable_role"] == "AI Ops Lead"


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("delete_everything", '{"order_id": "ORD-1001"}'),
        ("lookup_order", '{"order_id": "ORD-9999"}'),
        ("lookup_order", '{"order_id": "ORD-1001", "order_id": "ORD-1002"}'),
        ("lookup_order", '{"order_id": "ORD-1001", "extra": "x"}'),
    ],
)
def test_unexpected_function_calls_are_rejected(name, arguments):
    with pytest.raises(ValueError):
        parse_function_call(name, "call_1", arguments)


def test_error_after_an_executed_call_still_writes_evidence(tmp_path):
    class FailingSubmit(ScriptedSession):
        def submit(self, outputs):
            raise ConnectionError("synthetic outage with model text that must not leak")

    with pytest.raises(RunAborted) as aborted:
        _run("healthy", session=FailingSubmit(SCENARIOS["healthy"].replay), evidence_dir=tmp_path)

    evidence = aborted.value.evidence
    assert evidence["outcome"] == "aborted"
    assert evidence["error_class"] == "ConnectionError"
    assert evidence["admitted_calls"] == evidence["executed_calls"] == 1
    written = next(Path(tmp_path).glob("healthy-*.json")).read_text()
    assert "must not leak" not in written


def test_unexpected_model_output_aborts_with_evidence(tmp_path):
    class BadCall(ScriptedSession):
        def submit(self, outputs):
            raise ValueError("unknown_tool")

    with pytest.raises(RunAborted):
        _run("healthy", session=BadCall(SCENARIOS["healthy"].replay), evidence_dir=tmp_path)
    assert list(Path(tmp_path).glob("healthy-*.json"))
