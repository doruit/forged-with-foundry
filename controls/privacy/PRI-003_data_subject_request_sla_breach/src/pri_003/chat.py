"""Guided Chainlit experience for the PRI-003 DSR SLA demo."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import chainlit as cl
from dotenv import load_dotenv

CONTROL_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
load_dotenv(REPOSITORY_ROOT / "infra" / ".env")
load_dotenv(CONTROL_ROOT / ".env", override=True)
logging.basicConfig(level=logging.INFO)

from agent_control_specification import AgentControlBlocked  # noqa: E402

from .acs_gate import ApprovalTicket  # noqa: E402
from .agent import DSROperationsAgent  # noqa: E402
from .models import DSRAction, DSRDecision  # noqa: E402
from .presentation import decision_card, scan_summary  # noqa: E402
from .storage import DSRControlError, DSRStore  # noqa: E402


def _actions() -> list[cl.Action]:
    return [
        cl.Action(
            name="seed_pri003",
            payload={},
            label="1 · Create synthetic DSR records",
            description="Create five safe SLA scenarios.",
        ),
        cl.Action(
            name="scan_pri003",
            payload={},
            label="2 · Run SLA scan",
            description="Evaluate DSR metadata against the deterministic SLA policy.",
        ),
        cl.Action(
            name="cleanup_pri003",
            payload={},
            label="Cleanup demo records",
            description="Delete only PRI-003 synthetic records.",
        ),
    ]


def _get_store() -> DSRStore:
    store = cl.user_session.get("dsr_store")
    if not isinstance(store, DSRStore):
        store = DSRStore()
        cl.user_session.set("dsr_store", store)
    return store


def _decisions() -> dict[str, DSRDecision]:
    value = cl.user_session.get("dsr_decisions") or {}
    return value if isinstance(value, dict) else {}


@cl.on_chat_start
async def on_chat_start() -> None:
    try:
        store = DSRStore()
    except Exception:
        await cl.Message(
            content=(
                "# PRI-003 unavailable — fail closed\n\n"
                "Required control configuration could not be initialized. "
                "Deploy the PRI-003 infrastructure, then restart the demo."
            )
        ).send()
        return

    # The Foundry agent only explains an already-final deterministic decision
    # in plain language; it adds no decision authority. Its absence must not
    # block the real, authoritative SLA scan and escalation/extension below.
    agent: DSROperationsAgent | None
    try:
        agent = DSROperationsAgent()
    except Exception:
        agent = None

    cl.user_session.set("dsr_store", store)
    cl.user_session.set("dsr_agent", agent)
    cl.user_session.set("dsr_decisions", {})
    agent_note = (
        ""
        if agent is not None
        else (
            "\n\n> Foundry explanation is unavailable (shared infrastructure not deployed). "
            "Scanning, escalation, and extension still use real Azure Table Storage state."
        )
    )
    await cl.Message(
        content=(
            "# PRI-003 DSR Operations Agent\n\n"
            "This demo shows a data subject request SLA breach and a safe response:\n\n"
            "1. **Seed** five synthetic DSR records.\n"
            "2. **Scan** the register with a deterministic SLA policy.\n"
            "3. **Explain** the decisions with a Foundry agent.\n"
            "4. **Escalate** at-risk or breached requests to the DPO.\n"
            "5. **Extend** one eligible request's due date, explicitly and once.\n\n"
            "> No Microsoft platform automatically tracks a DSR SLA in this demo. PRI-003 "
            "is the primary control here. The agent explains and orchestrates; it never "
            "decides, escalates, or extends on its own."
            f"{agent_note}"
        ),
        actions=_actions(),
    ).send()


@cl.action_callback("seed_pri003")
async def seed_demo(_: cl.Action) -> None:
    status = cl.Message(content="### ⏳ Creating seven synthetic DSR records…")
    await status.send()
    try:
        await _get_store().seed_scenarios()
    except DSRControlError as exc:
        status.content = f"### ⛔ Seed failed safely\n\n{exc}"
    else:
        status.content = (
            "### ✅ Synthetic DSR register ready\n\n"
            "Created: one on-track access request, one at-risk rectification request, "
            "one breached open erasure request, one access request completed after its "
            "deadline, one access request completed within its deadline, one closed "
            "request with no recorded completion date, and one request with an unknown "
            "type. All data is synthetic."
        )
    await status.update()


@cl.action_callback("scan_pri003")
async def scan_demo(_: cl.Action) -> None:
    status = cl.Message(
        content=(
            "### ⏳ Scanning the DSR register…\n\n"
            "Only request type, dates, and status are read — never requester content."
        )
    )
    await status.send()
    try:
        decisions = await _get_store().scan()
    except DSRControlError as exc:
        status.content = f"### ⛔ PRI-003 unavailable — fail closed\n\n{exc}"
        await status.update()
        return

    by_id = {decision.decision_id: decision for decision in decisions}
    cl.user_session.set("dsr_decisions", by_id)
    status.content = scan_summary(decisions)
    await status.update()

    for decision in decisions:
        actions: list[cl.Action] = []
        if decision.action in (DSRAction.AT_RISK, DSRAction.BREACHED) and not decision.resolved:
            actions.append(
                cl.Action(
                    name="escalate_pri003",
                    payload={"decision_id": decision.decision_id},
                    label="Escalate to DPO",
                    description="Log-only escalation event; no record is changed.",
                )
            )
            actions.append(
                cl.Action(
                    name="request_extension_pri003",
                    payload={"decision_id": decision.decision_id},
                    label="Request SLA extension",
                    description="Only permitted once for eligible request types.",
                )
            )
        await cl.Message(content=decision_card(decision), actions=actions).send()

    agent: DSROperationsAgent | None = cl.user_session.get("dsr_agent")
    if agent is None:
        return
    agent_status = cl.Message(
        content="### ⏳ Agent explaining the deterministic results…"
    )
    await agent_status.send()
    try:
        explanation = await agent.explain(decisions)
    except Exception:
        agent_status.content = (
            "### ⚠️ Agent explanation unavailable\n\n"
            "The deterministic decisions remain valid. No escalation or extension was authorized."
        )
    else:
        agent_status.content = f"## Agent explanation\n\n{explanation}"
    await agent_status.update()


@cl.action_callback("escalate_pri003")
async def escalate_request(action: cl.Action) -> None:
    decision_id = str(action.payload.get("decision_id", ""))
    decision = _decisions().get(decision_id)
    if decision is None:
        await cl.Message(
            content="### ⛔ Escalation rejected\n\nThe decision is stale or unknown. Run a new scan."
        ).send()
        return

    status = cl.Message(content="### ⏳ Recording DPO escalation…")
    await status.send()
    try:
        result = await _get_store().escalate(decision)
    except DSRControlError as exc:
        status.content = f"### ⛔ Escalation failed safely\n\n{exc}"
    else:
        status.content = (
            f"### 📣 Escalation `{result.status.upper()}`\n\n"
            f"{result.message}\n\n"
            f"**Evidence reference:** `{result.evidence_id}`"
        )
    await status.update()


@cl.action_callback("request_extension_pri003")
async def request_extension(action: cl.Action) -> None:
    decision_id = str(action.payload.get("decision_id", ""))
    decision = _decisions().get(decision_id)
    if decision is None:
        await cl.Message(
            content="### ⛔ Extension rejected\n\nThe decision is stale or unknown. Run a new scan."
        ).send()
        return

    status = cl.Message(content="### ⏳ Checking extension eligibility and applying it…")
    await status.send()
    try:
        store = _get_store()
        store.request_extension_approval(decision)
        # The ticket is created here, at the exact moment of the click; the
        # resolver never assumes approval happened just because it was called.
        approval = ApprovalTicket(approved=True, issued_at=datetime.now(UTC))
        result = await store.grant_extension(decision, approval)
    except (AgentControlBlocked, DSRControlError) as exc:
        status.content = f"### ⛔ Extension refused\n\n{exc}"
    else:
        icon = "✅" if result.extension_granted else "⛔"
        status.content = (
            f"### {icon} Extension `{result.status.upper()}`\n\n"
            f"{result.message}\n\n"
            f"**Evidence reference:** `{result.evidence_id}`\n\n"
            "Rescan to see the updated due date."
        )
    await status.update()


@cl.action_callback("cleanup_pri003")
async def cleanup_demo(_: cl.Action) -> None:
    try:
        await _get_store().cleanup()
    except DSRControlError as exc:
        await cl.Message(content=f"### ⛔ Cleanup failed safely\n\n{exc}").send()
    else:
        cl.user_session.set("dsr_decisions", {})
        await cl.Message(
            content="### ✅ Cleanup complete\n\nOnly PRI-003 synthetic records were removed."
        ).send()


@cl.on_message
async def on_message(_: cl.Message) -> None:
    await cl.Message(
        content=(
            "Use the guided buttons below. The agent cannot bypass the deterministic "
            "scan or the explicit escalation/extension steps."
        ),
        actions=_actions(),
    ).send()
