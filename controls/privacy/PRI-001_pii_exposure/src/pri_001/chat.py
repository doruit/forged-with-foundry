"""Chainlit UI for the deterministic PRI-001 enforcement demonstration."""

from __future__ import annotations

import logging
from pathlib import Path

import chainlit as cl
from dotenv import load_dotenv

from .agent import GovernedAgent
from .document_pii import SUPPORTED_EXTENSIONS, enforce_document_pii
from .escalation import escalate
from .models import PolicyAction, PolicyDecision
from .text_pii import PiiEnforcementError, enforce_text_pii

# Shared deployment outputs are the default; a control-local file can override
# them without placing PRI-001 runtime configuration at the repository root.
CONTROL_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
load_dotenv(REPOSITORY_ROOT / "infra" / ".env")
load_dotenv(CONTROL_ROOT / ".env", override=True)
logging.basicConfig(level=logging.INFO)


def _source_label(source_type: str) -> str:
    return {
        "chat_input": "Inbound chat message",
        "native_document": "Uploaded native document",
        "agent_output": "Outbound agent response",
    }.get(source_type, "Content")


def _processing_banner(source_type: str) -> str:
    return (
        f"### ⏳ {_source_label(source_type)} — detection in progress\n"
        "Azure AI Language is inspecting the content inside the enforcement boundary. "
        "Nothing has been sent to GPT-5."
    )


def _banner(
    decision: PolicyDecision,
    source_type: str,
    event_id: str | None = None,
) -> str:
    source = _source_label(source_type)
    destination = (
        "the user" if source_type == "agent_output" else "Agent Framework and GPT-5"
    )
    if decision.action is PolicyAction.BLOCK:
        return (
            f"### ⛔ {source} — blocked (fail closed)\n\n"
            "**1 · Detection:** not safely completed  \n"
            "**2 · Policy decision:** `BLOCK`  \n"
            "**3 · Redaction:** not proven safe; no transformed content is released  \n"
            f"**4 · Handoff:** nothing was sent to {destination}\n\n"
            f"**Reason:** {decision.reason}\n\n"
            "> Detection and redaction are separate. If either required step cannot be "
            "completed safely, PRI-001 blocks the content."
        )
    if decision.escalate:
        categories = ", ".join(decision.categories) or "classified PII"
        reference = f"  \n**Escalation reference:** `{event_id}`" if event_id else ""
        return (
            f"### 🚨 {source} — PII detected\n\n"
            f"**1 · Detection:** `DETECTED` — {decision.pii_count} occurrence(s) in "
            f"{categories}  \n"
            "Detection is the **governance signal**; entity values are not shown.  \n"
            "**2 · Policy decision:** `REDACT_AND_ESCALATE`  \n"
            f"Privacy Officer escalation is immediate.{reference}  \n"
            "**3 · Redaction:** `COMPLETED` — a separate sanitized representation "
            "was created  \n"
            f"**4 · Handoff:** only redacted content may continue to {destination}\n\n"
            "> **Detected** means PII was found. **Redacted** means those findings were "
            "used to create transformed output. The original content stays behind the boundary."
        )
    return (
        f"### ✅ {source} — allowed\n\n"
        "**1 · Detection:** `NOT_DETECTED` — no PII findings  \n"
        "**2 · Policy decision:** `ALLOW`  \n"
        "**3 · Redaction:** `NOT_REQUIRED` — there is nothing to mask  \n"
        f"**4 · Handoff:** content may continue to {destination}\n\n"
        "> No PII detection means redaction is unnecessary; it does not mean redaction occurred."
    )


async def _show_decision(
    decision: PolicyDecision,
    source_type: str,
    status: cl.Message | None = None,
) -> None:
    event_id = await escalate(decision, source_type) if decision.escalate else None
    content = _banner(decision, source_type, event_id)
    if status is None:
        await cl.Message(content=content).send()
    else:
        status.content = content
        await status.update()


async def _govern_text(text: str, source_type: str) -> str | None:
    status = cl.Message(content=_processing_banner(source_type))
    await status.send()
    try:
        result = await enforce_text_pii(text)
    except PiiEnforcementError as exc:
        decision = PolicyDecision(
            control_id="PRI-001",
            action=PolicyAction.BLOCK,
            pii_count=0,
            categories=(),
            escalate=False,
            reason=str(exc),
        )
        await _show_decision(decision, source_type, status)
        return None

    await _show_decision(result.decision, source_type, status)
    if result.decision.escalate:
        await cl.Message(
            content=f"**Redacted preview**\n\n{result.redacted_text}"
        ).send()
    return result.redacted_text


@cl.on_chat_start
async def on_chat_start() -> None:
    cl.user_session.set("agent", GovernedAgent())
    await cl.Message(
        content=(
            "# PRI-001 PII Governance Demo\n\n"
            "Follow each request through four visible phases:\n\n"
            "1. **Detect** — find PII and return category/count metadata.\n"
            "2. **Decide** — PRI-001 allows, redacts + escalates, or blocks.\n"
            "3. **Redact** — create transformed text or a native redacted document.\n"
            "4. **Handoff** — only allowed/redacted content reaches GPT-5; its response "
            "is checked again before display.\n\n"
            "**Detected is not the same as redacted:** detection is a governance signal; "
            "redaction is a content transformation.\n\n"
            "### Try these scenarios\n"
            "- **No PII:** `Explain why governance belongs outside an AI agent.`\n"
            "- **Synthetic PII:** `Contact Alex at alex@example.com.`\n"
            "- **Document:** attach a PDF, DOCX, or TXT file (maximum 10 MB).\n\n"
            "> Governance outside the agent; intelligence inside the agent."
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    governed_parts: list[str] = []

    if message.content.strip():
        governed_text = await _govern_text(message.content, "chat_input")
        if governed_text is None:
            return
        governed_parts.append(f"Governed user message:\n{governed_text}")

    for element in message.elements:
        path_value = getattr(element, "path", None)
        name = getattr(element, "name", "uploaded-document")
        if not path_value:
            continue
        suffix = Path(name).suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            await cl.Message(
                content="### ⛔ Unsupported attachment\nOnly PDF, DOCX, and TXT are accepted."
            ).send()
            return

        # Chainlit stores the upload temporarily; bytes are passed directly to
        # Azure Blob Storage. No custom PDF/DOCX extraction occurs here.
        content = Path(path_value).read_bytes()
        status = cl.Message(content=_processing_banner("native_document"))
        await status.send()
        try:
            document = await enforce_document_pii(name, content)
        except PiiEnforcementError as exc:
            decision = PolicyDecision(
                control_id="PRI-001",
                action=PolicyAction.BLOCK,
                pii_count=0,
                categories=(),
                escalate=False,
                reason=str(exc),
            )
            await _show_decision(decision, "native_document", status)
            return

        await _show_decision(document.decision, "native_document", status)
        elements = [
            cl.File(
                name=document.redacted_name,
                content=document.redacted_bytes,
                display="inline",
            )
        ]
        preview = (
            f"\n\n**Redacted preview**\n\n{document.safe_text_for_agent}"
            if document.safe_text_for_agent is not None
            else ""
        )
        await cl.Message(
            content=(
                "**Microsoft-generated redacted document** is available below. "
                "The original upload was not sent to GPT-5."
                f"{preview}"
            ),
            elements=elements,
        ).send()

        if document.safe_text_for_agent is not None:
            governed_parts.append(
                f"Governed redacted TXT document ({document.redacted_name}):\n"
                f"{document.safe_text_for_agent}"
            )
        else:
            governed_parts.append(
                f"A governed {suffix[1:].upper()} document named "
                f"{document.redacted_name} was processed. The native redacted artifact "
                "is available to the user; no original document content is available "
                "to you. Detected categories: "
                f"{', '.join(document.decision.categories) or 'none'}."
            )

    if not governed_parts:
        return

    agent: GovernedAgent = cl.user_session.get("agent")
    agent_status = cl.Message(
        content=(
            "### ⏳ Agent handoff in progress\n"
            "Only content that passed PRI-001 is now being sent to GPT-5. "
            "The original detected PII is not included."
        )
    )
    await agent_status.send()
    response = await agent.run("\n\n".join(governed_parts))
    agent_status.content = (
        "### ✅ Agent response received\n"
        "GPT-5 processing is complete. The response must now pass outbound PII "
        "detection before it can be displayed."
    )
    await agent_status.update()

    # Apply the same deterministic boundary to model output before UX display.
    governed_response = await _govern_text(response, "agent_output")
    if governed_response is not None:
        await cl.Message(
            content=(
                f"{governed_response}\n\n"
                "_Response displayed only after outbound PRI-001 enforcement._"
            )
        ).send()
