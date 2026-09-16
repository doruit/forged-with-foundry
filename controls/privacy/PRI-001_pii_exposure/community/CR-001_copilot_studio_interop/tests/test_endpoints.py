"""Tests for the CR-001 MCP and A2A endpoints (no live Azure/A2A network calls).

Both protocols are exercised against the same monkeypatched core PRI-001
detection functions so they can be asserted to produce equivalent outcomes,
per the shared-policy constraint (no duplicated PII decision logic). Async
calls use ``asyncio.run`` (no pytest-asyncio plugin in this repo), matching
the existing ``test_acs_gate.py`` convention.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import src.cr001_interop.a2a_server as a2a_server
import src.cr001_interop.mcp_server as mcp_server
from src.pri_001.models import PiiFinding, PolicyAction, PolicyDecision, TextEnforcementResult
from src.pri_001.text_pii import PiiEnforcementError

_NO_PII_DECISION = PolicyDecision(
    control_id="PRI-001", action=PolicyAction.ALLOW, pii_count=0, categories=(), escalate=False
)
_PII_DECISION = PolicyDecision(
    control_id="PRI-001",
    action=PolicyAction.REDACT_AND_ESCALATE,
    pii_count=1,
    categories=("Email",),
    escalate=True,
)


async def _fake_no_pii(text: str, language: str = "en") -> TextEnforcementResult:
    return TextEnforcementResult(decision=_NO_PII_DECISION, redacted_text=text)


async def _fake_with_pii(text: str, language: str = "en") -> TextEnforcementResult:
    return TextEnforcementResult(
        decision=_PII_DECISION,
        redacted_text="[REDACTED] contact me",
        findings=(PiiFinding(category="Email", confidence=0.99),),
    )


async def _fake_raises(text: str, language: str = "en") -> TextEnforcementResult:
    raise PiiEnforcementError("Text PII service unavailable; input blocked.")


async def _noop_escalate(decision, source_type: str) -> str:
    return "escalation-id"


@pytest.fixture(autouse=True)
def _isolated_evidence_sink(tmp_path, monkeypatch):
    monkeypatch.setenv("CR001_EVIDENCE_PATH", str(tmp_path / "events.jsonl"))
    monkeypatch.setattr(mcp_server.escalation, "escalate", _noop_escalate)
    monkeypatch.setattr(a2a_server.escalation, "escalate", _noop_escalate)


def _read_recorded_events(tmp_path) -> list[dict]:
    from src.cr001_interop.evidence import read_events

    return read_events(tmp_path / "events.jsonl")


def test_mcp_redact_text_no_pii_allows_and_attests(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(mcp_server.text_pii, "enforce_text_pii", _fake_no_pii)

    result = asyncio.run(
        mcp_server.redact_text(text="hi there", agent_id="a1", run_id="r1", trace_id="t1")
    )

    assert result["action"] == "allow"
    events = _read_recorded_events(tmp_path)
    [attestation] = [e for e in events if e["event_name"] == "pii.control.evaluated"]
    assert attestation["decision"] == "allow"
    assert attestation["protocol"] == "mcp"


def test_mcp_redact_text_with_pii_redacts_and_attests(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(mcp_server.text_pii, "enforce_text_pii", _fake_with_pii)

    result = asyncio.run(
        mcp_server.redact_text(
            text="contact me at jane@example.com", agent_id="a1", run_id="r1", trace_id="t1"
        )
    )

    assert result["action"] == "redact_and_escalate"
    assert "[REDACTED]" in result["redacted_text"]
    events = _read_recorded_events(tmp_path)
    [attestation] = [e for e in events if e["event_name"] == "pii.control.evaluated"]
    assert attestation["decision"] == "redact"


def test_mcp_redact_text_failure_emits_error_and_fails_closed(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(mcp_server.text_pii, "enforce_text_pii", _fake_raises)

    with pytest.raises(PiiEnforcementError):
        asyncio.run(mcp_server.redact_text(text="hi", agent_id="a1", run_id="r1", trace_id="t1"))

    events = _read_recorded_events(tmp_path)
    [attestation] = [e for e in events if e["event_name"] == "pii.control.evaluated"]
    assert attestation["decision"] == "error"
    assert attestation["outcome"] == "failure"


class _FakeEventQueue:
    def __init__(self) -> None:
        self.enqueued: list[object] = []

    async def enqueue_event(self, event: object) -> None:
        self.enqueued.append(event)


class _FakeTaskUpdater:
    def __init__(self, *args, **kwargs) -> None:
        self.statuses: list[str] = []

    async def update_status(self, *, state, message=None) -> None:
        self.statuses.append(state)

    async def add_artifact(self, *args, **kwargs) -> None:
        pass


def _patch_a2a_collaborators(monkeypatch, user_text: str) -> SimpleNamespace:
    fake_task = SimpleNamespace(id="task-1", context_id="ctx-1")
    monkeypatch.setattr(a2a_server, "new_task", lambda **kwargs: fake_task)
    monkeypatch.setattr(a2a_server, "get_message_text", lambda message: user_text)
    monkeypatch.setattr(a2a_server, "new_text_message", lambda text: text)
    monkeypatch.setattr(a2a_server, "new_text_part", lambda text, media_type=None: text)
    monkeypatch.setattr(a2a_server, "TaskUpdater", _FakeTaskUpdater)
    return fake_task


def _fake_message(text: str = "") -> SimpleNamespace:
    """Stand-in for the real a2a Message proto: only task_id/context_id are read pre-execute."""
    return SimpleNamespace(task_id=None, context_id=None, text=text)


def _fake_governed_agent(captured: dict[str, str]):
    class _FakeGovernedAgent:
        async def run(self, governed_text: str) -> str:
            captured["governed_text"] = governed_text
            return "ok"

    return _FakeGovernedAgent


def test_a2a_no_pii_run_allows_and_attests(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(a2a_server.text_pii, "enforce_text_pii", _fake_no_pii)
    _patch_a2a_collaborators(monkeypatch, "hi there")

    captured: dict[str, str] = {}
    monkeypatch.setattr(a2a_server, "GovernedAgent", _fake_governed_agent(captured))

    executor = a2a_server.PriGuardedAgentExecutor()
    context = SimpleNamespace(current_task=None, message=_fake_message())
    asyncio.run(executor.execute(context, _FakeEventQueue()))

    assert captured["governed_text"] == "hi there"
    events = _read_recorded_events(tmp_path)
    [attestation] = [e for e in events if e["event_name"] == "pii.control.evaluated"]
    assert attestation["decision"] == "allow"
    assert attestation["protocol"] == "a2a"


def test_a2a_pii_run_redacts_before_foundry_agent_call(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(a2a_server.text_pii, "enforce_text_pii", _fake_with_pii)
    _patch_a2a_collaborators(monkeypatch, "contact me at jane@example.com")

    captured: dict[str, str] = {}
    monkeypatch.setattr(a2a_server, "GovernedAgent", _fake_governed_agent(captured))

    executor = a2a_server.PriGuardedAgentExecutor()
    context = SimpleNamespace(current_task=None, message=_fake_message())
    asyncio.run(executor.execute(context, _FakeEventQueue()))

    assert captured["governed_text"] == "[REDACTED] contact me"
    assert "jane@example.com" not in captured["governed_text"]


def test_a2a_failure_fails_closed_without_calling_foundry_agent(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(a2a_server.text_pii, "enforce_text_pii", _fake_raises)
    _patch_a2a_collaborators(monkeypatch, "hi")

    called = {"agent_invoked": False}

    class _FakeGovernedAgent:
        async def run(self, governed_text: str) -> str:
            called["agent_invoked"] = True
            return "should not happen"

    monkeypatch.setattr(a2a_server, "GovernedAgent", _FakeGovernedAgent)

    executor = a2a_server.PriGuardedAgentExecutor()
    context = SimpleNamespace(current_task=None, message=_fake_message())
    asyncio.run(executor.execute(context, _FakeEventQueue()))

    assert called["agent_invoked"] is False
    events = _read_recorded_events(tmp_path)
    [attestation] = [e for e in events if e["event_name"] == "pii.control.evaluated"]
    assert attestation["decision"] == "error"


def test_mcp_and_a2a_produce_equivalent_decisions_for_same_input(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(mcp_server.text_pii, "enforce_text_pii", _fake_with_pii)
    monkeypatch.setattr(a2a_server.text_pii, "enforce_text_pii", _fake_with_pii)
    _patch_a2a_collaborators(monkeypatch, "contact me at jane@example.com")

    captured: dict[str, str] = {}
    monkeypatch.setattr(a2a_server, "GovernedAgent", _fake_governed_agent(captured))

    mcp_result = asyncio.run(
        mcp_server.redact_text(
            text="contact me at jane@example.com", agent_id="a1", run_id="r1", trace_id="t1"
        )
    )
    executor = a2a_server.PriGuardedAgentExecutor()
    asyncio.run(executor.execute(SimpleNamespace(current_task=None, message=_fake_message()), _FakeEventQueue()))

    events = _read_recorded_events(tmp_path)
    decisions = {e["protocol"]: e["decision"] for e in events if e["event_name"] == "pii.control.evaluated"}
    assert mcp_result["action"] == "redact_and_escalate"
    assert decisions == {"mcp": "redact", "a2a": "redact"}


def test_evidence_never_contains_the_synthetic_pii_value(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(mcp_server.text_pii, "enforce_text_pii", _fake_with_pii)

    asyncio.run(
        mcp_server.redact_text(
            text="contact me at jane@example.com", agent_id="a1", run_id="r1", trace_id="t1"
        )
    )

    raw_sink_text = (tmp_path / "events.jsonl").read_text(encoding="utf-8")
    assert "jane@example.com" not in raw_sink_text


def test_a2a_default_base_url_falls_back_to_loopback(monkeypatch) -> None:
    monkeypatch.delenv("WEBSITE_HOSTNAME", raising=False)
    monkeypatch.delenv("CR001_PUBLIC_HOSTNAME", raising=False)

    assert a2a_server._default_base_url() == "http://127.0.0.1:9999"


def test_a2a_default_base_url_uses_website_hostname_when_hosted(monkeypatch) -> None:
    monkeypatch.setenv("WEBSITE_HOSTNAME", "fwf-cr001-a2a.azurewebsites.net")
    monkeypatch.delenv("CR001_PUBLIC_HOSTNAME", raising=False)

    assert a2a_server._default_base_url() == "https://fwf-cr001-a2a.azurewebsites.net"

