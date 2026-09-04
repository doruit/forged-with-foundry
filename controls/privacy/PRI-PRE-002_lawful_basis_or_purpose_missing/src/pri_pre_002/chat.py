"""Guided Chainlit experience for the PRI-PRE-002 lawful-basis gate demo."""

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

from .agent import LawfulBasisAgent  # noqa: E402
from .presentation import decision_card, scan_summary  # noqa: E402
from .storage import LawfulBasisStore, LawfulBasisStoreError  # noqa: E402


def _actions() -> list[cl.Action]:
    return [
        cl.Action(
            name="seed_pripre002",
            payload={},
            label="1 · Seed synthetic project records",
            description="Create four safe lawful-basis-gate scenarios.",
        ),
        cl.Action(
            name="scan_pripre002",
            payload={},
            label="2 · Scan for missing lawful basis or purpose",
            description="Evaluate personal-data, lawful-basis, and purpose evidence.",
        ),
        cl.Action(
            name="cleanup_pripre002",
            payload={},
            label="Cleanup demo records",
            description="Delete only PRI-PRE-002 synthetic records.",
        ),
    ]


def _get_store() -> LawfulBasisStore:
    store = cl.user_session.get("lawful_basis_store")
    if not isinstance(store, LawfulBasisStore):
        store = LawfulBasisStore()
        cl.user_session.set("lawful_basis_store", store)
    return store


@cl.on_chat_start
async def on_chat_start() -> None:
    try:
        store = LawfulBasisStore()
        agent = LawfulBasisAgent()
    except Exception:
        await cl.Message(
            content=(
                "# PRI-PRE-002 unavailable — fail closed\n\n"
                "Required control configuration could not be initialized. "
                "Deploy the shared and PRI-PRE-002 infrastructure, then restart the demo."
            )
        ).send()
        return

    cl.user_session.set("lawful_basis_store", store)
    cl.user_session.set("lawful_basis_agent", agent)
    await cl.Message(
        content=(
            "# PRI-PRE-002 Lawful Basis Gate Agent\n\n"
            "This demo shows a project processing personal data without a documented "
            "lawful basis or purpose, and a safe response using a real Azure Policy "
            "**`audit`** assignment:\n\n"
            "1. **Seed** four synthetic AI-system/project records.\n"
            "2. **Scan** them with a deterministic lawful-basis and purpose check.\n"
            "3. **Explain** the decisions with a Foundry agent.\n\n"
            "> The control decides. The agent explains. **Azure Policy is the real "
            "backstop** — but unlike a `deny` block, `audit` flags a non-compliant "
            "resource for remediation without stopping it, and the result shows up in "
            "Azure's compliance report on its own schedule, not instantly in this chat. "
            "See this control's README for a real, manual walkthrough of that flag."
        ),
        actions=_actions(),
    ).send()


@cl.action_callback("seed_pripre002")
async def seed_demo(_: cl.Action) -> None:
    status = cl.Message(content="### ⏳ Creating four synthetic project records…")
    await status.send()
    try:
        await _get_store().seed_scenarios()
    except LawfulBasisStoreError as exc:
        status.content = f"### ⛔ Seed failed safely\n\n{exc}"
    else:
        status.content = (
            "### ✅ Synthetic project register ready\n\n"
            "Created: one project with no personal data, one with a valid lawful basis "
            "and documented purpose, one with a missing lawful basis, and one with an "
            "unrecognized lawful-basis value. All data is synthetic."
        )
    await status.update()


@cl.action_callback("scan_pripre002")
async def scan_demo(_: cl.Action) -> None:
    status = cl.Message(
        content=(
            "### ⏳ Scanning the project register…\n\n"
            "Only the personal-data flag and lawful-basis/purpose evidence flags are "
            "read — never project names or business content."
        )
    )
    await status.send()
    try:
        decisions = await _get_store().scan()
    except LawfulBasisStoreError as exc:
        status.content = f"### ⛔ PRI-PRE-002 unavailable — fail closed\n\n{exc}"
        await status.update()
        return

    status.content = scan_summary(decisions)
    await status.update()

    for decision in decisions:
        await cl.Message(content=decision_card(decision)).send()

    agent: LawfulBasisAgent = cl.user_session.get("lawful_basis_agent")
    agent_status = cl.Message(content="### ⏳ Agent explaining the deterministic results…")
    await agent_status.send()
    try:
        explanation = await agent.explain(decisions)
    except Exception:
        agent_status.content = (
            "### ⚠️ Agent explanation unavailable\n\n"
            "The deterministic decisions remain valid."
        )
    else:
        agent_status.content = f"## Agent explanation\n\n{explanation}"
    await agent_status.update()


@cl.action_callback("cleanup_pripre002")
async def cleanup_demo(_: cl.Action) -> None:
    try:
        await _get_store().cleanup()
    except LawfulBasisStoreError as exc:
        await cl.Message(content=f"### ⛔ Cleanup failed safely\n\n{exc}").send()
    else:
        await cl.Message(
            content="### ✅ Cleanup complete\n\nOnly PRI-PRE-002 synthetic records were removed."
        ).send()


@cl.on_message
async def on_message(_: cl.Message) -> None:
    await cl.Message(
        content=(
            "Use the guided buttons below. The agent cannot bypass the deterministic "
            "scan or alter a compliance flag."
        ),
        actions=_actions(),
    ).send()
