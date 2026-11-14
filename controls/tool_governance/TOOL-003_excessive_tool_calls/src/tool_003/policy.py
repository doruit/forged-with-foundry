"""ACS policy dispatcher for the TOOL-003 tool-call budget."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import yaml
from agent_control_specification import AgentControl, Decision, JsonValue

MANIFEST_PATH = Path(__file__).resolve().parents[2] / "policy" / "acs_manifest.yaml"


def _deny(reason: str) -> dict[str, str]:
    return {"decision": Decision.DENY.value, "reason": reason}


def _allow(reason: str) -> dict[str, str]:
    return {"decision": Decision.ALLOW.value, "reason": reason}


def _valid_budget(value: Any) -> bool:
    return type(value) is int and value >= 1


def _metadata_error(metadata: Any) -> str | None:
    if not isinstance(metadata, dict):
        return "tool_003_metadata_missing"
    if metadata.get("contract_status") != "valid":
        return "tool_003_contract_invalid"
    task_type = metadata.get("task_type")
    if not isinstance(task_type, str) or not task_type.strip():
        return "tool_003_task_type_missing"
    if "budget" not in metadata or metadata["budget"] is None:
        return "tool_003_budget_undeclared"
    if not _valid_budget(metadata["budget"]):
        return "tool_003_budget_invalid"
    run_id = metadata.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        return "tool_003_run_id_missing"
    return None


def _journal_error(entries: Any, run_id: str) -> str | None:
    """Reject journals that are not one ordered, contiguous history of this run.

    ACS cannot detect a journal truncated at its tail; journal integrity is
    trusted host state. These checks catch the detectable defects.
    """

    if not isinstance(entries, list):
        return "tool_003_journal_missing"
    for expected_seq, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            return "tool_003_journal_malformed"
        if entry.get("run_id") != run_id:
            return "tool_003_journal_foreign_run"
        if entry.get("seq") != expected_seq:
            return "tool_003_journal_out_of_order"
        if entry.get("point") != "pre_tool_call" or entry.get("decision") not in {"allow", "deny"}:
            return "tool_003_journal_malformed"
    return None


class ToolCallBudgetPolicy:
    """Allow a tool call only while admitted calls in the run are below the budget."""

    def evaluate(self, invocation: Mapping[str, JsonValue]) -> Mapping[str, JsonValue]:
        policy_input = invocation.get("input")
        if not isinstance(policy_input, dict):
            return _deny("tool_003_policy_input_missing")
        point = policy_input.get("intervention_point")
        snapshot = policy_input.get("snapshot")
        if not isinstance(snapshot, dict):
            return _deny("tool_003_snapshot_missing")
        metadata = snapshot.get("metadata")
        error = _metadata_error(metadata)
        if error:
            return _deny(error)
        if point == "agent_startup":
            return _allow("tool_003_budget_declared")
        if point == "post_tool_call":
            return _allow("tool_003_post_tool_call_recorded")
        if point != "pre_tool_call":
            return _deny("tool_003_unexpected_intervention_point")
        entries = snapshot.get("prior_decisions")
        error = _journal_error(entries, metadata["run_id"])
        if error:
            return _deny(error)
        admitted = sum(1 for entry in entries if entry["decision"] == "allow")
        if admitted >= metadata["budget"]:
            return _deny("tool_003_budget_exceeded")
        return _allow("tool_003_within_budget")


@lru_cache(maxsize=1)
def get_control() -> AgentControl:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    return AgentControl.from_native(manifest, policy_dispatcher=ToolCallBudgetPolicy())
