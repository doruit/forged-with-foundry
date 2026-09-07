"""Guided Chainlit experience for the DAT-PRE-002 data-classification demo."""

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
from .agent import ClassificationAgent  # noqa: E402
from .graph_client import GraphControlError, SensitivityLabelStore  # noqa: E402
from .models import ClassificationAction, ClassificationDecision  # noqa: E402
from .presentation import decision_card, scan_summary  # noqa: E402


def _actions() -> list[cl.Action]:
    return [
        cl.Action(
            name="seed_dat_pre_002",
            payload={},
            label="1 · Seed synthetic files",
            description="Create three synthetic files in a dedicated OneDrive demo folder.",
        ),
        cl.Action(
            name="scan_dat_pre_002",
            payload={},
            label="2 · Scan classification state",
            description="Read each file's real Purview sensitivity-label state via Microsoft Graph.",
        ),
        cl.Action(
            name="cleanup_dat_pre_002",
            payload={},
            label="Cleanup demo folder",
            description="Delete only the DAT-PRE-002-demo OneDrive folder and its synthetic files.",
        ),
    ]


def _get_store() -> SensitivityLabelStore:
    store = cl.user_session.get("dat_pre_002_store")
    if not isinstance(store, SensitivityLabelStore):
        store = SensitivityLabelStore()
        cl.user_session.set("dat_pre_002_store", store)
    return store


def _decisions() -> dict[str, ClassificationDecision]:
    value = cl.user_session.get("dat_pre_002_decisions") or {}
    return value if isinstance(value, dict) else {}


@cl.on_chat_start
async def on_chat_start() -> None:
    try:
        store = SensitivityLabelStore()
    except GraphControlError as exc:
        await cl.Message(content=f"# DAT-PRE-002 unavailable — fail closed\n\n{exc}").send()
        return

    agent: ClassificationAgent | None
    try:
        agent = ClassificationAgent()
    except Exception:
        agent = None

    cl.user_session.set("dat_pre_002_store", store)
    cl.user_session.set("dat_pre_002_agent", agent)
    cl.user_session.set("dat_pre_002_decisions", {})
    agent_note = (
        ""
        if agent is not None
        else (
            "\n\n> Foundry explanation is unavailable (shared infrastructure not deployed). "
            "Scanning and classification still use real Microsoft Purview state."
        )
    )
    await cl.Message(
        content=(
            "# DAT-PRE-002 Data Classification Agent\n\n"
            "This demo shows a file with unknown sensitivity, and a safe response using real "
            "Microsoft Purview Information Protection state through Microsoft Graph:\n\n"
            "1. **Seed** three synthetic files into a dedicated OneDrive demo folder — a "
            "confidential-marked file with no label, a public-marked file pre-classified as a "
            "compliant baseline, and a simulated extraction-failure file.\n"
            "2. **Scan** each file's real sensitivity-label state (never asserted locally).\n"
            "3. **Explain** the decisions with a Foundry agent (optional).\n"
            "4. **Classify** a flagged file with a guarded, real, asynchronous "
            "`assignSensitivityLabel` call, then re-verify the platform confirms it.\n\n"
            "> The first device-code sign-in opens a browser prompt; approve it with the "
            "signed-in demo account." + agent_note
        ),
        actions=_actions(),
    ).send()


@cl.action_callback("seed_dat_pre_002")
async def seed_demo(_: cl.Action) -> None:
    status = cl.Message(content="### ⏳ Creating three synthetic files…")
    await status.send()
    try:
        await _get_store().seed_scenarios()
    except GraphControlError as exc:
        status.content = f"### ⛔ Seed failed safely\n\n{exc}"
    else:
        status.content = (
            "### ✅ Synthetic files created\n\n"
            "Created: one confidential-marked file with no label, one public-marked file "
            "pre-classified as a compliant baseline, and one simulated extraction-failure "
            "file. All content is synthetic — scan when ready."
        )
    await status.update()


@cl.action_callback("scan_dat_pre_002")
async def scan_demo(_: cl.Action) -> None:
    status = cl.Message(content="### ⏳ Reading real Purview sensitivity-label state…")
    await status.send()
    try:
        decisions = await _get_store().scan()
    except GraphControlError as exc:
        status.content = f"### ⛔ DAT-PRE-002 unavailable — fail closed\n\n{exc}"
        await status.update()
        return

    if not decisions:
        status.content = "### ⏳ No synthetic files found yet\n\nSeed first, then scan again."
        await status.update()
        return

    by_id = {decision.decision_id: decision for decision in decisions}
    cl.user_session.set("dat_pre_002_decisions", by_id)
    status.content = scan_summary(decisions)
    await status.update()

    for decision in decisions:
        actions: list[cl.Action] = []
        if decision.action is ClassificationAction.FLAGGED:
            actions.append(
                cl.Action(
                    name="classify_dat_pre_002",
                    payload={"decision_id": decision.decision_id},
                    label="Classify before use",
                    description="Guarded, real, asynchronous assignSensitivityLabel call.",
                )
            )
        await cl.Message(content=decision_card(decision), actions=actions).send()

    agent: ClassificationAgent | None = cl.user_session.get("dat_pre_002_agent")
    if agent is None:
        return
    agent_status = cl.Message(content="### ⏳ Agent explaining the deterministic results…")
    await agent_status.send()
    try:
        explanation = await agent.explain(decisions)
    except Exception:
        agent_status.content = (
            "### ⚠️ Agent explanation unavailable\n\n"
            "The deterministic decisions remain valid. No file was classified without explicit "
            "approval."
        )
    else:
        agent_status.content = f"## Agent explanation\n\n{explanation}"
    await agent_status.update()


@cl.action_callback("classify_dat_pre_002")
async def classify_file(action: cl.Action) -> None:
    decision_id = str(action.payload.get("decision_id", ""))
    decision = _decisions().get(decision_id)
    if decision is None:
        await cl.Message(
            content="### ⛔ Unknown decision\n\nScan again before requesting classification."
        ).send()
        return

    status = cl.Message(
        content=(
            "### ⏳ Requesting classification…\n\n"
            "Re-checking current state, calling the real, asynchronous "
            "`assignSensitivityLabel` operation, and re-verifying the result."
        )
    )
    await status.send()
    try:
        result = await _get_store().classify(
            decision, ApprovalTicket(approved=True, issued_at=datetime.now(UTC))
        )
    except (AgentControlBlocked, GraphControlError) as exc:
        status.content = f"### ⛔ Classify failed safely\n\n{exc}"
        await status.update()
        return

    icon = "✅" if result.status == "resolved" else ("⏳" if result.status == "pending" else "⛔")
    status.content = (
        f"### {icon} Classify {result.status}\n\n"
        f"{result.message}\n\n"
        f"- **Evidence id:** {result.evidence_id}\n"
        f"- **Operation:** {result.operation_id or 'n/a'}"
    )
    await status.update()


@cl.action_callback("cleanup_dat_pre_002")
async def cleanup_demo(_: cl.Action) -> None:
    status = cl.Message(content="### ⏳ Deleting the DAT-PRE-002 demo folder…")
    await status.send()
    try:
        removed = await _get_store().cleanup()
    except GraphControlError as exc:
        status.content = f"### ⛔ Cleanup failed safely\n\n{exc}"
    else:
        status.content = (
            "### ✅ Cleanup complete\n\nRemoved the DAT-PRE-002-demo OneDrive folder."
            if removed
            else "### ℹ️ Nothing to clean up\n\nThe demo folder did not exist."
        )
    await status.update()
