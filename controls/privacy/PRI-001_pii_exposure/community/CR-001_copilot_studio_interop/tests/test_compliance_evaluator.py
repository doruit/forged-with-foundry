"""Tests for the CR-001 per-run compliance evaluator."""

from __future__ import annotations

from src.cr001_interop.compliance_evaluator import evaluate
from src.cr001_interop.evidence import DEFAULT_POLICY_VERSION
from src.cr001_interop.policy_scope import AgentScope

_SCOPE = AgentScope(
    agent_id="agent-1",
    platform="copilot_studio",
    required_control="PRI-001",
    coverage_scope="every_run",
    allowed_protocols=("mcp", "a2a"),
)


def _started(run_id: str, ts: str = "2026-01-01T00:00:00+00:00") -> dict:
    return {
        "event_id": f"start-{run_id}",
        "event_name": "agent.run.started",
        "agent_id": "agent-1",
        "run_id": run_id,
        "timestamp": ts,
    }


def _completed(run_id: str, ts: str = "2026-01-01T00:05:00+00:00") -> dict:
    return {
        "event_id": f"complete-{run_id}",
        "event_name": "agent.run.completed",
        "agent_id": "agent-1",
        "run_id": run_id,
        "timestamp": ts,
    }


def _attestation(
    run_id: str,
    decision: str = "allow",
    protocol: str = "mcp",
    ts: str = "2026-01-01T00:02:00+00:00",
    event_id: str | None = None,
) -> dict:
    return {
        "event_id": event_id or f"attest-{run_id}",
        "event_name": "pii.control.evaluated",
        "agent_id": "agent-1",
        "run_id": run_id,
        "timestamp": ts,
        "control_id": "PRI-001",
        "protocol": protocol,
        "policy_version": DEFAULT_POLICY_VERSION,
        "decision": decision,
    }


def test_run_with_valid_attestation_is_compliant() -> None:
    events = [_started("r1"), _attestation("r1"), _completed("r1")]

    [report] = evaluate(events, [_SCOPE])

    assert report.status == "COMPLIANT"
    assert report.coverage == 1.0


def test_started_run_with_no_attestation_is_non_compliant() -> None:
    events = [_started("r1"), _completed("r1")]

    [report] = evaluate(events, [_SCOPE])

    assert report.status == "NON_COMPLIANT"
    assert report.missing == 1


def test_errored_control_is_control_failed() -> None:
    events = [_started("r1"), _attestation("r1", decision="error"), _completed("r1")]

    [report] = evaluate(events, [_SCOPE])

    assert report.status == "CONTROL_FAILED"


def test_deny_decision_counts_as_compliant_not_a_failure() -> None:
    events = [_started("r1"), _attestation("r1", decision="deny"), _completed("r1")]

    [report] = evaluate(events, [_SCOPE])

    assert report.status == "COMPLIANT"


def test_disallowed_protocol_is_non_compliant() -> None:
    events = [_started("r1"), _attestation("r1", protocol="carrier-pigeon"), _completed("r1")]

    [report] = evaluate(events, [_SCOPE])

    assert report.status == "NON_COMPLIANT"


def test_duplicate_events_do_not_inflate_coverage() -> None:
    attestation = _attestation("r1")
    events = [_started("r1"), attestation, dict(attestation), _completed("r1")]

    [report] = evaluate(events, [_SCOPE])

    assert report.valid_attestations == 1
    assert report.status == "COMPLIANT"


def test_multiple_runs_in_one_conversation_evaluated_independently() -> None:
    events = [
        _started("r1"),
        _attestation("r1"),
        _completed("r1"),
        _started("r2"),
        _completed("r2"),
    ]

    [report] = evaluate(events, [_SCOPE])

    assert report.required_runs == 2
    assert report.valid_attestations == 1
    assert report.missing == 1
    assert report.status == "NON_COMPLIANT"


def test_agent_with_no_observed_runs_is_no_activity() -> None:
    [report] = evaluate([], [_SCOPE])

    assert report.status == "NO_ACTIVITY"
