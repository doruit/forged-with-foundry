"""CR-001 per-run compliance evaluator.

Compares an independent run inventory (``agent.run.started``/
``agent.run.completed``, emitted by ``demo_runner.py``) against control
attestations (``pii.control.evaluated``, emitted by the MCP/A2A adapters) to
answer a question endpoint logs alone cannot: was PRI-001 actually evaluated
for *every* required run, not just for the runs that happened to call it?

Run with: ``python -m src.cr001_interop.compliance_evaluator --evidence <path> --policy <path>``
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from .evidence import DEFAULT_POLICY_VERSION, read_events
from .policy_scope import AgentScope, load_agent_scope

_VALID_ATTESTATION_DECISIONS = frozenset({"allow", "redact", "deny"})

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


def _matches_scope_and_decision(event: dict, scope: AgentScope) -> bool:
    """Eligible evidence for this run: right agent/control, allowed protocol, recognized decision.

    Failing this check means the event isn't authorized evidence for this
    scope at all (a real policy violation, e.g. an unapproved protocol) --
    it counts toward ``missing``, not ``unverifiable``.
    """
    return (
        event.get("event_name") == "pii.control.evaluated"
        and event.get("agent_id") == scope.agent_id
        and event.get("control_id") == scope.required_control
        and event.get("protocol") in scope.allowed_protocols
        and event.get("decision") in _VALID_ATTESTATION_DECISIONS
    )


def _is_correlatable(event: dict, started_at: str, completed_at: str | None) -> bool:
    """Policy version and timing must line up, or the evidence can't be trusted for this run."""
    if event.get("policy_version") != DEFAULT_POLICY_VERSION:
        return False
    timestamp = event.get("timestamp", "")
    if timestamp < started_at:
        return False
    if completed_at is not None and timestamp > completed_at:
        return False
    return True


def _has_control_error(event: dict, scope: AgentScope) -> bool:
    return (
        event.get("event_name") == "pii.control.evaluated"
        and event.get("agent_id") == scope.agent_id
        and event.get("control_id") == scope.required_control
        and event.get("decision") == "error"
    )


def _unregistered_agent_reports(events: list[dict], scopes: list[AgentScope]) -> list[AgentReport]:
    """Surface agent_ids seen in evidence with no declared scope, instead of silently dropping them."""
    known_ids = {scope.agent_id for scope in scopes}
    unknown_ids = {
        e["agent_id"]
        for e in events
        if e.get("event_name") == "agent.run.started" and e.get("agent_id") not in known_ids
    }
    reports = []
    for agent_id in sorted(unknown_ids):
        run_ids = {
            e["run_id"]
            for e in events
            if e.get("event_name") == "agent.run.started" and e.get("agent_id") == agent_id
        }
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
        started_events = [
            e for e in events if e.get("event_name") == "agent.run.started" and e.get("agent_id") == scope.agent_id
        ]
        completed_events = {
            e["run_id"]: e["timestamp"]
            for e in events
            if e.get("event_name") == "agent.run.completed" and e.get("agent_id") == scope.agent_id
        }
        # A run_id could in principle have more than one started event (a
        # harness bug, not a real run) -- iterate unique run_ids, using the
        # earliest started timestamp, so such a duplicate can never inflate
        # valid/missing/unverifiable beyond required_runs.
        earliest_started: dict[str, str] = {}
        for started in started_events:
            run_id = started["run_id"]
            timestamp = started["timestamp"]
            if run_id not in earliest_started or timestamp < earliest_started[run_id]:
                earliest_started[run_id] = timestamp

        if not earliest_started:
            reports.append(
                AgentReport(scope.agent_id, scope.platform, 0, 0, 0, 0, 0, 0.0, "NO_ACTIVITY")
            )
            continue

        valid = 0
        missing = 0
        unverifiable = 0
        failed = 0
        for run_id, started_at in earliest_started.items():
            completed_at = completed_events.get(run_id)
            run_events = [e for e in events if e.get("run_id") == run_id]

            if any(_has_control_error(e, scope) for e in run_events):
                failed += 1
                continue

            scoped_events = [e for e in run_events if _matches_scope_and_decision(e, scope)]
            if any(_is_correlatable(e, started_at, completed_at) for e in scoped_events):
                valid += 1
            elif scoped_events:
                unverifiable += 1
            else:
                missing += 1

        required_runs = len(earliest_started)
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
