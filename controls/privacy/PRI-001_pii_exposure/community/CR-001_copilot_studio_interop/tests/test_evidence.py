"""Tests for the CR-001 shared evidence schema and local JSONL sink."""

from __future__ import annotations

import dataclasses

import pytest

from src.cr001_interop.evidence import (
    EvidenceEvent,
    EvidenceValidationError,
    read_events,
    record_event,
    validate_event,
)


def test_run_started_event_is_valid() -> None:
    event = EvidenceEvent(
        event_name="agent.run.started",
        agent_id="a1",
        platform="foundry",
        run_id="r1",
        trace_id="t1",
    )
    validate_event(event)  # must not raise


def test_run_started_event_missing_field_raises() -> None:
    event = EvidenceEvent(
        event_name="agent.run.started", agent_id="", platform="foundry", run_id="r1", trace_id="t1"
    )
    with pytest.raises(EvidenceValidationError):
        validate_event(event)


def test_control_evaluated_requires_decision_and_protocol() -> None:
    event = EvidenceEvent(
        event_name="pii.control.evaluated",
        agent_id="a1",
        platform="foundry",
        run_id="r1",
        trace_id="t1",
        control_id="PRI-001",
        control_required=True,
        protocol="mcp",
        policy_version="cr-001-v1",
        decision=None,
    )
    with pytest.raises(EvidenceValidationError):
        validate_event(event)


def test_control_evaluated_rejects_unknown_decision() -> None:
    event = EvidenceEvent(
        event_name="pii.control.evaluated",
        agent_id="a1",
        platform="foundry",
        run_id="r1",
        trace_id="t1",
        control_id="PRI-001",
        control_required=True,
        protocol="mcp",
        policy_version="cr-001-v1",
        decision="maybe",  # type: ignore[arg-type]
    )
    with pytest.raises(EvidenceValidationError):
        validate_event(event)


def test_record_and_read_events_round_trip(tmp_path, monkeypatch) -> None:
    sink = tmp_path / "events.jsonl"
    monkeypatch.setenv("CR001_EVIDENCE_PATH", str(sink))
    event = EvidenceEvent(
        event_name="agent.run.started",
        agent_id="a1",
        platform="foundry",
        run_id="r1",
        trace_id="t1",
    )

    record_event(event)

    read_back = read_events(sink)
    assert len(read_back) == 1
    assert read_back[0]["agent_id"] == "a1"


def test_evidence_event_has_no_content_fields() -> None:
    field_names = {f.name for f in dataclasses.fields(EvidenceEvent)}
    for forbidden in ("text", "prompt", "message", "content", "pii_value", "redacted_text"):
        assert forbidden not in field_names
