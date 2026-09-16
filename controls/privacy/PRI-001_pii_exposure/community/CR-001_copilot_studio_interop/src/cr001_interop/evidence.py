"""Shared evidence schema and local sink for the CR-001 coverage-measurement demo.

Endpoint logs alone only prove a call happened, not that every required run
went through PRI-001. ``agent.run.started``/``agent.run.completed`` (emitted
by ``demo_runner.py``, independent of the endpoint) supply the denominator;
``pii.control.evaluated`` (emitted by ``mcp_server.py``/``a2a_server.py``)
supplies the numerator. ``compliance_evaluator.py`` compares the two.

This module has no field for prompts, messages, detected PII values,
redacted text, or tool arguments -- there is no place in the schema to put
that data. ``agent_id``/``run_id``/``trace_id`` are technical correlation
identifiers, not content, but MCP callers supply them as free-form tool
arguments (see ``mcp_server.py``), so ``validate_identifier`` below bounds
their shape before anything is persisted -- a free-form string field is
still a place PII-shaped content could otherwise land.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

EventName = Literal["agent.run.started", "pii.control.evaluated", "agent.run.completed"]
Protocol = Literal["mcp", "a2a", "none"]
Decision = Literal["allow", "redact", "deny", "error"]
Outcome = Literal["success", "failure"]

_DEFAULT_SINK_PATH = Path(__file__).resolve().parents[2] / "interop_evidence.jsonl"

#: Shared by both adapters so the evaluator can recognize a "known" version.
DEFAULT_POLICY_VERSION = "cr-001-v1"

_REQUIRED_FIELDS: dict[EventName, tuple[str, ...]] = {
    "agent.run.started": ("agent_id", "platform", "run_id", "trace_id", "outcome"),
    "agent.run.completed": ("agent_id", "platform", "run_id", "trace_id", "outcome"),
    "pii.control.evaluated": (
        "agent_id",
        "platform",
        "run_id",
        "trace_id",
        "control_id",
        "control_required",
        "protocol",
        "policy_version",
        "decision",
        "outcome",
    ),
}

_VALID_DECISIONS: frozenset[str] = frozenset({"allow", "redact", "deny", "error"})


@dataclass(frozen=True)
class EvidenceEvent:
    """One governance-evidence record. No content field exists by design."""

    event_name: EventName
    agent_id: str
    platform: str
    run_id: str
    trace_id: str
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    control_id: str | None = None
    control_required: bool | None = None
    protocol: Protocol = "none"
    policy_version: str | None = None
    decision: Decision | None = None
    redaction_count: int = 0
    pii_categories: tuple[str, ...] = ()
    outcome: Outcome = "success"


class EvidenceValidationError(ValueError):
    """Raised when an event is missing a required field for its event_name."""


def validate_event(event: EvidenceEvent) -> None:
    """Raise ``EvidenceValidationError`` if a required field is missing/invalid."""
    missing = [
        field_name
        for field_name in _REQUIRED_FIELDS[event.event_name]
        if getattr(event, field_name) in (None, "")
    ]
    if missing:
        raise EvidenceValidationError(
            f"{event.event_name} event is missing required field(s): {', '.join(missing)}"
        )
    if event.event_name == "pii.control.evaluated" and event.decision not in _VALID_DECISIONS:
        raise EvidenceValidationError(
            f"pii.control.evaluated event has invalid decision: {event.decision!r}"
        )


#: Short technical token: letters/digits/'-'/'_' only, 1-64 chars, alnum ends.
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9_-]{0,62}[A-Za-z0-9])?$")


class InvalidIdentifierError(ValueError):
    """Raised when a correlation identifier (agent_id/run_id/trace_id) fails validation.

    The rejected value is deliberately never included in this message, in
    any log line it triggers, or in evidence -- callers have been observed
    passing PII-shaped strings (e.g. an email address) as ``agent_id``.
    """


def validate_identifier(field_name: str, value: str) -> None:
    """Reject anything that isn't a short technical token, before it reaches processing or evidence."""
    if not isinstance(value, str) or not _IDENTIFIER_PATTERN.match(value):
        raise InvalidIdentifierError(
            f"{field_name} was rejected: expected a short technical identifier "
            "(letters, digits, '-', '_', max 64 chars), not free-form/PII-shaped text."
        )


def _sink_path() -> Path:
    override = os.getenv("CR001_EVIDENCE_PATH")
    return Path(override) if override else _DEFAULT_SINK_PATH


def record_event(event: EvidenceEvent) -> None:
    """Validate and append one event as a JSON line. Never sampled, never skipped."""
    validate_event(event)
    path = _sink_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        # json.dumps serializes tuples (e.g. pii_categories) as arrays natively.
        handle.write(json.dumps(asdict(event)) + "\n")
    _maybe_export_to_app_insights(event)


def read_events(path: Path | str | None = None) -> list[dict]:
    """Read all recorded events from the JSONL sink (or an explicit path)."""
    target = Path(path) if path else _sink_path()
    if not target.exists():
        return []
    events: list[dict] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            events.append(json.loads(line))
    return events


def _maybe_export_to_app_insights(event: EvidenceEvent) -> None:
    """Optional, supplementary exporter -- the JSONL sink stays authoritative.

    Only runs when ``APPLICATIONINSIGHTS_CONNECTION_STRING`` is set. Imports
    are lazy so the demo works with zero extra installs when unset, and any
    exporter failure is swallowed (never blocks or fails the demo) -- this is
    a convenience mirror, not the source of truth for compliance evaluation.
    """
    connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not connection_string:
        return
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor  # type: ignore[import-not-found]
        from opentelemetry import _logs as otel_logs  # type: ignore[import-not-found]
    except ImportError:
        return

    if not getattr(_maybe_export_to_app_insights, "_configured", False):
        configure_azure_monitor(connection_string=connection_string)
        _maybe_export_to_app_insights._configured = True  # type: ignore[attr-defined]

    logger = otel_logs.get_logger("cr001_interop.evidence")
    logger.emit(otel_logs.LogRecord(body=json.dumps(asdict(event))))
