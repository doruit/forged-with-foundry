"""Real in-process HTTP tests for the A2A server's task-history exposure fix.

Uses the actual a2a-sdk client transport (``JsonRpcTransport``), the actual
Starlette app from ``create_app()``, the actual ``InMemoryTaskStore``, and
real JSON-RPC serialization -- connected in-process via
``httpx.ASGITransport`` (no real network, no live Azure/Foundry calls). Only
Azure PII detection (``text_pii.enforce_text_pii``) and the Foundry model
call (``GovernedAgent.run``) are mocked.

Covers the two P1 findings together: (1) the SDK's own response and stored
task must never carry the raw, unredacted user message, and (2) a second,
independent caller must not be able to retrieve or list any task at all,
since this demo has no caller-based authorization.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest
from a2a.client.transports.jsonrpc import JsonRpcTransport
from a2a.helpers import get_message_text, new_text_message
from a2a.types import Role, TaskState
from a2a.types.a2a_pb2 import GetTaskRequest, ListTasksRequest, SendMessageRequest
from a2a.utils.errors import A2AError

import src.cr001_interop.a2a_server as a2a_server
from src.pri_001.models import PiiFinding, PolicyAction, PolicyDecision, TextEnforcementResult

_RAW_PII_TEXT = "Contact me at jane.doe@example.com about the invoice."
_REDACTED_TEXT = "Contact me at [REDACTED] about the invoice."

_PII_DECISION = PolicyDecision(
    control_id="PRI-001",
    action=PolicyAction.REDACT_AND_ESCALATE,
    pii_count=1,
    categories=("Email",),
    escalate=True,
)


async def _fake_with_pii(text: str, language: str = "en") -> TextEnforcementResult:
    return TextEnforcementResult(
        decision=_PII_DECISION,
        redacted_text=_REDACTED_TEXT,
        findings=(PiiFinding(category="Email", confidence=0.99),),
    )


async def _noop_escalate(decision, source_type: str) -> str:
    return "escalation-id"


class _FakeGovernedAgent:
    async def run(self, governed_text: str) -> str:
        return f"Summary based on governed content: {governed_text}"


@pytest.fixture(autouse=True)
def _isolated_evidence_sink(tmp_path, monkeypatch):
    monkeypatch.setenv("CR001_EVIDENCE_PATH", str(tmp_path / "events.jsonl"))
    monkeypatch.setattr(a2a_server.escalation, "escalate", _noop_escalate)
    monkeypatch.setattr(a2a_server.text_pii, "enforce_text_pii", _fake_with_pii)
    monkeypatch.setattr(a2a_server, "GovernedAgent", _FakeGovernedAgent)


def _new_client(app) -> JsonRpcTransport:
    """A fresh, independent caller: its own httpx client, talking to the real ASGI app in-process."""
    httpx_client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
        # This adapter's agent card declares protocol_version="1.0"; the
        # server's version_validator otherwise treats a missing header as
        # the older "0.3" and rejects the request.
        headers={"A2A-Version": "1.0"},
    )
    agent_card = a2a_server._build_agent_card("http://testserver")
    return JsonRpcTransport(httpx_client=httpx_client, agent_card=agent_card, url="http://testserver/")


def test_send_message_redacts_and_never_returns_raw_pii() -> None:
    async def _run() -> None:
        app = a2a_server.create_app(base_url="http://testserver")
        client = _new_client(app)
        try:
            user_message = new_text_message(_RAW_PII_TEXT, role=Role.ROLE_USER)
            response = await client.send_message(SendMessageRequest(message=user_message))

            assert response.task.status.state == TaskState.TASK_STATE_COMPLETED
            [artifact] = response.task.artifacts
            [part] = artifact.parts
            assert "jane.doe@example.com" not in part.text
            assert "[REDACTED]" in part.text

            # The core of the fix: the SDK's own task object -- history
            # included -- must never carry the raw message either.
            history_text = " ".join(get_message_text(m) for m in response.task.history)
            assert "jane.doe@example.com" not in history_text
        finally:
            await client.httpx_client.aclose()

    asyncio.run(_run())


def test_get_task_is_disabled_even_for_the_caller_that_created_it() -> None:
    async def _run() -> None:
        app = a2a_server.create_app(base_url="http://testserver")
        client = _new_client(app)
        try:
            user_message = new_text_message(_RAW_PII_TEXT, role=Role.ROLE_USER)
            send_response = await client.send_message(SendMessageRequest(message=user_message))
            task_id = send_response.task.id

            with pytest.raises(A2AError):
                await client.get_task(GetTaskRequest(id=task_id))
        finally:
            await client.httpx_client.aclose()

    asyncio.run(_run())


def test_second_independent_client_cannot_retrieve_or_list_the_first_clients_task() -> None:
    async def _run() -> None:
        app = a2a_server.create_app(base_url="http://testserver")
        first_caller = _new_client(app)
        second_caller = _new_client(app)
        try:
            user_message = new_text_message(_RAW_PII_TEXT, role=Role.ROLE_USER)
            send_response = await first_caller.send_message(SendMessageRequest(message=user_message))
            task_id = send_response.task.id

            # A different caller altogether must not be able to reach the
            # first caller's task via either retrieval method.
            with pytest.raises(A2AError):
                await second_caller.get_task(GetTaskRequest(id=task_id))
            with pytest.raises(A2AError):
                await second_caller.list_tasks(ListTasksRequest())
        finally:
            await first_caller.httpx_client.aclose()
            await second_caller.httpx_client.aclose()

    asyncio.run(_run())


def test_a2a_delegation_still_completes_normally() -> None:
    """The retrieval fix must not break normal, non-PII delegation."""

    async def _run() -> None:
        app = a2a_server.create_app(base_url="http://testserver")
        client = _new_client(app)
        try:
            benign_message = new_text_message("Please reschedule my appointment.", role=Role.ROLE_USER)
            response = await client.send_message(SendMessageRequest(message=benign_message))
            assert response.task.status.state == TaskState.TASK_STATE_COMPLETED
        finally:
            await client.httpx_client.aclose()

    asyncio.run(_run())


def test_a2a_fails_closed_and_retrieval_stays_disabled_when_pii_service_errors(monkeypatch) -> None:
    """Fail-closed behavior and the retrieval fix must both hold when PRI-001 itself errors."""

    async def _fake_raises(text: str, language: str = "en") -> TextEnforcementResult:
        raise a2a_server.text_pii.PiiEnforcementError("Text PII service unavailable; input blocked.")

    monkeypatch.setattr(a2a_server.text_pii, "enforce_text_pii", _fake_raises)

    async def _run() -> None:
        app = a2a_server.create_app(base_url="http://testserver")
        client = _new_client(app)
        try:
            user_message = new_text_message(_RAW_PII_TEXT, role=Role.ROLE_USER)
            response = await client.send_message(SendMessageRequest(message=user_message))

            assert response.task.status.state == TaskState.TASK_STATE_FAILED
            task_id = response.task.id

            with pytest.raises(A2AError):
                await client.get_task(GetTaskRequest(id=task_id))
        finally:
            await client.httpx_client.aclose()

    asyncio.run(_run())

