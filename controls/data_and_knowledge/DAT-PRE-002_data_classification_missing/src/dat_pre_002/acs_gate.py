"""Agent Control Specification (ACS) enforcement boundary for DAT-PRE-002.

The guarded classify action -- the real, asynchronous
`assignSensitivityLabel` Graph call -- is a real ACS
`pre_tool_call`/`post_tool_call` gate, not an unmediated direct call. Every
guarded classify escalates; the Chainlit "Classify before use" button click
is the human approval event, and ACS's `action_identity` binds that approval
to the exact item id and required label it evaluated.
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


class GuardedClassifyPolicyDispatcher:
    """Every guarded classify action requires explicit human approval."""

    def evaluate(self, invocation: Mapping[str, JsonValue]) -> Mapping[str, JsonValue]:
        return {
            "decision": Decision.ESCALATE.value,
            "reason": "dat_pre_002_guarded_classify_requires_approval",
        }


@lru_cache(maxsize=1)
def get_control() -> AgentControl:
    """Return the process-wide ACS control instance (stateless; safe to share)."""
    manifest = yaml.safe_load(_MANIFEST_PATH.read_text(encoding="utf-8"))
    return AgentControl.from_native(manifest, policy_dispatcher=GuardedClassifyPolicyDispatcher())


def approved_by_ui_click(
    _intervention_point: InterventionPoint, result: InterventionPointResult
) -> ApprovalResolution:
    """Resolve the escalate verdict raised for a Chainlit-approved classify action."""
    return ApprovalResolution.allow(result.action_identity)
