"""Unit tests for the PRI-004 ACS enforcement boundary (no live Monitor call)."""

import asyncio

from agent_control_specification import AgentControlBlocked

from src.pri_004.acs_gate import (
    GuardedActionPolicyDispatcher,
    approved_by_ui_click,
    get_control,
)


def test_policy_dispatcher_escalates_purge() -> None:
    dispatcher = GuardedActionPolicyDispatcher()

    verdict = dispatcher.evaluate(
        {"input": {"tool_call": {"name": "submit_data_purge"}, "policy_target": {"value": {}}}}
    )

    assert verdict["decision"] == "escalate"
    assert "submit_data_purge" in verdict["reason"]


def test_policy_dispatcher_escalates_field_policy() -> None:
    dispatcher = GuardedActionPolicyDispatcher()

    verdict = dispatcher.evaluate(
        {"input": {"tool_call": {"name": "apply_field_policy"}, "policy_target": {"value": {}}}}
    )

    assert verdict["decision"] == "escalate"
    assert "apply_field_policy" in verdict["reason"]


def test_approved_click_allows_the_guarded_purge() -> None:
    control = get_control()

    async def execute(args: dict[str, str]) -> dict[str, object]:
        return {"operation_id": "op-1", "args": args}

    async def run() -> object:
        result = await control.run_tool(
            "submit_data_purge",
            {"record_id": "r1", "message_hash": "abc"},
            execute,
            approval_resolver=approved_by_ui_click,
        )
        return result.value

    value = asyncio.run(run())

    assert value["operation_id"] == "op-1"


def test_without_a_resolver_the_guarded_action_fails_closed() -> None:
    control = get_control()

    async def execute(_args: dict[str, str]) -> dict[str, object]:
        raise AssertionError("execute must not run without an approval resolver")

    async def run() -> None:
        await control.run_tool(
            "apply_field_policy",
            {"field_name": "Message"},
            execute,
        )

    try:
        asyncio.run(run())
        raised = False
    except AgentControlBlocked:
        raised = True

    assert raised is True
