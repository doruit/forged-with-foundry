"""Minimized RUN-006 evidence: decisions, fingerprints and counts, never arguments or prompts."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import ACCOUNTABLE_ROLE, CONTROL_ID, POLICY_VERSION

_JOURNAL_FIELDS = ("seq", "kind", "tool_name", "reason", "progress")


def _minimized_journal(journal: list[dict[str, object]]) -> list[dict[str, object]]:
    """Replace argument fingerprints with per-run labels (A1, A2, ...).

    A hash of a small argument space (order IDs, ticket IDs) can be reversed
    by guessing, so fingerprints never leave the process.
    """

    labels: dict[object, str] = {}
    minimized = []
    for entry in journal:
        label = labels.setdefault(entry["fingerprint"], f"A{len(labels) + 1}")
        minimized.append({"action": label, **{key: entry[key] for key in _JOURNAL_FIELDS if key in entry}})
    return minimized
GOVERNANCE_ACTIONS = {
    "completed": "none",
    "stopped": "repeated_action_denied_before_execution; later_model_and_tool_calls_denied",
    "not_started": "run_denied_at_agent_startup",
    "aborted": "run_stopped_on_error; admitted_calls_may_have_executed",
}


def build_evidence(
    *,
    run_id: str,
    scenario: str,
    threshold: int | None,
    contract: dict[str, object],
    startup: dict[str, str],
    journal: list[dict[str, object]],
    model_gate: list[dict[str, object]],
    outcome: str,
    executed_calls: int,
    refund_attempts: int,
    notification: dict[str, str],
    source: str,
    correlation: dict[str, object],
    error_class: str | None,
    stopped_at: str | None,
) -> dict[str, Any]:
    return {
        "control_id": CONTROL_ID,
        "policy_version": POLICY_VERSION,
        "timestamp": datetime.now(UTC).isoformat(),
        "correlation_id": run_id,
        "scenario": scenario,
        "signal_source": source,
        "repeat_threshold": threshold,
        "contract": contract,
        "agent_startup": startup,
        "tool_journal": _minimized_journal(journal),
        "model_gate": model_gate,
        "admitted_tool_calls": sum(1 for entry in journal if entry["kind"] == "admission"),
        "executed_tool_calls": executed_calls,
        "refund_attempts_executed": refund_attempts,
        "stopped_at": stopped_at,
        "outcome": outcome,
        "governance_action": GOVERNANCE_ACTIONS[outcome],
        "notification": notification,
        "error_class": error_class,
        "foundry": correlation,
        "accountable_role": ACCOUNTABLE_ROLE,
    }


def write_evidence(directory: Path, evidence: dict[str, Any]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{evidence['scenario']}-{evidence['correlation_id']}.json"
    path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return path
