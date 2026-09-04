"""Unit tests for the PRI-002 ACS enforcement boundary (no live Blob call)."""

import asyncio

from agent_control_specification import AgentControlBlocked

from src.pri_002.acs_gate import GuardedDeletePolicyDispatcher, get_control, approved_by_ui_click


def test_policy_dispatcher_always_escalates() -> None:
    dispatcher = GuardedDeletePolicyDispatcher()

    verdict = dispatcher.evaluate({"input": {"policy_target": {"value": {"blob_name": "records/a"}}}})

    assert verdict["decision"] == "escalate"


def test_approved_click_allows_the_guarded_delete() -> None:
    control = get_control()

    async def execute(args: dict[str, str]) -> dict[str, object]:
        return {"blocked": False, "verified_absent": True, "args": args}

    async def run() -> object:
        result = await control.run_tool(
            "delete_expired_blob",
            {"blob_name": "records/a", "etag": "0x1"},
            execute,
            approval_resolver=approved_by_ui_click,
        )
        return result.value

    value = asyncio.run(run())

    assert value["verified_absent"] is True


def test_without_a_resolver_the_guarded_delete_fails_closed() -> None:
    control = get_control()

    async def execute(_args: dict[str, str]) -> dict[str, object]:
        raise AssertionError("execute must not run without an approval resolver")

    async def run() -> None:
        await control.run_tool(
            "delete_expired_blob",
            {"blob_name": "records/a", "etag": "0x1"},
            execute,
        )

    try:
        asyncio.run(run())
        raised = False
    except AgentControlBlocked:
        raised = True

    assert raised is True
