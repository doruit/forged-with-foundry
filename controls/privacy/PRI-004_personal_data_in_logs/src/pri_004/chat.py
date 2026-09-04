"""Guided Chainlit experience for the PRI-004 personal-data-in-logs demo."""

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

from agent_control_specification import AgentControlBlocked  # noqa: E402

from .agent import LogOperationsAgent  # noqa: E402
from .models import LogAction, LogDecision  # noqa: E402
from .monitor_store import LogControlError, MonitorLogStore  # noqa: E402
from .presentation import decision_card, scan_summary  # noqa: E402


def _actions() -> list[cl.Action]:
    return [
        cl.Action(
            name="seed_pri004",
            payload={},
            label="1 · Seed synthetic log entries",
            description="Ingest three safe scenarios via the real Logs Ingestion API.",
        ),
        cl.Action(
            name="scan_pri004",
            payload={},
            label="2 · Scan for personal data",
            description="Query Log Analytics and evaluate the deterministic PII policy.",
        ),
        cl.Action(
            name="cleanup_pri004",
            payload={},
            label="Cleanup demo records",
            description="Submit a real, guarded Data Purge request for PRI-004 records only.",
        ),
    ]


def _get_store() -> MonitorLogStore:
    store = cl.user_session.get("log_store")
    if not isinstance(store, MonitorLogStore):
        store = MonitorLogStore()
        cl.user_session.set("log_store", store)
    return store


def _decisions() -> dict[str, LogDecision]:
    value = cl.user_session.get("log_decisions") or {}
    return value if isinstance(value, dict) else {}


def _operations() -> dict[str, str]:
    value = cl.user_session.get("log_purge_operations") or {}
    return value if isinstance(value, dict) else {}


@cl.on_chat_start
async def on_chat_start() -> None:
    try:
        store = MonitorLogStore()
        agent = LogOperationsAgent()
    except Exception:
        await cl.Message(
            content=(
                "# PRI-004 unavailable — fail closed\n\n"
                "Required control configuration could not be initialized. "
                "Deploy the shared and PRI-004 infrastructure, then restart the demo."
            )
        ).send()
        return

    cl.user_session.set("log_store", store)
    cl.user_session.set("log_agent", agent)
    cl.user_session.set("log_decisions", {})
    cl.user_session.set("log_purge_operations", {})
    await cl.Message(
        content=(
            "# PRI-004 Log Operations Agent\n\n"
            "This demo shows personal data reaching application logs, and a safe response "
            "using real Azure Monitor Logs infrastructure:\n\n"
            "1. **Seed** three synthetic log entries.\n"
            "2. **Scan** them with Azure AI Language Text PII and a deterministic policy.\n"
            "3. **Explain** the decisions with a Foundry agent.\n"
            "4. **Preview** a redacted mask for records with detected PII.\n"
            "5. **Request a real Data Purge** — Microsoft's own compliance deletion API. "
            "This is asynchronous and can take **up to 30 days** to complete; the demo does "
            "not simulate instant deletion.\n"
            "6. **Suppress a field going forward** — an \"update logging\" fix that changes "
            "future records, not past ones.\n\n"
            "> Log Analytics ingestion can take a few minutes to become queryable; if a scan "
            "finds nothing yet, try scanning again shortly."
        ),
        actions=_actions(),
    ).send()


@cl.action_callback("seed_pri004")
async def seed_demo(_: cl.Action) -> None:
    status = cl.Message(content="### ⏳ Ingesting three synthetic log entries…")
    await status.send()
    try:
        await _get_store().seed_scenarios()
    except LogControlError as exc:
        status.content = f"### ⛔ Seed failed safely\n\n{exc}"
    else:
        status.content = (
            "### ✅ Synthetic log entries ingested\n\n"
            "Ingested: one clean entry, one entry with personal data, and one entry with a "
            "simulated detector outage. All content is synthetic. Ingestion may take a few "
            "minutes to become queryable — scan when ready."
        )
    await status.update()


@cl.action_callback("scan_pri004")
async def scan_demo(_: cl.Action) -> None:
    status = cl.Message(
        content=(
            "### ⏳ Scanning ingested log entries…\n\n"
            "Retrying for up to a minute to account for ingestion latency."
        )
    )
    await status.send()
    try:
        decisions, pending = await _get_store().scan()
    except LogControlError as exc:
        status.content = f"### ⛔ PRI-004 unavailable — fail closed\n\n{exc}"
        await status.update()
        return

    if pending:
        status.content = (
            "### ⏳ No synthetic entries visible yet\n\n"
            "Log Analytics ingestion can take a few minutes. Seed first if you haven't, "
            "then click **Scan for personal data** again shortly."
        )
        await status.update()
        return

    by_id = {decision.decision_id: decision for decision in decisions}
    cl.user_session.set("log_decisions", by_id)
    status.content = scan_summary(decisions)
    await status.update()

    for decision in decisions:
        actions: list[cl.Action] = []
        if decision.action is LogAction.PII_DETECTED:
            actions.extend(
                [
                    cl.Action(
                        name="mask_pri004",
                        payload={"decision_id": decision.decision_id},
                        label="Preview redacted mask",
                        description="Safe, non-destructive preview only.",
                    ),
                    cl.Action(
                        name="purge_pri004",
                        payload={"decision_id": decision.decision_id},
                        label="Request real Data Purge",
                        description="Guarded; asynchronous; up to 30 days to complete.",
                    ),
                    cl.Action(
                        name="suppress_field_pri004",
                        payload={"decision_id": decision.decision_id},
                        label="Suppress field going forward",
                        description="Update-logging fix for future records only.",
                    ),
                ]
            )
        await cl.Message(content=decision_card(decision), actions=actions).send()

    agent: LogOperationsAgent = cl.user_session.get("log_agent")
    agent_status = cl.Message(content="### ⏳ Agent explaining the deterministic results…")
    await agent_status.send()
    try:
        explanation = await agent.explain(decisions)
    except Exception:
        agent_status.content = (
            "### ⚠️ Agent explanation unavailable\n\n"
            "The deterministic decisions remain valid. No mask, purge, or policy change was authorized."
        )
    else:
        agent_status.content = f"## Agent explanation\n\n{explanation}"
    await agent_status.update()


@cl.action_callback("mask_pri004")
async def mask_preview(action: cl.Action) -> None:
    decision_id = str(action.payload.get("decision_id", ""))
    decision = _decisions().get(decision_id)
    if decision is None:
        await cl.Message(
            content="### ⛔ Preview rejected\n\nThe decision is stale or unknown. Run a new scan."
        ).send()
        return

    status = cl.Message(content="### ⏳ Generating a redacted preview…")
    await status.send()
    try:
        redacted = await _get_store().mask_preview(decision)
    except LogControlError as exc:
        status.content = f"### ⛔ Preview failed safely\n\n{exc}"
    else:
        status.content = (
            f"### 🕶️ Redacted preview for `{decision.record_id}`\n\n"
            f"> {redacted}\n\n"
            "This preview is for review only; it does not change the stored log entry."
        )
    await status.update()


@cl.action_callback("purge_pri004")
async def request_purge(action: cl.Action) -> None:
    decision_id = str(action.payload.get("decision_id", ""))
    decision = _decisions().get(decision_id)
    if decision is None:
        await cl.Message(
            content="### ⛔ Purge rejected\n\nThe decision is stale or unknown. Run a new scan."
        ).send()
        return

    status = cl.Message(content="### ⏳ Verifying eligibility and submitting the Data Purge request…")
    await status.send()
    try:
        store = _get_store()
        store.request_purge_approval(decision)
        result = await store.execute_purge(decision)
    except (AgentControlBlocked, LogControlError) as exc:
        status.content = f"### ⛔ Purge refused\n\n{exc}"
        await status.update()
        return

    if result.operation_id:
        operations = _operations()
        operations[decision.decision_id] = result.operation_id
        cl.user_session.set("log_purge_operations", operations)

    status.content = (
        f"### 📨 Purge `{result.status.upper()}`\n\n"
        f"{result.message}\n\n"
        f"**Operation id:** `{result.operation_id or 'n/a'}`\n\n"
        f"**Evidence reference:** `{result.evidence_id}`"
    )
    await status.update()

    if result.operation_id:
        await cl.Message(
            content="Check the purge status below once it's ready to poll.",
            actions=[
                cl.Action(
                    name="check_purge_pri004",
                    payload={"decision_id": decision.decision_id},
                    label="Check purge status",
                    description="Expect 'pending'; completion can take up to 30 days.",
                )
            ],
        ).send()


@cl.action_callback("check_purge_pri004")
async def check_purge_status(action: cl.Action) -> None:
    decision_id = str(action.payload.get("decision_id", ""))
    operation_id = _operations().get(decision_id)
    if operation_id is None:
        await cl.Message(
            content="### ⛔ No purge operation found\n\nRequest a purge first."
        ).send()
        return

    status = cl.Message(content="### ⏳ Checking purge status…")
    await status.send()
    try:
        purge_status = await _get_store().check_purge_status(operation_id)
    except LogControlError as exc:
        status.content = f"### ⛔ Status check failed safely\n\n{exc}"
    else:
        status.content = (
            f"### 📋 Purge status: `{purge_status}`\n\n"
            "Microsoft's documented SLA allows up to 30 days for completion; "
            "`pending` is the expected result shortly after a request."
        )
    await status.update()


@cl.action_callback("suppress_field_pri004")
async def suppress_field(action: cl.Action) -> None:
    decision_id = str(action.payload.get("decision_id", ""))
    decision = _decisions().get(decision_id)
    if decision is None:
        await cl.Message(
            content="### ⛔ Policy change rejected\n\nThe decision is stale or unknown. Run a new scan."
        ).send()
        return

    status = cl.Message(content="### ⏳ Checking eligibility and applying the field policy…")
    await status.send()
    try:
        store = _get_store()
        store.request_field_policy_approval(decision)
        result = await store.apply_field_policy(decision)
    except (AgentControlBlocked, LogControlError) as exc:
        status.content = f"### ⛔ Policy change refused\n\n{exc}"
        await status.update()
        return

    status.content = (
        f"### 🔧 Field policy `{result.status.upper()}`\n\n"
        f"{result.message}\n\n"
        f"**Evidence reference:** `{result.evidence_id}`"
    )
    await status.update()

    await cl.Message(
        content="Seed a follow-up record for this field to see the fix take effect on a rescan.",
        actions=[
            cl.Action(
                name="seed_followup_pri004",
                payload={"field_name": decision.field_name},
                label=f"Seed follow-up record for '{decision.field_name}'",
                description="Demonstrates the update-logging fix going forward.",
            )
        ],
    ).send()


@cl.action_callback("seed_followup_pri004")
async def seed_followup(action: cl.Action) -> None:
    field_name = str(action.payload.get("field_name", "Message"))
    status = cl.Message(content=f"### ⏳ Seeding a follow-up record for '{field_name}'…")
    await status.send()
    try:
        await _get_store().seed_followup_for_field(field_name)
    except LogControlError as exc:
        status.content = f"### ⛔ Seed failed safely\n\n{exc}"
    else:
        status.content = (
            f"### ✅ Follow-up record seeded for '{field_name}'\n\n"
            "Rescan (allowing a few minutes for ingestion) to see it come back clean."
        )
    await status.update()


@cl.action_callback("cleanup_pri004")
async def cleanup_demo(_: cl.Action) -> None:
    status = cl.Message(content="### ⏳ Submitting a broad guarded purge for PRI-004 records…")
    await status.send()
    try:
        result = await _get_store().cleanup()
    except LogControlError as exc:
        status.content = f"### ⛔ Cleanup failed safely\n\n{exc}"
    else:
        cl.user_session.set("log_decisions", {})
        cl.user_session.set("log_purge_operations", {})
        status.content = (
            f"### ✅ Cleanup submitted\n\n{result.message}\n\n"
            f"**Operation id:** `{result.operation_id or 'n/a'}`"
        )
    await status.update()


@cl.on_message
async def on_message(_: cl.Message) -> None:
    await cl.Message(
        content=(
            "Use the guided buttons below. The agent cannot bypass the deterministic "
            "scan or the explicit mask/purge/field-policy steps."
        ),
        actions=_actions(),
    ).send()
