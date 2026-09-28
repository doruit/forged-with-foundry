"""Live Chainlit chat for the AUT-002 ACS gate."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path

import chainlit as cl
from agent_control_specification import AgentControlBlocked

from .acs_gate import ApprovalTicket, get_control, resolver_for
from .evidence import write_evidence

logger = logging.getLogger("aut_002.chat")
TOOL_NAME = "permanently_delete_demo_record"
RECORD_ID = "synthetic-record-001"
CONTROL_ROOT = Path(__file__).resolve().parents[2]


def _actions() -> list[cl.Action]:
    return [
        cl.Action(
            name="attempt_aut002",
            payload={},
            label="1. Attempt irreversible action",
            description="Let the agent attempt the protected delete without approval.",
        ),
        cl.Action(
            name="cleanup_aut002",
            payload={},
            label="Clean up demo",
            description="Remove only local AUT-002 evidence.",
        ),
    ]


def _store() -> set[str]:
    records = cl.user_session.get("aut_002_records")
    if not isinstance(records, set):
        records = {RECORD_ID}
        cl.user_session.set("aut_002_records", records)
    return records


def _evidence_dir() -> Path:
    destination = CONTROL_ROOT / "evidence"
    destination.mkdir(exist_ok=True)
    return destination


async def _delete(args: dict[str, str]) -> dict[str, object]:
    record_id = args["record_id"]
    records = _store()
    if record_id not in records:
        raise RuntimeError("synthetic record is already absent")
    records.remove(record_id)
    return {"record_id": record_id, "verified_absent": record_id not in records}


async def _run_guarded_delete(
    *, approval: ApprovalTicket | None, correlation_id: str
) -> tuple[bool, str | None, bool]:
    control = get_control()
    args = {"record_id": RECORD_ID}
    try:
        result = await control.run_tool(
            TOOL_NAME,
            args,
            _delete,
            approval_resolver=resolver_for(approval) if approval else None,
        )
    except AgentControlBlocked:
        write_evidence(
            _evidence_dir() / f"blocked-{correlation_id}.json",
            decision="escalate",
            tool_name=TOOL_NAME,
            action_identity=None,
            executed=False,
            verified=False,
            reason="approval_missing_or_invalid",
            correlation_id=correlation_id,
        )
        return False, None, False

    verified = bool(result.value["verified_absent"])
    write_evidence(
        _evidence_dir() / f"approved-{correlation_id}.json",
        decision="allow",
        tool_name=TOOL_NAME,
        action_identity=result.pre_tool_call_result.action_identity,
        executed=True,
        verified=verified,
        reason="exact_action_approved_and_verified",
        correlation_id=correlation_id,
    )
    return True, result.pre_tool_call_result.action_identity, verified


@cl.on_chat_start
async def on_chat_start() -> None:
    cl.user_session.set("aut_002_records", {RECORD_ID})
    await cl.Message(
        content=(
            "# AUT-002 Live Test\n\n"
            "This chat agent demonstrates an irreversible action. First, it attempts "
            "the action without approval. Then you can approve the exact action as the **Ops Manager**.\n\n"
            "The chat agent orchestrates the test; **ACS decides whether the tool may run**. "
            "No model is used to simulate approval."
        ),
        actions=_actions(),
    ).send()


@cl.action_callback("attempt_aut002")
async def attempt_action(_: cl.Action) -> None:
    correlation_id = str(uuid.uuid4())
    await cl.Message(
        content=(
            "### Agent attempts the action\n\n"
            f"`{TOOL_NAME}` for `{RECORD_ID}` is sent to ACS without an approval resolver."
        )
    ).send()
    allowed, _, _ = await _run_guarded_delete(
        approval=None,
        correlation_id=correlation_id,
    )
    if allowed:
        await cl.Message(content="### Unexpectedly allowed\n\nThis scenario requires investigation.").send()
        return
    await cl.Message(
        content=(
            "### Blocked by ACS\n\n"
            "The tool did not execute. The action is now ready for explicit Ops Manager approval."
        ),
        actions=[
            cl.Action(
                name="approve_aut002",
                payload={},
                label="2. Approve as Ops Manager",
                description="One-time approval for this exact action.",
            ),
            cl.Action(
                name="decline_aut002",
                payload={},
                label="Do not approve",
                description="Keep the action blocked.",
            ),
        ],
    ).send()


@cl.action_callback("approve_aut002")
async def approve_action(_: cl.Action) -> None:
    correlation_id = str(uuid.uuid4())
    approval = ApprovalTicket(approved=True, issued_at=datetime.now(UTC))
    await cl.Message(content="### Ops Manager approval received\n\nACS is retrying the exact action.").send()
    allowed, action_identity, verified = await _run_guarded_delete(
        approval=approval,
        correlation_id=correlation_id,
    )
    if not allowed:
        await cl.Message(content="### Blocked\n\nThe approval could not be used.").send()
        return
    await cl.Message(
        content=(
            "### Action executed and verified\n\n"
            f"Record `{RECORD_ID}` is absent.\n\n"
            f"ACS action identity: `{action_identity}`\n\n"
            f"Verification: `{verified}`\n\n"
            "Evidence was stored locally without record content."
        ),
        actions=[
            cl.Action(
                name="cleanup_aut002",
                payload={},
                label="Clean up evidence",
                description="Remove local demo evidence.",
            )
        ],
    ).send()


@cl.action_callback("decline_aut002")
async def decline_action(_: cl.Action) -> None:
    await cl.Message(
        content="### Not executed\n\nThe action remains blocked and the record remains present."
    ).send()


@cl.action_callback("cleanup_aut002")
async def cleanup_action(_: cl.Action) -> None:
    evidence_dir = _evidence_dir()
    removed = 0
    for evidence_file in evidence_dir.glob("*.json"):
        evidence_file.unlink()
        removed += 1
    cl.user_session.set("aut_002_records", {RECORD_ID})
    await cl.Message(content=f"### Cleanup complete\n\nRemoved {removed} evidence file(s).").send()


@cl.on_message
async def on_message(_: cl.Message) -> None:
    await cl.Message(
        content="Use the buttons in the chat to test the ACS gate step by step.",
        actions=_actions(),
    ).send()