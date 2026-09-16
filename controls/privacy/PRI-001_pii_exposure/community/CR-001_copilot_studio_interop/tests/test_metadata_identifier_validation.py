"""Tests for CR-001's identifier-metadata bounding (agent_id/run_id/trace_id).

MCP tool arguments are caller-supplied; an untrusted model can pass anything
as ``agent_id``/``run_id``/``trace_id``, including PII-shaped strings (an
email address has been observed in practice). These must be rejected before
any processing or evidence write, and the rejected value must never be
echoed back in an error message or written to the evidence sink.
"""

from __future__ import annotations

import asyncio

import pytest

import src.cr001_interop.mcp_server as mcp_server
from src.cr001_interop.evidence import InvalidIdentifierError, read_events
from src.pri_001.models import PolicyAction, PolicyDecision, TextEnforcementResult

_NO_PII_DECISION = PolicyDecision(
    control_id="PRI-001", action=PolicyAction.ALLOW, pii_count=0, categories=(), escalate=False
)

_PII_SHAPED_AGENT_ID = "attacker@example.com"


async def _fake_no_pii(text: str, language: str = "en") -> TextEnforcementResult:
    return TextEnforcementResult(decision=_NO_PII_DECISION, redacted_text=text)


@pytest.fixture(autouse=True)
def _isolated_evidence_sink(tmp_path, monkeypatch):
    monkeypatch.setenv("CR001_EVIDENCE_PATH", str(tmp_path / "events.jsonl"))
    monkeypatch.setattr(mcp_server.text_pii, "enforce_text_pii", _fake_no_pii)


def _events(tmp_path) -> list[dict]:
    return read_events(tmp_path / "events.jsonl")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("agent_id", _PII_SHAPED_AGENT_ID),
        ("run_id", "please call me at 555-0100"),
        ("trace_id", "Jane Doe <jane.doe@example.com>"),
    ],
)
def test_redact_text_rejects_pii_shaped_identifiers(field: str, value: str, tmp_path) -> None:
    kwargs = {"text": "hi", "agent_id": "a1", "run_id": "r1", "trace_id": "t1"}
    kwargs[field] = value

    with pytest.raises(InvalidIdentifierError) as excinfo:
        asyncio.run(mcp_server.redact_text(**kwargs))

    # The rejected value must never be echoed back in the error message...
    assert value not in str(excinfo.value)
    # ...nor recorded in evidence -- nothing should have been written at all.
    assert _events(tmp_path) == []


def test_redact_document_rejects_pii_shaped_agent_id(tmp_path) -> None:
    with pytest.raises(InvalidIdentifierError) as excinfo:
        asyncio.run(
            mcp_server.redact_document(
                filename="notes.txt",
                content_base64="aGVsbG8=",
                agent_id=_PII_SHAPED_AGENT_ID,
                run_id="r1",
                trace_id="t1",
            )
        )

    assert _PII_SHAPED_AGENT_ID not in str(excinfo.value)
    assert _events(tmp_path) == []


def test_existing_demo_identifiers_remain_valid(tmp_path) -> None:
    """The demo's own identifiers (hyphenated slug, uuid4) must keep working."""
    result = asyncio.run(
        mcp_server.redact_text(
            text="hi",
            agent_id="copilot-pii-demo",
            run_id="550e8400-e29b-41d4-a716-446655440000",
            trace_id="6ba7b810-9dad-11d1-80b4-00c04fd430c8",
        )
    )

    assert result["action"] == "allow"
    [event] = _events(tmp_path)
    assert event["agent_id"] == "copilot-pii-demo"
