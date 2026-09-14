"""OPTIONAL: ACS pre_tool_call/post_tool_call gate shared by CR-001's MCP and A2A adapters.

Community-requested extension (see ASSESSMENT.md's optional-extension
section). Reuses the exact ``_ACTION_TO_DECISION`` mapping from core
PRI-001's ``acs_gate.py`` -- this module never re-decides PII policy, it
only re-expresses the already-computed
:class:`~src.pri_001.models.PolicyDecision` as a Verdict at a different ACS
intervention point (``pre_tool_call``/``post_tool_call`` instead of the core
demo's ``input``/``output``). ``pre_tool_call`` always allows: unlike the
core `input` point, there is no PII decision yet at admission time -- the
tool's job *is* to produce one, so the deterministic policy applies only to
`post_tool_call`, after ``mcp_server.py``/``a2a_server.py``'s ``execute()``
callable ran detection and redaction. No ``escalate`` verdict is ever
produced here (this tool has no human-click approval step like
PRI-002/003/004's guarded actions), so ``run_tool(..., approval_resolver=None)``
is sufficient.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Mapping

import yaml
from agent_control_specification import AgentControl, Decision, JsonValue

from src.pri_001.acs_gate import _ACTION_TO_DECISION
from src.pri_001.models import PolicyAction

_MANIFEST_PATH = Path(__file__).resolve().parents[2] / "policy" / "acs_interop_manifest.yaml"


class PiiToolPolicyDispatcher:
    """Admission-only at pre_tool_call; the real PII decision gates post_tool_call.

    ACS passes the manifest's declared ``policy_target`` (not a raw
    ``tool_result`` key) as ``invocation["input"]["policy_target"]["value"]``
    for *both* intervention points -- verified against the installed
    ``agent_control_specification`` runtime, matching PRI-002's
    ``acs_gate.py``. Which point is active is read from
    ``invocation["input"]["intervention_point"]``.
    """

    def evaluate(self, invocation: Mapping[str, JsonValue]) -> Mapping[str, JsonValue]:
        point = invocation["input"].get("intervention_point")
        target = invocation["input"]["policy_target"]["value"]

        if point == "pre_tool_call":
            # No PII decision exists yet at admission time -- the tool's job
            # *is* to produce one.
            return {"decision": Decision.ALLOW.value, "reason": "pri_001_mcp_admission"}

        action_value = target.get("action") if isinstance(target, Mapping) else None
        try:
            action = PolicyAction(action_value)
        except ValueError:
            return {"decision": Decision.DENY.value, "reason": "acs_policy_target_invalid"}

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
            "reason": f"pri_001_mcp_action_{action.value}",
            "message": message,
        }


@lru_cache(maxsize=1)
def get_mcp_control() -> AgentControl:
    """Return the process-wide ACS control instance for the MCP tool gate."""
    manifest = yaml.safe_load(_MANIFEST_PATH.read_text(encoding="utf-8"))
    return AgentControl.from_native(manifest, policy_dispatcher=PiiToolPolicyDispatcher())
