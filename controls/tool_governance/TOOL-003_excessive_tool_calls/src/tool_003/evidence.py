"""Minimized TOOL-003 evidence: decisions and counts, never tool arguments or prompts."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import ACCOUNTABLE_ROLE, CONTROL_ID, POLICY_VERSION

_JOURNAL_FIELDS = ("seq", "point", "decision", "tool_name", "reason")


def build_evidence(
    *,
    run_id: str,
    scenario: str,
    task_type: str,
    budget: int | None,
    contract: dict[str, object],
    startup: dict[str, str],
    journal: list[dict[str, object]],
    outcome: str,
    denied_tool: str | None,
    executed_calls: int,
    source: str,
    correlation: dict[str, object],
    error_class: str | None = None,
) -> dict[str, Any]:
    return {
        "control_id": CONTROL_ID,
        "policy_version": POLICY_VERSION,
        "timestamp": datetime.now(UTC).isoformat(),
        "correlation_id": run_id,
        "scenario": scenario,
        "signal_source": source,
        "task_type": task_type,
        "approved_budget": budget,
        "contract": contract,
        "agent_startup": startup,
        "decisions": [{key: entry[key] for key in _JOURNAL_FIELDS} for entry in journal],
        "admitted_calls": sum(1 for entry in journal if entry["decision"] == "allow"),
        "executed_calls": executed_calls,
        "denied_tool": denied_tool,
        "outcome": outcome,
        "governance_action": {
            "completed": "none",
            "handed_off": "over_budget_call_denied_before_execution; workflow_optimization_finding",
            "not_started": "run_denied_at_agent_startup",
            "aborted": "run_stopped_on_error; admitted_calls_may_have_executed",
        }[outcome],
        "error_class": error_class,
        "foundry": correlation,
        "accountable_role": ACCOUNTABLE_ROLE,
    }


def write_evidence(directory: Path, evidence: dict[str, Any]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{evidence['scenario']}-{evidence['correlation_id']}.json"
    path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return path
