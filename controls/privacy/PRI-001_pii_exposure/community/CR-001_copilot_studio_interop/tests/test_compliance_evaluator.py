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


def _started(run_id: str, ts: str = "2026-01-01T00:00:00+00:00", trace_id: str = "t1") -> dict:
    return {
        "event_id": f"start-{run_id}",
        "event_name": "agent.run.started",
        "agent_id": "agent-1",
        "platform": "copilot_studio",
        "run_id": run_id,
        "trace_id": trace_id,
        "timestamp": ts,
    }


def _completed(run_id: str, ts: str = "2026-01-01T00:05:00+00:00", trace_id: str = "t1") -> dict:
    return {
        "event_id": f"complete-{run_id}",
        "event_name": "agent.run.completed",
        "agent_id": "agent-1",
        "platform": "copilot_studio",
        "run_id": run_id,
        "trace_id": trace_id,
        "timestamp": ts,
    }


def _attestation(
    run_id: str,
    decision: str = "allow",
    protocol: str = "mcp",
    ts: str = "2026-01-01T00:02:00+00:00",
    event_id: str | None = None,
    trace_id: str = "t1",
) -> dict:
    return {
        "event_id": event_id or f"attest-{run_id}",
        "event_name": "pii.control.evaluated",
        "agent_id": "agent-1",
        "platform": "copilot_studio",
        "run_id": run_id,
        "trace_id": trace_id,
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


def test_stale_policy_version_is_unverifiable_not_missing() -> None:
    events = [
        _started("r1"),
        _attestation("r1", event_id="attest-r1")
        | {"policy_version": "some-older-version"},
        _completed("r1"),
    ]

    [report] = evaluate(events, [_SCOPE])

    assert report.status == "UNVERIFIABLE"
    assert report.unverifiable == 1
    assert report.missing == 0


def test_attestation_outside_run_window_is_unverifiable_not_missing() -> None:
    events = [
        _started("r1"),
        _completed("r1"),
        # Timestamped after the run completed: can't be trusted to belong to this run.
        _attestation("r1", ts="2026-01-01T00:10:00+00:00"),
    ]

    [report] = evaluate(events, [_SCOPE])

    assert report.status == "UNVERIFIABLE"
    assert report.unverifiable == 1


def test_duplicate_started_event_for_same_run_does_not_inflate_counts() -> None:
    events = [
        _started("r1"),
        dict(_started("r1"), event_id="start-r1-duplicate"),
        _attestation("r1"),
        _completed("r1"),
    ]

    [report] = evaluate(events, [_SCOPE])

    assert report.required_runs == 1
    assert report.valid_attestations == 1
    assert report.status == "COMPLIANT"


def test_unregistered_agent_is_reported_not_silently_dropped() -> None:
    events = [
        {
            "event_id": "start-x1",
            "event_name": "agent.run.started",
            "agent_id": "some-typo-d-agent",
            "platform": "copilot_studio",
            "run_id": "x1",
            "timestamp": "2026-01-01T00:00:00+00:00",
        }
    ]

    reports = evaluate(events, [_SCOPE])
    [unregistered] = [r for r in reports if r.agent_id == "some-typo-d-agent"]

    assert unregistered.status == "UNREGISTERED_AGENT"
    assert unregistered.required_runs == 1


def test_start_and_attestation_without_completion_is_unverifiable_not_compliant() -> None:
    """A missing half of the start/completion pair must never read as COMPLIANT."""
    events = [_started("r1"), _attestation("r1")]

    [report] = evaluate(events, [_SCOPE])

    assert report.status == "UNVERIFIABLE"
    assert report.valid_attestations == 0
    assert report.unverifiable == 1


def test_attestation_with_mismatched_trace_id_is_unverifiable_not_compliant() -> None:
    """A full pair with an attestation for a different trace_id is not valid evidence for this run."""
    events = [
        _started("r1", trace_id="t1"),
        _completed("r1", trace_id="t1"),
        _attestation("r1", trace_id="t-someone-elses-run"),
    ]

    [report] = evaluate(events, [_SCOPE])

    assert report.status == "UNVERIFIABLE"
    assert report.valid_attestations == 0
    assert report.unverifiable == 1


def test_orphan_completion_without_start_does_not_disappear() -> None:
    """A second run with only a completion event must still be counted, not silently dropped."""
    events = [
        _started("r1"),
        _attestation("r1"),
        _completed("r1"),
        _completed("r2"),  # No agent.run.started for r2 at all.
    ]

    [report] = evaluate(events, [_SCOPE])

    assert report.required_runs == 2
    assert report.valid_attestations == 1
    assert report.unverifiable == 1
    assert report.status == "UNVERIFIABLE"


def test_attestation_and_completion_without_start_is_not_no_activity() -> None:
    """Real recorded activity for an agent must never be reported as NO_ACTIVITY."""
    events = [_completed("r1"), _attestation("r1")]

    [report] = evaluate(events, [_SCOPE])

    assert report.status != "NO_ACTIVITY"
    assert report.status == "UNVERIFIABLE"
    assert report.required_runs == 1
    assert report.unverifiable == 1


def test_platform_mismatch_is_non_compliant() -> None:
    """An attestation for the wrong platform isn't authorized evidence for this scope."""
    events = [
        _started("r1"),
        _completed("r1"),
        dict(_attestation("r1"), platform="foundry"),
    ]

    [report] = evaluate(events, [_SCOPE])

    assert report.status == "NON_COMPLIANT"
    assert report.missing == 1


def test_orphan_attestation_for_unregistered_agent_is_not_silently_dropped() -> None:
    """An attestation-only orphan for an agent with no declared scope must still surface."""
    events = [
        {
            "event_id": "attest-x1",
            "event_name": "pii.control.evaluated",
            "agent_id": "some-typo-d-agent",
            "platform": "copilot_studio",
            "run_id": "x1",
            "trace_id": "t1",
            "timestamp": "2026-01-01T00:00:00+00:00",
            "control_id": "PRI-001",
            "protocol": "mcp",
            "policy_version": DEFAULT_POLICY_VERSION,
            "decision": "allow",
        }
    ]

    reports = evaluate(events, [_SCOPE])
    [unregistered] = [r for r in reports if r.agent_id == "some-typo-d-agent"]

    assert unregistered.status == "UNREGISTERED_AGENT"
    assert unregistered.required_runs == 1

