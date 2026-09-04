"""Agent Control Specification (ACS) enforcement boundary for PRI-003.

The one-time human approval for an SLA due-date extension is now a real ACS
`pre_tool_call`/`post_tool_call` gate around the guarded Table update, not an
in-memory token registry. Every guarded extension escalates; the Chainlit
"Request extension" button click is the human approval event, and ACS's
`action_identity` binds that approval to the exact tool_call args
(request_id + etag) it evaluated -- the same binding guarantee the removed
`ExtensionApprovalRegistry` gave, now enforced by ACS instead of local
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


class GuardedExtensionPolicyDispatcher:
    """Every guarded due-date extension requires explicit human approval."""

    def evaluate(self, invocation: Mapping[str, JsonValue]) -> Mapping[str, JsonValue]:
        return {
            "decision": Decision.ESCALATE.value,
            "reason": "pri_003_guarded_extension_requires_approval",
        }


@lru_cache(maxsize=1)
def get_control() -> AgentControl:
    """Return the process-wide ACS control instance (stateless; safe to share)."""
    manifest = yaml.safe_load(_MANIFEST_PATH.read_text(encoding="utf-8"))
    return AgentControl.from_native(manifest, policy_dispatcher=GuardedExtensionPolicyDispatcher())


def approved_by_ui_click(
    _intervention_point: InterventionPoint, result: InterventionPointResult
) -> ApprovalResolution:
    """Resolve the escalate verdict raised for a Chainlit-approved extension."""
    return ApprovalResolution.allow(result.action_identity)
