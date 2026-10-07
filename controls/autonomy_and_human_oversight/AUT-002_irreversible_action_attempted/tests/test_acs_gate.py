"""Focused ACS enforcement tests for AUT-002."""

import asyncio
from datetime import UTC, datetime, timedelta

from agent_control_specification import AgentControlBlocked

from src.aut_002.acs_gate import (
    ApprovalTicket,
    IrreversibleActionPolicyDispatcher,
    get_control,
    resolver_for,
)


def test_policy_dispatcher_always_escalates() -> None:
    verdict = IrreversibleActionPolicyDispatcher().evaluate({})

    assert verdict["decision"] == "escalate"


def test_missing_approval_fails_closed_before_execution() -> None:
    async def run() -> None:
        async def execute(_args: dict[str, str]) -> None:
            raise AssertionError("execute must not run without approval")

        await get_control().run_tool(
            "permanently_delete_demo_record",
            {"record_id": "synthetic-record-001"},
            execute,
        )

    try:
        asyncio.run(run())
    except AgentControlBlocked:
        return
    raise AssertionError("missing approval was not blocked")


def test_current_approval_allows_exact_action() -> None:
    async def run() -> object:
        ticket = ApprovalTicket(approved=True, issued_at=datetime.now(UTC))

        async def execute(args: dict[str, str]) -> dict[str, object]:
            return {"executed": True, "record_id": args["record_id"], "verified": True}

        result = await get_control().run_tool(
            "permanently_delete_demo_record",
            {"record_id": "synthetic-record-001"},
            execute,
            approval_resolver=resolver_for(ticket),
        )
        return result.value

    assert asyncio.run(run()) == {
        "executed": True,
        "record_id": "synthetic-record-001",
        "verified": True,
    }


def test_expired_approval_fails_closed() -> None:
    async def run() -> None:
        ticket = ApprovalTicket(
            approved=True,
            issued_at=datetime.now(UTC) - timedelta(minutes=10),
        )

        async def execute(_args: dict[str, str]) -> None:
            raise AssertionError("execute must not run with expired approval")

        await get_control().run_tool(
            "permanently_delete_demo_record",
            {"record_id": "synthetic-record-001"},
            execute,
            approval_resolver=resolver_for(ticket),
        )

    try:
        asyncio.run(run())
    except AgentControlBlocked:
        return
    raise AssertionError("expired approval was not blocked")


def test_approval_cannot_be_replayed_for_a_changed_action() -> None:
    async def run() -> None:
        ticket = ApprovalTicket(approved=True, issued_at=datetime.now(UTC))

        async def execute(_args: dict[str, str]) -> dict[str, object]:
            return {"executed": True, "verified": True}

        await get_control().run_tool(
            "permanently_delete_demo_record",
            {"record_id": "synthetic-record-001"},
            execute,
            approval_resolver=resolver_for(ticket),
        )
        await get_control().run_tool(
            "permanently_delete_demo_record",
            {"record_id": "synthetic-record-002"},
            execute,
            approval_resolver=resolver_for(ticket),
        )

    try:
        asyncio.run(run())
    except AgentControlBlocked:
        return
    raise AssertionError("approval was replayed for a changed action")


def test_prebound_approval_rejects_another_action() -> None:
    async def run() -> None:
        async def execute(_args: dict[str, str]) -> None:
            raise AssertionError("mismatched approval must not execute")

        control = get_control()
        try:
            await control.run_tool(
                "permanently_delete_demo_record",
                {"record_id": "synthetic-record-001"},
                execute,
                tool_call_id="call-original",
            )
        except AgentControlBlocked as blocked:
            identity = blocked.result.action_identity
        else:
            raise AssertionError("initial request was not blocked")
        ticket = ApprovalTicket(
            approved=True,
            issued_at=datetime.now(UTC),
            expected_action_identity=identity,
        )
        try:
            await control.run_tool(
                "permanently_delete_demo_record",
                {"record_id": "synthetic-record-002"},
                execute,
                tool_call_id="call-changed",
                approval_resolver=resolver_for(ticket),
            )
        except AgentControlBlocked:
            return
        raise AssertionError("changed action was allowed")

    asyncio.run(run())


def test_ticket_is_consumed_before_execution_finishes() -> None:
    async def run() -> None:
        executions = 0
        entered = asyncio.Event()
        release = asyncio.Event()
        ticket = ApprovalTicket(approved=True, issued_at=datetime.now(UTC))

        async def execute(_args: dict[str, str]) -> dict[str, bool]:
            nonlocal executions
            executions += 1
            entered.set()
            await release.wait()
            return {"verified": True}

        async def invoke() -> object:
            return await get_control().run_tool(
                "permanently_delete_demo_record",
                {"record_id": "synthetic-record-001"},
                execute,
                approval_resolver=resolver_for(ticket),
            )

        first = asyncio.create_task(invoke())
        await entered.wait()
        try:
            await invoke()
        except AgentControlBlocked:
            pass
        else:
            raise AssertionError("concurrent replay was allowed")
        finally:
            release.set()
            await first
        assert executions == 1

    asyncio.run(run())