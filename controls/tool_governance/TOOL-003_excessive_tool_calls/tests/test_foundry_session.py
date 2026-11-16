"""FoundryAgentSession behaviour against a fake Responses client (no network)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from src.tool_003.agent import FoundryAgentSession
from src.tool_003.runner import SCENARIOS, run_scenario


class FakeResponses:
    def __init__(self, rounds):
        self.rounds = list(rounds)
        self.created = []
        self.deleted = []

    def create(self, **kwargs):
        self.created.append(kwargs)
        calls = self.rounds.pop(0) if self.rounds else []
        index = len(self.created)
        output = [
            SimpleNamespace(type="function_call", name=name, call_id=f"c{index}{n}", arguments=arguments)
            for n, (name, arguments) in enumerate(calls)
        ]
        return SimpleNamespace(id=f"resp_{index}", output=output, output_text="done")

    def delete(self, response_id):
        self.deleted.append(response_id)


def test_session_counts_responses_and_deletes_stored_responses():
    responses = FakeResponses([[("lookup_order", '{"order_id": "ORD-1001"}')], []])
    session = FoundryAgentSession(SimpleNamespace(responses=responses), model="gpt-5", agent_version="1")

    evidence = asyncio.run(run_scenario(SCENARIOS["healthy"], session))

    assert evidence["foundry"] == {
        "agent_name": "tool-003-support-refunds",
        "agent_version": "1",
        "model_responses": 2,
        "stored_responses_deleted": 2,
        "stored_responses_delete_failed": 0,
    }
    assert responses.deleted == ["resp_1", "resp_2"]
    follow_up = responses.created[1]
    assert follow_up["previous_response_id"] == "resp_1"
    assert follow_up["input"][0]["type"] == "function_call_output"
    assert follow_up["extra_body"]["agent_reference"]["name"] == "tool-003-support-refunds"


def test_denied_run_sends_no_tool_output_back_to_the_model():
    lookups = [("lookup_order", f'{{"order_id": "ORD-100{i}"}}') for i in range(1, 7)]
    responses = FakeResponses([lookups])
    session = FoundryAgentSession(SimpleNamespace(responses=responses), model="gpt-5", agent_version="1")

    evidence = asyncio.run(run_scenario(SCENARIOS["over-budget"], session))

    assert evidence["outcome"] == "handed_off"
    assert len(responses.created) == 1
    assert responses.deleted == ["resp_1"]


def test_failed_response_delete_is_counted_not_raised():
    class FailingDelete(FakeResponses):
        def delete(self, response_id):
            raise ConnectionError("synthetic")

    responses = FailingDelete([[("lookup_order", '{"order_id": "ORD-1001"}')], []])
    session = FoundryAgentSession(SimpleNamespace(responses=responses), model="gpt-5", agent_version="1")

    evidence = asyncio.run(run_scenario(SCENARIOS["healthy"], session))

    assert evidence["outcome"] == "completed"
    assert evidence["foundry"]["stored_responses_delete_failed"] == 2
