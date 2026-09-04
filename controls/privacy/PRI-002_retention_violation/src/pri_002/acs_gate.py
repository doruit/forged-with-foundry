"""Agent Control Specification (ACS) enforcement boundary for PRI-002.

The one-time human approval this demo requires is now a real ACS
`pre_tool_call`/`post_tool_call` gate around the guarded Blob delete, not an
in-memory token registry. Every guarded delete escalates; the Chainlit
"Approve guarded deletion" button click is the human approval event, and by
the time `approved_by_ui_click` runs that click has already happened. ACS
still pins the approval to the exact `action_identity` of the tool_call it
evaluated (a hash of blob_name + etag), so a Blob that changed between scan
and click cannot slip through -- the same binding guarantee the old
`ApprovalRegistry` gave, now enforced by ACS instead of local bookkeeping.
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


class GuardedDeletePolicyDispatcher:
    """Every guarded delete requires explicit human approval."""

    def evaluate(self, invocation: Mapping[str, JsonValue]) -> Mapping[str, JsonValue]:
        return {
            "decision": Decision.ESCALATE.value,
            "reason": "pri_002_guarded_deletion_requires_approval",
        }


@lru_cache(maxsize=1)
def get_control() -> AgentControl:
    """Return the process-wide ACS control instance (stateless; safe to share)."""
    manifest = yaml.safe_load(_MANIFEST_PATH.read_text(encoding="utf-8"))
    return AgentControl.from_native(manifest, policy_dispatcher=GuardedDeletePolicyDispatcher())


def approved_by_ui_click(
    _intervention_point: InterventionPoint, result: InterventionPointResult
) -> ApprovalResolution:
    """Resolve the escalate verdict raised for a Chainlit-approved delete."""
    return ApprovalResolution.allow(result.action_identity)
