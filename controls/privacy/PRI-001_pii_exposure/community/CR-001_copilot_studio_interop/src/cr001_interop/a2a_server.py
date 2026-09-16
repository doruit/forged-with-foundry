"""OPTIONAL: A2A adapter exposing PRI-001's PII-governed Foundry agent.

Community-requested extension answering "can a Copilot Studio agent delegate
to this via A2A?". Uses the official ``a2a-sdk`` (``a2aproject/a2a-python``)
rather than inventing a protocol. Reuses, unchanged: the shared
``pre_tool_call``/``post_tool_call`` ACS gate in ``acs_gate.py``, core
PRI-001's ``text_pii.enforce_text_pii`` detection/redaction, ``escalation``,
and ``agent.GovernedAgent`` -- this file only maps A2A's task/message
lifecycle onto that existing boundary and emits one ``pii.control.evaluated``
attestation per run. No second Foundry agent, no duplicated PII policy.

Run locally with: ``uvicorn src.cr001_interop.a2a_server:create_app --factory``
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any

from a2a.helpers import get_message_text, new_task_from_user_message, new_text_message, new_text_part
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill, TaskState
from agent_control_specification import AgentControlBlocked
from starlette.applications import Starlette

from src.pri_001 import escalation, text_pii
from src.pri_001.agent import GovernedAgent
from src.pri_001.models import PolicyAction

from .acs_gate import get_mcp_control
from .evidence import DEFAULT_POLICY_VERSION, EvidenceEvent, record_event

logger = logging.getLogger("cr001_interop.a2a_server")

_CONTROL_ID = "PRI-001"
_PROTOCOL = "a2a"
_AGENT_ID = "foundry-pii-demo"

_ACTION_TO_EVIDENCE_DECISION: dict[PolicyAction, str] = {
    PolicyAction.ALLOW: "allow",
    PolicyAction.REDACT_AND_ESCALATE: "redact",
    PolicyAction.BLOCK: "deny",
}


def _emit_control_evidence(
    *, run_id: str, trace_id: str, decision: str, pii_count: int, categories: tuple[str, ...]
) -> None:
    record_event(
        EvidenceEvent(
            event_name="pii.control.evaluated",
            agent_id=_AGENT_ID,
            platform="foundry",
            run_id=run_id,
            trace_id=trace_id,
            control_id=_CONTROL_ID,
            control_required=True,
            protocol=_PROTOCOL,
            policy_version=DEFAULT_POLICY_VERSION,
            decision=decision,
            redaction_count=pii_count,
            pii_categories=categories,
            outcome="success" if decision != "error" else "failure",
        )
    )


class PriGuardedAgentExecutor(AgentExecutor):
    """Gates every inbound A2A message through PRI-001 before the Foundry agent sees it."""

    def __init__(self) -> None:
        self._agent = GovernedAgent()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task = context.current_task
        if task is None:
            task = new_task_from_user_message(context.message)
            await event_queue.enqueue_event(task)

        # Correlation: reuse A2A's own IDs where the SDK provides them; a
        # freshly generated run_id/trace_id (rather than a silent guess) is
        # the honest fallback when it doesn't -- never claim propagation
        # this adapter cannot actually observe.
        run_id = getattr(task, "id", None) or str(uuid.uuid4())
        trace_id = getattr(task, "context_id", None) or str(uuid.uuid4())

        task_updater = TaskUpdater(event_queue=event_queue, task_id=task.id, context_id=task.context_id)
        await task_updater.update_status(
            state=TaskState.TASK_STATE_WORKING,
            message=new_text_message("Evaluating PRI-001 before delegating to the governed agent..."),
        )

        query = get_message_text(context.message) or ""
        control = get_mcp_control()

        async def gated_execute(effective_args: dict[str, Any]) -> dict[str, Any]:
            enforcement = await text_pii.enforce_text_pii(effective_args["text"])
            decision = enforcement.decision
            if decision.action is PolicyAction.REDACT_AND_ESCALATE:
                await escalation.escalate(decision, source_type="cr001_a2a_redact_text")
            return {
                "redacted_text": enforcement.redacted_text,
                "pii_count": decision.pii_count,
                "categories": list(decision.categories),
                "action": decision.action.value,
            }

        try:
            gate_result = await control.run_tool(
                "redact_text", {"text": query}, gated_execute, approval_resolver=None
            )
        except AgentControlBlocked:
            _emit_control_evidence(
                run_id=run_id, trace_id=trace_id, decision="deny", pii_count=0, categories=()
            )
            await task_updater.update_status(
                state=TaskState.TASK_STATE_FAILED,
                message=new_text_message("Blocked by PRI-001: content could not be safely governed."),
            )
            return
        except text_pii.PiiEnforcementError:
            _emit_control_evidence(
                run_id=run_id, trace_id=trace_id, decision="error", pii_count=0, categories=()
            )
            await task_updater.update_status(
                state=TaskState.TASK_STATE_FAILED,
                message=new_text_message("PRI-001 could not be evaluated; failing closed."),
            )
            return

        result = gate_result.value
        _emit_control_evidence(
            run_id=run_id,
            trace_id=trace_id,
            decision=_ACTION_TO_EVIDENCE_DECISION[PolicyAction(result["action"])],
            pii_count=result["pii_count"],
            categories=tuple(result["categories"]),
        )

        agent_response = await self._agent.run(result["redacted_text"])
        await task_updater.add_artifact(parts=[new_text_part(text=agent_response, media_type="text/plain")])
        await task_updater.update_status(
            state=TaskState.TASK_STATE_COMPLETED,
            message=new_text_message("Request completed."),
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("Cancel is not supported by this demo executor.")


def _build_agent_card(base_url: str) -> AgentCard:
    skill = AgentSkill(
        id="pri_001_governed_chat",
        name="PRI-001 governed chat",
        description="Answers a request only after PRI-001 detects and redacts PII in it.",
        input_modes=["text/plain"],
        output_modes=["text/plain"],
        tags=["pii", "governance", "pri-001"],
        examples=["Summarize the attached customer note."],
    )
    return AgentCard(
        name="PRI-001 PII-Governed Agent (CR-001 demo)",
        description="Community-request demo: A2A entry point in front of PRI-001's PII gate.",
        version="0.1.0",
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        capabilities=AgentCapabilities(streaming=False),
        supported_interfaces=[
            AgentInterface(protocol_binding="JSONRPC", url=base_url, protocol_version="1.0")
        ],
        skills=[skill],
    )


def _default_base_url() -> str:
    """Loopback default, or the App Service's public HTTPS URL when hosted."""
    hosted_name = os.environ.get("WEBSITE_HOSTNAME") or os.environ.get("CR001_PUBLIC_HOSTNAME")
    if hosted_name:
        return f"https://{hosted_name}"
    return "http://127.0.0.1:9999"


def create_app(base_url: str | None = None) -> Starlette:
    """ASGI app factory: ``uvicorn src.cr001_interop.a2a_server:create_app --factory``.

    ``base_url`` defaults to the hosted App Service URL when deployed (uvicorn's
    ``--factory`` calls this with no arguments, so the default must be
    resolved here rather than at the call site).
    """
    base_url = base_url or _default_base_url()
    request_handler = DefaultRequestHandler(
        agent_executor=PriGuardedAgentExecutor(),
        task_store=InMemoryTaskStore(),
        agent_card=_build_agent_card(base_url),
    )
    routes = []
    routes.extend(create_agent_card_routes(_build_agent_card(base_url)))
    # enable_v0_3_compat=True: Copilot Studio's A2A client (and the docs' own
    # sample payload) uses the v0.3 method name "message/send", not this
    # SDK's newer gRPC-style default method names.
    routes.extend(create_jsonrpc_routes(request_handler, "/", enable_v0_3_compat=True))
    return Starlette(routes=routes)
