"""Unit tests for CR-001's OPTIONAL, shared ACS pre_tool_call/post_tool_call gate."""

import asyncio

import pytest
from agent_control_specification import AgentControlBlocked

from src.cr001_interop.acs_gate import PiiToolPolicyDispatcher, get_pii_tool_control


def _post_tool_call_invocation(target: dict) -> dict:
    return {"input": {"intervention_point": "post_tool_call", "policy_target": {"value": target}}}


def test_dispatcher_allows_pre_tool_call_admission() -> None:
    dispatcher = PiiToolPolicyDispatcher()

    verdict = dispatcher.evaluate(
        {"input": {"intervention_point": "pre_tool_call", "policy_target": {"value": {"text": "hi"}}}}
    )

    assert verdict["decision"] == "allow"


def test_dispatcher_maps_allow_tool_result_to_acs_allow() -> None:
    dispatcher = PiiToolPolicyDispatcher()

    verdict = dispatcher.evaluate(
        _post_tool_call_invocation({"action": "allow", "pii_count": 0, "categories": []})
    )

    assert verdict["decision"] == "allow"


def test_dispatcher_maps_redact_and_escalate_tool_result_to_acs_warn() -> None:
    dispatcher = PiiToolPolicyDispatcher()

    verdict = dispatcher.evaluate(
        _post_tool_call_invocation(
            {"action": "redact_and_escalate", "pii_count": 2, "categories": ["Email"]}
        )
    )

    assert verdict["decision"] == "warn"
    assert "Email" in verdict["message"]


def test_dispatcher_maps_block_tool_result_to_acs_deny() -> None:
    dispatcher = PiiToolPolicyDispatcher()

    verdict = dispatcher.evaluate(
        _post_tool_call_invocation({"action": "block", "pii_count": 0, "categories": []})
    )

    assert verdict["decision"] == "deny"


def test_dispatcher_denies_invalid_tool_result_action() -> None:
    dispatcher = PiiToolPolicyDispatcher()

    verdict = dispatcher.evaluate(_post_tool_call_invocation({"action": "not_a_real_action"}))

    assert verdict["decision"] == "deny"


def test_run_tool_allows_when_execute_reports_allow() -> None:
    control = get_pii_tool_control()

    async def execute(args: dict) -> dict:
        return {"action": "allow", "pii_count": 0, "categories": []}

    result = asyncio.run(
        control.run_tool("redact_text", {"text": "hi"}, execute, approval_resolver=None)
    )

    assert result.value == {"action": "allow", "pii_count": 0, "categories": []}


def test_run_tool_passes_redact_and_escalate_through() -> None:
    control = get_pii_tool_control()

    async def execute(args: dict) -> dict:
        return {"action": "redact_and_escalate", "pii_count": 1, "categories": ["Email"]}

    result = asyncio.run(
        control.run_tool("redact_text", {"text": "hi"}, execute, approval_resolver=None)
    )

    assert result.value["action"] == "redact_and_escalate"


def test_run_tool_fails_closed_when_execute_reports_block() -> None:
    control = get_pii_tool_control()

    async def execute(args: dict) -> dict:
        return {"action": "block", "pii_count": 0, "categories": []}

    with pytest.raises(AgentControlBlocked):
        asyncio.run(
            control.run_tool("redact_text", {"text": "hi"}, execute, approval_resolver=None)
        )
