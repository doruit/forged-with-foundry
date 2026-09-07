"""Unit tests for the PRI-004 ACS enforcement boundary (no live Monitor call)."""

import asyncio
from datetime import UTC, datetime, timedelta

from agent_control_specification import AgentControlBlocked

from src.pri_004.acs_gate import (
    ApprovalTicket,
    GuardedActionPolicyDispatcher,
    denied_resolver,
    get_control,
    resolver_for,
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


def test_approved_ticket_allows_the_guarded_purge() -> None:
    control = get_control()
    ticket = ApprovalTicket(approved=True, issued_at=datetime.now(UTC))

    async def execute(args: dict[str, str]) -> dict[str, object]:
        return {"operation_id": "op-1", "args": args}

    async def run() -> object:
        result = await control.run_tool(
            "submit_data_purge",
            {"record_id": "r1", "message_hash": "abc"},
            execute,
            approval_resolver=resolver_for(ticket),
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


def test_missing_ticket_is_denied_not_auto_approved() -> None:
    """Approval must never be assumed just because the resolver was called."""

    async def execute(_args: dict[str, str]) -> dict[str, object]:
        raise AssertionError("execute must not run with no approval ticket")

    try:
        asyncio.run(
            get_control().run_tool(
                "apply_field_policy",
                {"field_name": "Message"},
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
        asyncio.run(
            get_control().run_tool(
                "apply_field_policy",
                {"field_name": "Message"},
                execute,
                approval_resolver=resolver_for(ticket),
            )
        )
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
        asyncio.run(
            get_control().run_tool(
                "apply_field_policy",
                {"field_name": "Message"},
                execute,
                approval_resolver=resolver_for(ticket),
            )
        )
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

