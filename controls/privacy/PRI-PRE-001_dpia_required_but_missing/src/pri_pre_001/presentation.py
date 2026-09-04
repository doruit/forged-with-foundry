"""Self-explaining, deterministic UI text for PRI-PRE-001."""

from __future__ import annotations

from .models import GateAction, GateDecision

ICONS = {
    GateAction.ALLOWED: "✅",
    GateAction.BLOCKED: "🚫",
    GateAction.BLOCKED_UNKNOWN: "⛔",
}


def decision_card(decision: GateDecision) -> str:
    risk = decision.risk_factor_count if decision.risk_factor_count is not None else "unknown"
    return (
        f"### {ICONS[decision.action]} {decision.project_id} — `{decision.action.value.upper()}`\n\n"
        f"- **Risk factor count:** {risk}\n"
        f"- **DPIA required:** {'Yes' if decision.dpia_required else 'No'}\n"
        f"- **DPIA evidence complete:** {'Yes' if decision.evidence_complete else 'No'}\n"
        f"- **Reason:** {decision.reason}\n\n"
        "_No DPIA approver name or report identifier was read or sent to the agent._"
    )


def scan_summary(decisions: list[GateDecision]) -> str:
    counts = {action: 0 for action in GateAction}
    for decision in decisions:
        counts[decision.action] += 1
    return (
        "## PRI-PRE-001 deterministic scan complete\n\n"
        f"✅ Allowed: **{counts[GateAction.ALLOWED]}** · "
        f"🚫 Blocked: **{counts[GateAction.BLOCKED]}** · "
        f"⛔ Blocked (unknown risk): **{counts[GateAction.BLOCKED_UNKNOWN]}**\n\n"
        "> The control decided from metadata. The agent may explain the result, but "
        "the real go-live check is Azure Policy, not the agent."
    )
