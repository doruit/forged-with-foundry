"""ACS policy dispatcher for the AUT-004 emergency stop."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import yaml
from agent_control_specification import AgentControl, Decision, JsonValue

from . import STOP_REASON
from .tools import TOOL_NAMES

MANIFEST_PATH = Path(__file__).resolve().parents[2] / "policy" / "acs_manifest.yaml"
_STATUSES = {"enabled", "disabled", "missing", "invalid", "throttled", "unavailable"}


def _deny(reason: str) -> dict[str, str]:
    return {"decision": Decision.DENY.value, "reason": reason}


def _allow(reason: str) -> dict[str, str]:
    return {"decision": Decision.ALLOW.value, "reason": reason}


def _scope_error(metadata: Any) -> str | None:
    if not isinstance(metadata, dict):
        return "aut_004_scope_missing"
    for key in ("protected_tool", "flag_name", "contract_sha256"):
        value = metadata.get(key)
        if not isinstance(value, str) or not value.strip():
            return "aut_004_scope_missing"
    if metadata["protected_tool"] not in TOOL_NAMES:
        return "aut_004_protected_tool_unknown"
    return None


class EmergencyStopPolicy:
    """Allow the protected tool only when its stop switch reads `enabled`."""

    def evaluate(self, invocation: Mapping[str, JsonValue]) -> Mapping[str, JsonValue]:
        policy_input = invocation.get("input")
        if not isinstance(policy_input, dict):
            return _deny("aut_004_policy_input_missing")
        point = policy_input.get("intervention_point")
        snapshot = policy_input.get("snapshot")
        if not isinstance(snapshot, dict):
            return _deny("aut_004_snapshot_missing")
        metadata = snapshot.get("metadata")
        error = _scope_error(metadata)
        if error:
            return _deny(error)
        if point == "agent_startup":
            return _allow("aut_004_scope_declared")
        if point == "post_tool_call":
            return _allow("aut_004_post_tool_call_recorded")
        if point != "pre_tool_call":
            return _deny("aut_004_unexpected_intervention_point")
        call = snapshot.get("tool_call")
        if not isinstance(call, dict) or not isinstance(call.get("name"), str):
            return _deny("aut_004_tool_call_missing")
        if call["name"] not in TOOL_NAMES:
            return _deny("aut_004_tool_unknown")
        if call["name"] != metadata["protected_tool"]:
            return _allow("aut_004_outside_stop_scope")
        state = snapshot.get("stop_state")
        if not isinstance(state, dict) or state.get("flag_name") != metadata["flag_name"]:
            return _deny("aut_004_stop_state_missing")
        status = state.get("status")
        if status not in _STATUSES:
            return _deny("aut_004_stop_state_invalid")
        if status == "enabled":
            return _allow("aut_004_switch_enabled")
        if status == "disabled":
            return _deny(STOP_REASON)
        return _deny(f"aut_004_stop_state_{status}")


@lru_cache(maxsize=1)
def get_control() -> AgentControl:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    return AgentControl.from_native(manifest, policy_dispatcher=EmergencyStopPolicy())
