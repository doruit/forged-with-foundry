"""Unit tests for the PRI-003 ACS enforcement boundary (no live Table call)."""

import asyncio
from datetime import UTC, datetime, timedelta

from agent_control_specification import AgentControlBlocked

from src.pri_003.acs_gate import (
    ApprovalTicket,
    GuardedExtensionPolicyDispatcher,
    denied_resolver,
    get_control,
    resolver_for,
)


def test_policy_dispatcher_always_escalates() -> None:
    dispatcher = GuardedExtensionPolicyDispatcher()

    verdict = dispatcher.evaluate({"input": {"policy_target": {"value": {"request_id": "r1"}}}})

    assert verdict["decision"] == "escalate"


async def _run_guarded_extension(resolver) -> object:
    control = get_control()

    async def execute(args: dict[str, str]) -> dict[str, object]:
        return {"blocked": False, "args": args}

    result = await control.run_tool(
        "extend_dsr_due_date",
        {"request_id": "r1", "etag": "0x1"},
        execute,
        approval_resolver=resolver,
    )
    return result.value


def test_approved_ticket_allows_the_guarded_extension() -> None:
    ticket = ApprovalTicket(approved=True, issued_at=datetime.now(UTC))

    value = asyncio.run(_run_guarded_extension(resolver_for(ticket)))

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


def test_missing_ticket_is_denied_not_auto_approved() -> None:
    """Approval must never be assumed just because the resolver was called."""

    async def execute(_args: dict[str, str]) -> dict[str, object]:
        raise AssertionError("execute must not run with no approval ticket")

    try:
        asyncio.run(
            get_control().run_tool(
                "extend_dsr_due_date",
                {"request_id": "r1", "etag": "0x1"},
                execute,
                approval_resolver=denied_resolver,
            )
        )
        raised = False
    except AgentControlBlocked:
        raised = True

    assert raised is True


def test_rejected_ticket_is_denied() -> None:
    ticket = ApprovalTicket(approved=False, issued_at=datetime.now(UTC))

    async def execute(_args: dict[str, str]) -> dict[str, object]:
        raise AssertionError("execute must not run for a rejected approval")

    try:
        asyncio.run(_run_guarded_extension(resolver_for(ticket)))
        raised = False
    except AgentControlBlocked:
        raised = True

    assert raised is True


def test_stale_ticket_is_denied() -> None:
    ticket = ApprovalTicket(
        approved=True,
        issued_at=datetime.now(UTC) - timedelta(minutes=30),
        ttl=timedelta(minutes=5),
    )

    async def execute(_args: dict[str, str]) -> dict[str, object]:
        raise AssertionError("execute must not run for an expired approval")

    try:
        asyncio.run(_run_guarded_extension(resolver_for(ticket)))
        raised = False
    except AgentControlBlocked:
        raised = True

    assert raised is True


def test_ticket_claim_is_single_use() -> None:
    """`run_tool` calls the resolver at both pre and post_tool_call for one
    action, so single-use is enforced by `claim()`, not the resolver itself.
    """
    ticket = ApprovalTicket(approved=True, issued_at=datetime.now(UTC))

    assert ticket.claim() is True
    assert ticket.claim() is False

