"""Agent Control Specification (ACS) enforcement boundary for PRI-004.

Both guarded, destructive actions -- the Data Purge request and the field
suppression policy change -- are real ACS `pre_tool_call`/`post_tool_call`
gates, not bespoke in-memory approval tokens. Every guarded action escalates;
the Chainlit approval button click is the human approval event, and ACS's
`action_identity` binds that approval to the exact tool_call args it
evaluated -- the same binding guarantee the removed `PurgeApprovalRegistry`
and `FieldPolicyApprovalRegistry` gave, now enforced by ACS instead of local
bookkeeping.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Mapping

import yaml
from agent_control_specification import (
    AgentControl,
    ApprovalResolution,
    Decision,
    InterventionPoint,
    InterventionPointResult,
    JsonValue,
)

_MANIFEST_PATH = Path(__file__).resolve().parents[2] / "policy" / "acs_manifest.yaml"


class GuardedActionPolicyDispatcher:
    """Every guarded purge or field-policy change requires explicit approval."""

    def evaluate(self, invocation: Mapping[str, JsonValue]) -> Mapping[str, JsonValue]:
        tool_call = invocation["input"].get("tool_call") or {}
        tool_name = tool_call.get("name", "guarded_action") if isinstance(tool_call, Mapping) else "guarded_action"
        return {
            "decision": Decision.ESCALATE.value,
            "reason": f"pri_004_{tool_name}_requires_approval",
        }


@lru_cache(maxsize=1)
def get_control() -> AgentControl:
    """Return the process-wide ACS control instance (stateless; safe to share)."""
    manifest = yaml.safe_load(_MANIFEST_PATH.read_text(encoding="utf-8"))
    return AgentControl.from_native(manifest, policy_dispatcher=GuardedActionPolicyDispatcher())


def approved_by_ui_click(
    _intervention_point: InterventionPoint, result: InterventionPointResult
) -> ApprovalResolution:
    """Resolve the escalate verdict raised for a Chainlit-approved guarded action."""
    return ApprovalResolution.allow(result.action_identity)
