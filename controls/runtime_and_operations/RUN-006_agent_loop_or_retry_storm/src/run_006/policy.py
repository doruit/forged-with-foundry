"""ACS policy dispatcher for RUN-006 loop detection."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import yaml
from agent_control_specification import AgentControl, Decision, JsonValue

from . import LOOP_REASON, STOPPED_REASON
from .fingerprint import fingerprint

MANIFEST_PATH = Path(__file__).resolve().parents[2] / "policy" / "acs_manifest.yaml"
_KINDS = {"admission", "denial", "outcome"}


def _deny(reason: str) -> dict[str, str]:
    return {"decision": Decision.DENY.value, "reason": reason}


def _allow(reason: str) -> dict[str, str]:
    return {"decision": Decision.ALLOW.value, "reason": reason}


def _metadata_error(metadata: Any) -> str | None:
    if not isinstance(metadata, dict):
        return "run_006_metadata_missing"
    if metadata.get("contract_status") != "valid":
        return "run_006_contract_invalid"
    threshold = metadata.get("threshold")
    if threshold is None:
        return "run_006_threshold_undeclared"
    if type(threshold) is not int or threshold < 2:
        return "run_006_threshold_invalid"
    run_id = metadata.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        return "run_006_run_id_missing"
    return None


def _journal_error(entries: Any, run_id: str) -> str | None:
    """Reject journals that are not one ordered, contiguous history of this run.

    A journal truncated at its end cannot be detected; its integrity is
    trusted host state.
    """

    if not isinstance(entries, list):
        return "run_006_journal_missing"
    for expected_seq, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            return "run_006_journal_malformed"
        if entry.get("run_id") != run_id:
            return "run_006_journal_foreign_run"
        if entry.get("seq") != expected_seq:
            return "run_006_journal_out_of_order"
        if entry.get("kind") not in _KINDS or not isinstance(entry.get("fingerprint"), str):
            return "run_006_journal_malformed"
        if entry["kind"] == "outcome" and type(entry.get("progress")) is not bool:
            return "run_006_journal_malformed"
    return None


def _stopped(entries: list[dict[str, Any]]) -> bool:
    return any(entry["kind"] == "denial" and entry.get("reason") == LOOP_REASON for entry in entries)


def attempts_without_progress(entries: list[dict[str, Any]], action: str) -> int:
    """Admitted attempts of this exact action since it last made verified progress.

    Progress on a different action never resets the count, and an
    outcome without verified progress does not reset it.
    """

    count = 0
    for entry in entries:
        if entry["fingerprint"] != action:
            continue
        if entry["kind"] == "admission":
            count += 1
        elif entry["kind"] == "outcome" and entry["progress"]:
            count = 0
    return count


class LoopDetectionPolicy:
    """Deny attempt N of an action that has not progressed, then stop the run."""

    def evaluate(self, invocation: Mapping[str, JsonValue]) -> Mapping[str, JsonValue]:
        policy_input = invocation.get("input")
        if not isinstance(policy_input, dict):
            return _deny("run_006_policy_input_missing")
        point = policy_input.get("intervention_point")
        snapshot = policy_input.get("snapshot")
        if not isinstance(snapshot, dict):
            return _deny("run_006_snapshot_missing")
        metadata = snapshot.get("metadata")
        error = _metadata_error(metadata)
        if error:
            return _deny(error)
        if point == "agent_startup":
            return _allow("run_006_threshold_declared")
        if point in {"post_tool_call", "post_model_call"}:
            return _allow("run_006_post_call_recorded")
        if point not in {"pre_tool_call", "pre_model_call"}:
            return _deny("run_006_unexpected_intervention_point")
        entries = snapshot.get("prior_decisions")
        error = _journal_error(entries, metadata["run_id"])
        if error:
            return _deny(error)
        if _stopped(entries):
            return _deny(STOPPED_REASON)
        if point == "pre_model_call":
            return _allow("run_006_run_active")
        call = snapshot.get("tool_call")
        if not isinstance(call, dict) or not isinstance(call.get("name"), str):
            return _deny("run_006_tool_call_missing")
        action = fingerprint(call["name"], call.get("args"))
        if attempts_without_progress(entries, action) >= metadata["threshold"] - 1:
            return _deny(LOOP_REASON)
        return _allow("run_006_no_loop")


@lru_cache(maxsize=None)
def get_control(telemetry_sink: Any = None) -> AgentControl:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    return AgentControl.from_native(
        manifest, policy_dispatcher=LoopDetectionPolicy(), telemetry_sink=telemetry_sink
    )
