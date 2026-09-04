"""Agent Control Specification (ACS) enforcement boundary for PRI-001.

Azure AI Language (see ``text_pii.py`` / ``document_pii.py``) is the
detection signal and ``policy.py`` is where PRI-001's PII policy is decided.
This module is the real intervention-point *enforcement* mechanism: it hands
the already-computed :class:`~pri_001.models.PolicyDecision` to a native
Python ACS policy dispatcher (no OPA/Rego bundle -- ``policy/acs_manifest.yaml``
declares a ``custom`` policy so the Rust runtime calls straight into
:class:`PiiPolicyDispatcher`) and enforces the resulting verdict at the
``input``/``output`` intervention points around the Foundry agent call.

Only the decision's action, count, and category names cross the ACS
boundary -- never raw text or PII entity values.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Mapping

import yaml
from agent_control_specification import (
    AgentControl,
    AgentControlBlocked,
    Decision,
    EnforcementMode,
    InterventionPoint,
    JsonValue,
)

from .models import PolicyAction, PolicyDecision

_MANIFEST_PATH = Path(__file__).resolve().parents[2] / "policy" / "acs_manifest.yaml"

# PRI-001's own policy.py already decided ALLOW / REDACT_AND_ESCALATE / BLOCK.
# ACS re-expresses that decision as a Verdict rather than re-deciding it, so
# the repository keeps exactly one place PII policy is authored while ACS
# becomes the actual gate the content must cross.
_ACTION_TO_DECISION: Mapping[PolicyAction, Decision] = {
    PolicyAction.ALLOW: Decision.ALLOW,
    PolicyAction.REDACT_AND_ESCALATE: Decision.WARN,
    PolicyAction.BLOCK: Decision.DENY,
}


class PiiPolicyDispatcher:
    """Native Python ``PolicyDispatcher`` -- no OPA/Rego bundle required."""

    def evaluate(self, invocation: Mapping[str, JsonValue]) -> Mapping[str, JsonValue]:
        target = invocation["input"]["policy_target"]["value"]
        action_value = target.get("action") if isinstance(target, Mapping) else None
        try:
            action = PolicyAction(action_value)
        except ValueError:
            return {
                "decision": Decision.DENY.value,
                "reason": "acs_policy_target_invalid",
            }

        decision = _ACTION_TO_DECISION[action]
        categories = target.get("categories") or ()
        pii_count = target.get("pii_count") or 0
        message = (
            f"{pii_count} PII occurrence(s) in {', '.join(categories) or 'none'}"
            if decision is Decision.WARN
            else None
        )
        return {
            "decision": decision.value,
            "reason": f"pri_001_action_{action.value}",
            "message": message,
        }


@lru_cache(maxsize=1)
def get_control() -> AgentControl:
    """Return the process-wide ACS control instance.

    ACS is stateless, so one instance safely serves unbounded concurrent
    evaluations across Chainlit sessions.
    """
    manifest = yaml.safe_load(_MANIFEST_PATH.read_text(encoding="utf-8"))
    return AgentControl.from_native(manifest, policy_dispatcher=PiiPolicyDispatcher())


async def enforce_boundary(decision: PolicyDecision, source_type: str) -> PolicyDecision:
    """Evaluate and enforce the ACS intervention point for one PRI-001 decision.

    Returns the decision to use for the UI banner: normally the same
    decision that was passed in, but forced to ``BLOCK`` when ACS itself
    denies -- a real, fail-closed second checkpoint rather than narration.
    """
    point = (
        InterventionPoint.OUTPUT
        if source_type == "agent_output"
        else InterventionPoint.INPUT
    )
    control = get_control()
    snapshot = {
        "pii_scan": {
            "action": decision.action.value,
            "pii_count": decision.pii_count,
            "categories": list(decision.categories),
            "source_type": source_type,
        }
    }
    result = await control.evaluate_intervention_point(point, snapshot)
    try:
        await control.enforce(point, result, EnforcementMode.ENFORCE)
    except AgentControlBlocked:
        return PolicyDecision(
            control_id=decision.control_id,
            action=PolicyAction.BLOCK,
            pii_count=decision.pii_count,
            categories=decision.categories,
            escalate=False,
            reason="Agent Control Specification denied this intervention point.",
        )
    return decision
