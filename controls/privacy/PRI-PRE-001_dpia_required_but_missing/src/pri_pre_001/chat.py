"""Guided Chainlit experience for the PRI-PRE-001 DPIA gate demo."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import chainlit as cl
from dotenv import load_dotenv

CONTROL_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
load_dotenv(REPOSITORY_ROOT / "infra" / ".env")
load_dotenv(CONTROL_ROOT / ".env", override=True)
logging.basicConfig(level=logging.INFO)

from .agent import DpiaGateAgent  # noqa: E402
from .azure_policy_gate import GoLiveGateError, attempt_go_live  # noqa: E402
from .models import GateAction, GateDecision  # noqa: E402
from .presentation import decision_card, scan_summary  # noqa: E402
from .storage import DpiaGateStore, DpiaGateStoreError  # noqa: E402


def _actions() -> list[cl.Action]:
    return [
        cl.Action(
            name="seed_pripre001",
            payload={},
            label="1 · Seed synthetic project records",
            description="Create four safe DPIA-gate scenarios.",
        ),
        cl.Action(
            name="scan_pripre001",
            payload={},
            label="2 · Scan for DPIA-required-but-missing",
            description="Evaluate risk score and DPIA evidence against the deterministic policy.",
        ),
        cl.Action(
            name="cleanup_pripre001",
            payload={},
            label="Cleanup demo records",
            description="Delete only PRI-PRE-001 synthetic records.",
        ),
    ]


def _get_store() -> DpiaGateStore:
    store = cl.user_session.get("dpia_store")
    if not isinstance(store, DpiaGateStore):
        store = DpiaGateStore()
        cl.user_session.set("dpia_store", store)
    return store


def _decisions() -> dict[str, GateDecision]:
    value = cl.user_session.get("dpia_decisions") or {}
    return value if isinstance(value, dict) else {}


@cl.on_chat_start
async def on_chat_start() -> None:
    try:
        store = DpiaGateStore()
        agent = DpiaGateAgent()
    except Exception:
        await cl.Message(
            content=(
                "# PRI-PRE-001 unavailable — fail closed\n\n"
                "Required control configuration could not be initialized. "
                "Deploy the shared and PRI-PRE-001 infrastructure, then restart the demo."
            )
        ).send()
        return

    cl.user_session.set("dpia_store", store)
    cl.user_session.set("dpia_agent", agent)
    cl.user_session.set("dpia_decisions", {})
    await cl.Message(
        content=(
            "# PRI-PRE-001 DPIA Gate Agent\n\n"
            "This demo shows an AI system going live without a required DPIA, and a safe "
            "response using a real Azure Policy `deny` assignment:\n\n"
            "1. **Seed** four synthetic AI-system/project records.\n"
            "2. **Scan** them with a deterministic multi-factor risk score and DPIA-evidence check.\n"
            "3. **Explain** the decisions with a Foundry agent.\n"
            "4. **Attempt go-live** — this never creates a real resource. It calls "
            "`az deployment group validate`, which genuinely triggers Azure Policy's real "
            "`deny` evaluation.\n\n"
            "> The control decides. The agent explains and orchestrates. **Azure Policy is the "
            "actual backstop** — even if this demo's own code were bypassed, Azure itself still "
            "refuses a non-compliant go-live request."
        ),
        actions=_actions(),
    ).send()


@cl.action_callback("seed_pripre001")
async def seed_demo(_: cl.Action) -> None:
    status = cl.Message(content="### ⏳ Creating four synthetic project records…")
    await status.send()
    try:
        await _get_store().seed_scenarios()
    except DpiaGateStoreError as exc:
        status.content = f"### ⛔ Seed failed safely\n\n{exc}"
    else:
        status.content = (
            "### ✅ Synthetic project register ready\n\n"
            "Created: one low-risk project (no DPIA needed), one high-risk project with a "
            "completed DPIA, one high-risk project with a missing DPIA, and one project with "
            "unknown/invalid risk factors. All data is synthetic."
        )
    await status.update()


@cl.action_callback("scan_pripre001")
async def scan_demo(_: cl.Action) -> None:
    status = cl.Message(
        content=(
            "### ⏳ Scanning the project register…\n\n"
            "Only risk factors and DPIA status/evidence flags are read — never project names "
            "or business content."
        )
    )
    await status.send()
    try:
        decisions = await _get_store().scan()
    except DpiaGateStoreError as exc:
        status.content = f"### ⛔ PRI-PRE-001 unavailable — fail closed\n\n{exc}"
        await status.update()
        return

    by_id = {decision.decision_id: decision for decision in decisions}
    cl.user_session.set("dpia_decisions", by_id)
    status.content = scan_summary(decisions)
    await status.update()

    for decision in decisions:
        actions = [
            cl.Action(
                name="golive_pripre001",
                payload={"decision_id": decision.decision_id},
                label="Attempt go-live",
                description="Re-verifies, then asks Azure Policy for a real answer.",
            )
        ]
        await cl.Message(content=decision_card(decision), actions=actions).send()

    agent: DpiaGateAgent = cl.user_session.get("dpia_agent")
    agent_status = cl.Message(content="### ⏳ Agent explaining the deterministic results…")
    await agent_status.send()
    try:
        explanation = await agent.explain(decisions)
    except Exception:
        agent_status.content = (
            "### ⚠️ Agent explanation unavailable\n\n"
            "The deterministic decisions remain valid. No go-live attempt was authorized."
        )
    else:
        agent_status.content = f"## Agent explanation\n\n{explanation}"
    await agent_status.update()


@cl.action_callback("golive_pripre001")
async def go_live(action: cl.Action) -> None:
    decision_id = str(action.payload.get("decision_id", ""))
    decision = _decisions().get(decision_id)
    if decision is None:
        await cl.Message(
            content="### ⛔ Go-live attempt rejected\n\nThe decision is stale or unknown. Run a new scan."
        ).send()
        return

    status = cl.Message(
        content="### ⏳ Re-verifying and asking Azure Policy for a real answer…"
    )
    await status.send()
    try:
        store = _get_store()
        record = await store.get_record(decision.project_id)
        result = await attempt_go_live(
            decision,
            record,
            subscription_id=os.environ["AZURE_SUBSCRIPTION_ID"],
            resource_group=os.environ["AZURE_RESOURCE_GROUP"],
        )
    except (DpiaGateStoreError, GoLiveGateError) as exc:
        status.content = f"### ⛔ Go-live attempt failed safely\n\n{exc}"
        await status.update()
        return

    icon = "✅" if result.status == GateAction.ALLOWED.value else "🚫"
    policy_line = (
        "Azure Policy: **DENIED** (RequestDisallowedByPolicy)"
        if result.azure_policy_denied
        else "Azure Policy: **allowed** (no objection)"
        if result.azure_policy_denied is False
        else "Azure Policy: not called (refused locally before reaching Azure)"
    )
    status.content = (
        f"### {icon} Go-live `{result.status.upper()}`\n\n"
        f"{result.message}\n\n"
        f"{policy_line}\n\n"
        f"**Evidence reference:** `{result.evidence_id}`"
    )
    await status.update()


@cl.action_callback("cleanup_pripre001")
async def cleanup_demo(_: cl.Action) -> None:
    try:
        await _get_store().cleanup()
    except DpiaGateStoreError as exc:
        await cl.Message(content=f"### ⛔ Cleanup failed safely\n\n{exc}").send()
    else:
        cl.user_session.set("dpia_decisions", {})
        await cl.Message(
            content="### ✅ Cleanup complete\n\nOnly PRI-PRE-001 synthetic records were removed."
        ).send()


@cl.on_message
async def on_message(_: cl.Message) -> None:
    await cl.Message(
        content=(
            "Use the guided buttons below. The agent cannot bypass the deterministic "
            "scan or trigger a go-live attempt on its own."
        ),
        actions=_actions(),
    ).send()
