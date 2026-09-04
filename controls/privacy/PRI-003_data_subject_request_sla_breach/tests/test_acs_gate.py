"""Unit tests for the PRI-003 ACS enforcement boundary (no live Table call)."""

import asyncio

from agent_control_specification import AgentControlBlocked

from src.pri_003.acs_gate import (
    GuardedExtensionPolicyDispatcher,
    approved_by_ui_click,
    get_control,
)


def test_policy_dispatcher_always_escalates() -> None:
    dispatcher = GuardedExtensionPolicyDispatcher()

    verdict = dispatcher.evaluate({"input": {"policy_target": {"value": {"request_id": "r1"}}}})

    assert verdict["decision"] == "escalate"


def test_approved_click_allows_the_guarded_extension() -> None:
    control = get_control()

    async def execute(args: dict[str, str]) -> dict[str, object]:
        return {"blocked": False, "args": args}

    async def run() -> object:
        result = await control.run_tool(
            "extend_dsr_due_date",
            {"request_id": "r1", "etag": "0x1"},
            execute,
            approval_resolver=approved_by_ui_click,
        )
        return result.value

    value = asyncio.run(run())

    assert value["blocked"] is False


def test_without_a_resolver_the_guarded_extension_fails_closed() -> None:
    control = get_control()

    async def execute(_args: dict[str, str]) -> dict[str, object]:
        raise AssertionError("execute must not run without an approval resolver")

    async def run() -> None:
        await control.run_tool(
            "extend_dsr_due_date",
            {"request_id": "r1", "etag": "0x1"},
            execute,
        )

    try:
        asyncio.run(run())
        raised = False
    except AgentControlBlocked:
        raised = True

    assert raised is True
