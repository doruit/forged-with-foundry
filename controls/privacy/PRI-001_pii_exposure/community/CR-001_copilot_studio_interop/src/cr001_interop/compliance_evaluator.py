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

Status = str  # "COMPLIANT" | "NON_COMPLIANT" | "CONTROL_FAILED" | "UNVERIFIABLE" | "NO_ACTIVITY"


@dataclass(frozen=True)
class AgentReport:
    agent_id: str
    platform: str
    required_runs: int
    valid_attestations: int
    missing: int
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


def _is_valid_attestation(event: dict, scope: AgentScope, started_at: str, completed_at: str | None) -> bool:
    if event.get("event_name") != "pii.control.evaluated":
        return False
    if event.get("agent_id") != scope.agent_id:
        return False
    if event.get("control_id") != scope.required_control:
        return False
    if event.get("protocol") not in scope.allowed_protocols:
        return False
    if event.get("policy_version") != DEFAULT_POLICY_VERSION:
        return False
    if event.get("decision") not in _VALID_ATTESTATION_DECISIONS:
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
        run_ids = {e["run_id"] for e in started_events}

        if not run_ids:
            reports.append(
                AgentReport(scope.agent_id, scope.platform, 0, 0, 0, 0, 0.0, "NO_ACTIVITY")
            )
            continue

        valid = 0
        missing = 0
        failed = 0
        for started in started_events:
            run_id = started["run_id"]
            completed_at = completed_events.get(run_id)
            run_events = [e for e in events if e.get("run_id") == run_id]

            if any(_has_control_error(e, scope) for e in run_events):
                failed += 1
                continue

            if any(_is_valid_attestation(e, scope, started["timestamp"], completed_at) for e in run_events):
                valid += 1
            else:
                missing += 1

        required_runs = len(run_ids)
        coverage = valid / required_runs if required_runs else 0.0

        if failed:
            status = "CONTROL_FAILED"
        elif missing:
            status = "NON_COMPLIANT"
        elif coverage == 1.0:
            status = "COMPLIANT"
        else:
            status = "UNVERIFIABLE"

        reports.append(
            AgentReport(scope.agent_id, scope.platform, required_runs, valid, missing, failed, coverage, status)
        )

    return reports


def _print_table(reports: list[AgentReport]) -> None:
    header = f"{'Agent':<22}{'Platform':<16}{'Required':<10}{'Valid':<8}{'Missing':<9}{'Failed':<8}{'Coverage':<10}{'Status'}"
    print(header)
    print("-" * len(header))
    for r in reports:
        print(
            f"{r.agent_id:<22}{r.platform:<16}{r.required_runs:<10}{r.valid_attestations:<8}"
            f"{r.missing:<9}{r.failed:<8}{r.coverage:<10.0%}{r.status}"
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
