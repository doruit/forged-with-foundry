"""Runner behaviour with scripted calls and a fake Foundry client (no cloud access)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.run_006.agent import FoundryAgentSession, ScriptedSession
from src.run_006.contract import load_threshold
from src.run_006.policy import get_control
from src.run_006.runner import SCENARIOS, RunAborted, run_scenario


def _run(name, session=None, **kwargs):
    control = get_control()
    scenario = SCENARIOS[name]
    session = session or ScriptedSession(control, scenario.replay)
    return asyncio.run(run_scenario(scenario, session, control, **kwargs)), session


class FakeResponses:
    """Records every request that would leave the process."""

    def __init__(self, rounds):
        self.rounds = list(rounds)
        self.created = []
        self.deleted = []

    def create(self, **kwargs):
        self.created.append(kwargs)
        calls = self.rounds.pop(0) if self.rounds else []
        index = len(self.created)
        output = [
            SimpleNamespace(type="function_call", name=name, call_id=f"c{index}{n}", arguments=json.dumps(args))
            for n, (name, args) in enumerate(calls)
        ]
        return SimpleNamespace(id=f"resp_{index}", output=output, output_text="done")

    def delete(self, response_id):
        self.deleted.append(response_id)


def _foundry(rounds):
    responses = FakeResponses(rounds)
    session = FoundryAgentSession(
        get_control(), SimpleNamespace(responses=responses), model="gpt-5", agent_version="1"
    )
    return session, responses


def test_healthy_run_completes():
    evidence, _ = _run("healthy")
    assert evidence["outcome"] == "completed"
    assert evidence["refund_attempts_executed"] == 1


def test_retry_storm_stops_at_the_third_identical_check_and_blocks_the_next_model_call():
    evidence, session = _run("retry-storm")
    assert evidence["outcome"] == "stopped"
    assert evidence["stopped_at"] == "pre_tool_call"
    assert evidence["refund_attempts_executed"] == 2
    last = evidence["tool_journal"][-1]
    assert (last["kind"], last["tool_name"], last["reason"]) == ("denial", "lookup_order", "run_006_loop_detected")
    assert evidence["model_gate"][-1] == {
        "after_journal_seq": len(evidence["tool_journal"]),
        "decision": "deny",
        "reason": "run_006_run_stopped",
    }
    assert session.model_calls_sent == 5


@pytest.mark.parametrize(
    ("call", "executed"),
    [
        # The first refund/reply is real progress; two identical repeats follow, the third is denied.
        (("issue_refund", {"order_id": "ORD-1001"}), 3),
        (("reply_to_ticket", {"ticket_id": "TCK-2001", "summary": "Refund issued."}), 3),
        # A read never makes progress: the third identical read is denied.
        (("lookup_order", {"order_id": "ORD-1001"}), 2),
    ],
    ids=["refund-after-success", "duplicate-reply", "repeated-read"],
)
def test_repeating_an_action_that_already_succeeded_is_not_progress(call, executed):
    control = get_control()
    session = ScriptedSession(control, [[call]] * 8)
    evidence = asyncio.run(run_scenario(SCENARIOS["healthy"], session, control))
    assert evidence["outcome"] == "stopped"
    assert evidence["executed_tool_calls"] == executed
    assert evidence["tool_journal"][-1]["reason"] == "run_006_loop_detected"


def test_missing_threshold_never_reaches_the_model():
    evidence, session = _run("missing-threshold")
    assert evidence["outcome"] == "not_started"
    assert evidence["agent_startup"]["reason"] == "run_006_contract_invalid"
    assert session.model_calls_sent == 0


def test_unreadable_contract_never_reaches_the_model(tmp_path):
    evidence, session = _run("healthy", contract_path=tmp_path / "missing.yaml")
    assert evidence["outcome"] == "not_started"
    assert session.model_calls_sent == 0


def test_no_request_leaves_the_process_after_the_stop():
    session, responses = _foundry(
        [
            [("issue_refund", {"order_id": "ORD-1003"})],
            [("issue_refund", {"order_id": "ORD-1003"})],
            [("issue_refund", {"order_id": "ORD-1003"})],
            [("reply_to_ticket", {"ticket_id": "TCK-2003", "summary": "never sent"})],
        ]
    )
    evidence, _ = _run("retry-storm", session=session)
    assert evidence["outcome"] == "stopped"
    # Three model responses created; the fourth request was denied by ACS before sending.
    assert len(responses.created) == 3
    assert all("agent_control_snapshot" not in request for request in responses.created)
    assert responses.deleted == ["resp_1", "resp_2", "resp_3"]
    assert evidence["foundry"]["model_responses"] == 3


def test_parallel_retries_in_one_response_are_admitted_one_at_a_time():
    session, responses = _foundry([[("issue_refund", {"order_id": "ORD-1003"})] * 4])
    evidence, _ = _run("retry-storm", session=session)
    kinds = [(entry["kind"], entry.get("reason")) for entry in evidence["tool_journal"]]
    assert kinds == [
        ("admission", "run_006_no_loop"),
        ("outcome", None),
        ("admission", "run_006_no_loop"),
        ("outcome", None),
        ("denial", "run_006_loop_detected"),
        ("denial", "run_006_run_stopped"),
    ]
    assert evidence["refund_attempts_executed"] == 2
    assert len(responses.created) == 1


def test_error_after_an_executed_call_still_writes_evidence(tmp_path):
    class FailingSubmit(ScriptedSession):
        async def submit(self, outputs, snapshot):
            raise ConnectionError("synthetic outage text that must not leak")

    control = get_control()
    with pytest.raises(RunAborted) as aborted:
        asyncio.run(
            run_scenario(
                SCENARIOS["healthy"],
                FailingSubmit(control, SCENARIOS["healthy"].replay),
                control,
                evidence_dir=tmp_path,
            )
        )
    assert aborted.value.evidence["error_class"] == "ConnectionError"
    assert "must not leak" not in next(Path(tmp_path).glob("*.json")).read_text()


def test_evidence_contains_neither_arguments_nor_reversible_fingerprints(tmp_path):
    _run("retry-storm", evidence_dir=tmp_path)
    text = next(Path(tmp_path).glob("retry-storm-*.json")).read_text()
    assert "ORD-1003" not in text
    assert "sha256:" not in text
    actions = [entry["action"] for entry in json.loads(text)["tool_journal"]]
    assert actions[:5:2] == ["A1", "A2", "A1"]


def test_telemetry_flush_result_is_recorded():
    class FakeTelemetry:
        def flush(self):
            return "exported"

    evidence, _ = _run("retry-storm", telemetry=FakeTelemetry())
    assert evidence["notification"] == {"channel": "azure_monitor_log_alert", "acs_metrics_export": "exported"}


def test_without_a_notification_path_evidence_says_not_deployed():
    evidence, _ = _run("retry-storm")
    assert evidence["notification"] == {"channel": "not_deployed", "acs_metrics_export": "not_configured"}


def test_shipped_contract_declares_threshold_three():
    assert load_threshold().threshold == 3


def test_governance_action_never_claims_an_alert_was_sent():
    evidence, _ = _run("retry-storm")
    assert "alert" not in evidence["governance_action"]
    assert evidence["notification"]["channel"] == "not_deployed"
