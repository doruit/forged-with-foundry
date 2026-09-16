"""CR-001 per-run compliance evaluator.

Compares an independent run inventory (``agent.run.started``/
``agent.run.completed``, emitted by ``demo_runner.py``) against control
attestations (``pii.control.evaluated``, emitted by the MCP/A2A adapters) to
answer a question endpoint logs alone cannot: was PRI-001 actually evaluated
for *every* required run, not just for the runs that happened to call it?

A run is only ever counted ``valid`` when a full, parsed, timezone-aware
start/completion pair exists for it *and* a matching attestation agrees on
agent, platform, control, an allowed protocol, policy version, trace_id, and
falls inside the run's time window. Anything less -- a missing half of the
pair, a mismatched trace_id, a stale policy version, an out-of-window
timestamp -- is insufficient evidence, never a silent COMPLIANT/NO_ACTIVITY.

Run with: ``python -m src.cr001_interop.compliance_evaluator --evidence <path> --policy <path>``
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .evidence import DEFAULT_POLICY_VERSION, read_events
from .policy_scope import AgentScope, load_agent_scope

_VALID_ATTESTATION_DECISIONS = frozenset({"allow", "redact", "deny"})
_RUN_EVENT_NAMES = frozenset({"agent.run.started", "agent.run.completed", "pii.control.evaluated"})

Status = str  # "COMPLIANT" | "NON_COMPLIANT" | "CONTROL_FAILED" | "UNVERIFIABLE" | "NO_ACTIVITY" | "UNREGISTERED_AGENT"


@dataclass(frozen=True)
class AgentReport:
    agent_id: str
    platform: str
    required_runs: int
    valid_attestations: int
    missing: int
    unverifiable: int
    failed: int
    coverage: float
    status: Status


def _dedupe(events: list[dict]) -> list[dict]:
    """Duplicate events must never inflate coverage."""
    seen: set[str] = set()
    deduped: list[dict] = []
    for event in events:
        event_id = event.get("event_id")
        if event_id in seen:
            continue
        seen.add(event_id)
        deduped.append(event)
    return deduped


def _parse_timestamp(value: object) -> datetime | None:
    """Parse an ISO-8601 timestamp into a timezone-aware ``datetime``, or None if unusable.

    Never compare raw timestamp strings -- lexical ordering is not
    guaranteed to match chronological ordering across producers.
    """
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _matches_scope_and_decision(event: dict, scope: AgentScope) -> bool:
    """Eligible evidence for this run: right agent/platform/control, allowed protocol, recognized decision.

    Failing this check means the event isn't authorized evidence for this
    scope at all (a real policy violation, e.g. an unapproved protocol or a
    platform mismatch) -- it counts toward ``missing``, not ``unverifiable``.
    """
    return (
        event.get("event_name") == "pii.control.evaluated"
        and event.get("agent_id") == scope.agent_id
        and event.get("platform") == scope.platform
        and event.get("control_id") == scope.required_control
        and event.get("protocol") in scope.allowed_protocols
        and event.get("decision") in _VALID_ATTESTATION_DECISIONS
    )


def _is_correlated_evidence(
    event: dict, started_at: datetime, completed_at: datetime, reference_trace: str | None
) -> bool:
    """Policy version, trace_id, and timing must all line up, or the evidence can't be trusted for this run."""
    if reference_trace is None or event.get("trace_id") != reference_trace:
        return False
    if event.get("policy_version") != DEFAULT_POLICY_VERSION:
        return False
    timestamp = _parse_timestamp(event.get("timestamp"))
    if timestamp is None:
        return False
    try:
        return started_at <= timestamp <= completed_at
    except TypeError:
        # Naive/aware datetime mismatch: cannot be compared, so it cannot be trusted.
        return False


def _has_control_error(event: dict, scope: AgentScope) -> bool:
    return (
        event.get("event_name") == "pii.control.evaluated"
        and event.get("agent_id") == scope.agent_id
        and event.get("control_id") == scope.required_control
        and event.get("decision") == "error"
    )


def _run_ids_for_agent(events: list[dict], agent_id: str) -> set[str]:
    """Every run_id referencing this agent, across all three event kinds.

    A run_id that only ever appears via ``agent.run.completed`` (no start) or
    only via ``pii.control.evaluated`` (no start/completion at all) is still a
    real orphan run that must be counted and reported, not silently dropped.
    """
    return {
        e["run_id"]
        for e in events
        if e.get("agent_id") == agent_id and e.get("event_name") in _RUN_EVENT_NAMES and e.get("run_id")
    }


def _unregistered_agent_reports(events: list[dict], scopes: list[AgentScope]) -> list[AgentReport]:
    """Surface agent_ids seen in any evidence with no declared scope, instead of silently dropping them."""
    known_ids = {scope.agent_id for scope in scopes}
    unknown_ids = {
        e["agent_id"]
        for e in events
        if e.get("event_name") in _RUN_EVENT_NAMES and e.get("agent_id") and e.get("agent_id") not in known_ids
    }
    reports = []
    for agent_id in sorted(unknown_ids):
        run_ids = _run_ids_for_agent(events, agent_id)
        platform = next(
            (e.get("platform", "") for e in events if e.get("agent_id") == agent_id and e.get("platform")),
            "",
        )
        reports.append(
            AgentReport(agent_id, platform, len(run_ids), 0, 0, 0, 0, 0.0, "UNREGISTERED_AGENT")
        )
    return reports


def evaluate(events: list[dict], scopes: list[AgentScope]) -> list[AgentReport]:
    events = _dedupe(events)
    reports: list[AgentReport] = []

    for scope in scopes:
        run_ids = _run_ids_for_agent(events, scope.agent_id)

        if not run_ids:
            reports.append(
                AgentReport(scope.agent_id, scope.platform, 0, 0, 0, 0, 0, 0.0, "NO_ACTIVITY")
            )
            continue

        valid = 0
        missing = 0
        unverifiable = 0
        failed = 0
        for run_id in sorted(run_ids):
            run_events = [
                e for e in events if e.get("run_id") == run_id and e.get("agent_id") == scope.agent_id
            ]

            if any(_has_control_error(e, scope) for e in run_events):
                failed += 1
                continue

            started_events = [e for e in run_events if e.get("event_name") == "agent.run.started"]
            completed_events = [e for e in run_events if e.get("event_name") == "agent.run.completed"]
            # Duplicate started/completed events for one run_id (a harness bug,
            # not a real second run) collapse to the earliest of each, so they
            # can never inflate valid/missing/unverifiable beyond required_runs.
            started_event = min(started_events, key=lambda e: e.get("timestamp", "")) if started_events else None
            completed_event = (
                min(completed_events, key=lambda e: e.get("timestamp", "")) if completed_events else None
            )

            started_at = _parse_timestamp(started_event["timestamp"]) if started_event else None
            completed_at = _parse_timestamp(completed_event["timestamp"]) if completed_event else None

            reference_trace: str | None = None
            if started_event and completed_event:
                if started_event.get("trace_id") == completed_event.get("trace_id"):
                    reference_trace = started_event.get("trace_id")
                # else: start/completion disagree on trace_id -- untrustworthy, leave None.
            elif started_event:
                reference_trace = started_event.get("trace_id")
            elif completed_event:
                reference_trace = completed_event.get("trace_id")

            has_full_pair = started_at is not None and completed_at is not None
            scoped_events = [e for e in run_events if _matches_scope_and_decision(e, scope)]

            if not has_full_pair:
                # Missing half of the start/completion pair (or an unparsable
                # timestamp): we cannot confirm this run's boundaries at all,
                # so it can never be valid, and calling it "missing" would
                # overstate what we actually know.
                unverifiable += 1
            elif any(
                _is_correlated_evidence(e, started_at, completed_at, reference_trace) for e in scoped_events
            ):
                valid += 1
            elif scoped_events:
                unverifiable += 1
            else:
                missing += 1

        required_runs = len(run_ids)
        coverage = valid / required_runs if required_runs else 0.0

        if failed:
            status = "CONTROL_FAILED"
        elif missing:
            status = "NON_COMPLIANT"
        elif unverifiable:
            status = "UNVERIFIABLE"
        else:
            status = "COMPLIANT"

        reports.append(
            AgentReport(
                scope.agent_id, scope.platform, required_runs, valid, missing, unverifiable, failed, coverage, status
            )
        )

    reports.extend(_unregistered_agent_reports(events, scopes))
    return reports


def _print_table(reports: list[AgentReport]) -> None:
    header = (
        f"{'Agent':<22}{'Platform':<16}{'Required':<10}{'Valid':<8}{'Missing':<9}"
        f"{'Unverif.':<10}{'Failed':<8}{'Coverage':<10}{'Status'}"
    )
    print(header)
    print("-" * len(header))
    for r in reports:
        print(
            f"{r.agent_id:<22}{r.platform:<16}{r.required_runs:<10}{r.valid_attestations:<8}"
            f"{r.missing:<9}{r.unverifiable:<10}{r.failed:<8}{r.coverage:<10.0%}{r.status}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CR-001 per-run PRI-001 compliance evaluator")
    parser.add_argument("--evidence", type=Path, default=None, help="Path to the JSONL evidence sink")
    parser.add_argument("--policy", type=Path, default=None, help="Path to agent_scope.yaml")
    parser.add_argument("--json-out", type=Path, default=None, help="Optional path to write the JSON result")
    args = parser.parse_args(argv)

    events = read_events(args.evidence)
    scopes = load_agent_scope(args.policy)
    reports = evaluate(events, scopes)

    _print_table(reports)

    json_result = [
        {
            "agent_id": r.agent_id,
            "platform": r.platform,
            "required_runs": r.required_runs,
            "valid_attestations": r.valid_attestations,
            "missing": r.missing,
            "unverifiable": r.unverifiable,
            "failed": r.failed,
            "coverage": r.coverage,
            "status": r.status,
        }
        for r in reports
    ]
    if args.json_out:
        args.json_out.write_text(json.dumps(json_result, indent=2), encoding="utf-8")
    else:
        print()
        print(json.dumps(json_result, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
