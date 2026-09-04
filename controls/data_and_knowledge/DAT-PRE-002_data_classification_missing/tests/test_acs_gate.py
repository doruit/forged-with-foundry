"""Unit tests for the DAT-PRE-002 ACS enforcement boundary (no live Graph call)."""

import asyncio

from agent_control_specification import AgentControlBlocked

from src.dat_pre_002.acs_gate import (
    GuardedClassifyPolicyDispatcher,
    approved_by_ui_click,
    get_control,
)


def test_policy_dispatcher_always_escalates() -> None:
    dispatcher = GuardedClassifyPolicyDispatcher()

    verdict = dispatcher.evaluate({"input": {"policy_target": {"value": {"item_id": "i1"}}}})

    assert verdict["decision"] == "escalate"


def test_approved_click_allows_the_guarded_classify() -> None:
    control = get_control()

    async def execute(args: dict[str, str]) -> dict[str, object]:
        return {"location": "https://example.com/op/1", "args": args}

    async def run() -> object:
        result = await control.run_tool(
            "classify_file",
            {"item_id": "i1", "required_label_id": "l1"},
            execute,
            approval_resolver=approved_by_ui_click,
        )
        return result.value

    value = asyncio.run(run())

    assert value["location"] == "https://example.com/op/1"


def test_without_a_resolver_the_guarded_classify_fails_closed() -> None:
    control = get_control()

    async def execute(_args: dict[str, str]) -> dict[str, object]:
        raise AssertionError("execute must not run without an approval resolver")

    async def run() -> None:
        await control.run_tool(
            "classify_file",
            {"item_id": "i1", "required_label_id": "l1"},
            execute,
        )

    try:
        asyncio.run(run())
        raised = False
    except AgentControlBlocked:
        raised = True

    assert raised is True
