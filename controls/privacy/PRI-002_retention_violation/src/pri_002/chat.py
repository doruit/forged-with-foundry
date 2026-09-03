"""Guided Chainlit experience for the PRI-002 retention demo."""

from __future__ import annotations

import logging
from pathlib import Path

import chainlit as cl
from dotenv import load_dotenv

CONTROL_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
load_dotenv(REPOSITORY_ROOT / "infra" / ".env")
load_dotenv(CONTROL_ROOT / ".env", override=True)
logging.basicConfig(level=logging.INFO)

from .approval import ApprovalError  # noqa: E402
from .agent import RetentionOperationsAgent  # noqa: E402
from .models import RetentionAction, RetentionDecision  # noqa: E402
from .presentation import decision_card, scan_summary  # noqa: E402
from .storage import RetentionControlError, RetentionStore  # noqa: E402


def _actions() -> list[cl.Action]:
    return [
        cl.Action(
            name="seed_pri002",
            payload={},
            label="1 · Create synthetic records",
            description="Create three safe retention scenarios.",
        ),
        cl.Action(
            name="scan_pri002",
            payload={},
            label="2 · Run retention scan",
            description="Evaluate Blob metadata without downloading content.",
        ),
        cl.Action(
            name="cleanup_pri002",
            payload={},
            label="Cleanup demo records",
            description="Delete only PRI-002 synthetic records.",
        ),
    ]


def _get_store() -> RetentionStore:
    store = cl.user_session.get("retention_store")
    if not isinstance(store, RetentionStore):
        store = RetentionStore()
        cl.user_session.set("retention_store", store)
    return store


def _decisions() -> dict[str, RetentionDecision]:
    value = cl.user_session.get("retention_decisions") or {}
    return value if isinstance(value, dict) else {}


@cl.on_chat_start
async def on_chat_start() -> None:
    try:
        store = RetentionStore()
        agent = RetentionOperationsAgent()
    except Exception:
        await cl.Message(
            content=(
                "# PRI-002 unavailable — fail closed\n\n"
                "Required control configuration could not be initialized. "
                "Deploy the shared and PRI-002 infrastructure, then restart the demo."
            )
        ).send()
        return

    cl.user_session.set("retention_store", store)
    cl.user_session.set("retention_agent", agent)
    cl.user_session.set("retention_decisions", {})
    await cl.Message(
        content=(
            "# PRI-002 Retention Operations Agent\n\n"
            "This demo shows an Azure Blob retention exception and a safe response:\n\n"
            "1. **Seed** three synthetic records.\n"
            "2. **Scan** metadata with a deterministic control.\n"
            "3. **Explain** the decisions with a Foundry agent.\n"
            "4. **Approve** the one destructive remediation explicitly.\n"
            "5. **Verify** deletion and record metadata-only evidence.\n\n"
            "> Azure Lifecycle Management is the primary platform control. PRI-002 "
            "independently detects an exception. The agent explains and orchestrates; "
            "it never decides or deletes on its own."
        ),
        actions=_actions(),
    ).send()


@cl.action_callback("seed_pri002")
async def seed_demo(_: cl.Action) -> None:
    status = cl.Message(content="### ⏳ Creating three synthetic retention scenarios…")
    await status.send()
    try:
        await _get_store().seed_scenarios()
    except RetentionControlError as exc:
        status.content = f"### ⛔ Seed failed safely\n\n{exc}"
    else:
        status.content = (
            "### ✅ Synthetic scenarios ready\n\n"
            "Created: one compliant record, one overdue record missed by the lifecycle "
            "tag filter, and one protected record. Payloads are synthetic."
        )
    await status.update()


@cl.action_callback("scan_pri002")
async def scan_demo(_: cl.Action) -> None:
    status = cl.Message(
        content=(
            "### ⏳ Scanning retention metadata…\n\n"
            "Blob payloads are not downloaded. The projected clock makes the lifecycle "
            "outcome demonstrable immediately."
        )
    )
    await status.send()
    try:
        decisions = await _get_store().scan()
    except RetentionControlError as exc:
        status.content = f"### ⛔ PRI-002 unavailable — fail closed\n\n{exc}"
        await status.update()
        return

    by_id = {decision.decision_id: decision for decision in decisions}
    cl.user_session.set("retention_decisions", by_id)
    status.content = scan_summary(decisions)
    await status.update()

    for decision in decisions:
        actions: list[cl.Action] = []
        if decision.action is RetentionAction.REMEDIATION_REQUIRED:
            actions = [
                cl.Action(
                    name="approve_pri002",
                    payload={"decision_id": decision.decision_id},
                    label="Approve guarded deletion",
                    description="One-time approval for this exact Blob version.",
                ),
                cl.Action(
                    name="decline_pri002",
                    payload={"decision_id": decision.decision_id},
                    label="Escalate without deletion",
                    description="Keep the record active and route for review.",
                ),
            ]
        await cl.Message(content=decision_card(decision), actions=actions).send()

    agent: RetentionOperationsAgent = cl.user_session.get("retention_agent")
    agent_status = cl.Message(
        content="### ⏳ Agent explaining the deterministic results…"
    )
    await agent_status.send()
    try:
        explanation = await agent.explain(decisions)
    except Exception:
        agent_status.content = (
            "### ⚠️ Agent explanation unavailable\n\n"
            "The deterministic decisions remain valid. No remediation was authorized."
        )
    else:
        agent_status.content = f"## Agent explanation\n\n{explanation}"
    await agent_status.update()


@cl.action_callback("approve_pri002")
async def approve_remediation(action: cl.Action) -> None:
    decision_id = str(action.payload.get("decision_id", ""))
    decision = _decisions().get(decision_id)
    if decision is None:
        await cl.Message(
            content="### ⛔ Approval rejected\n\nThe decision is stale or unknown. Run a new scan."
        ).send()
        return

    status = cl.Message(
        content=(
            "### ⏳ Human approval received\n\n"
            "Rechecking scope and ETag, then executing the guarded delete tool."
        )
    )
    await status.send()
    try:
        store = _get_store()
        token = store.approve(decision)
        result = await store.remediate(decision, token)
    except (ApprovalError, RetentionControlError) as exc:
        status.content = f"### ⛔ Remediation failed safely\n\n{exc}"
    else:
        icon = "✅" if result.verified_absent else "⛔"
        status.content = (
            f"### {icon} Remediation `{result.status.upper()}`\n\n"
            f"{result.message}\n\n"
            f"**Evidence reference:** `{result.evidence_id}`\n\n"
            "Soft delete remains enabled for one day on the dedicated PRI-002 storage account."
        )
    await status.update()


@cl.action_callback("decline_pri002")
async def decline_remediation(action: cl.Action) -> None:
    decision_id = str(action.payload.get("decision_id", ""))
    decision = _decisions().get(decision_id)
    if decision is None:
        message = "The decision is stale or unknown. Run a new scan."
    else:
        message = (
            "Deletion was not authorized. The active record remains unchanged and the "
            "exception is routed to the Privacy Officer for review."
        )
    await cl.Message(content=f"### 🛡️ Remediation not executed\n\n{message}").send()


@cl.action_callback("cleanup_pri002")
async def cleanup_demo(_: cl.Action) -> None:
    try:
        await _get_store().cleanup()
    except RetentionControlError as exc:
        await cl.Message(content=f"### ⛔ Cleanup failed safely\n\n{exc}").send()
    else:
        cl.user_session.set("retention_decisions", {})
        await cl.Message(
            content="### ✅ Cleanup complete\n\nOnly PRI-002 synthetic records were removed."
        ).send()


@cl.on_message
async def on_message(_: cl.Message) -> None:
    await cl.Message(
        content=(
            "Use the guided buttons below. The agent cannot bypass the deterministic "
            "scan or the explicit approval step."
        ),
        actions=_actions(),
    ).send()
