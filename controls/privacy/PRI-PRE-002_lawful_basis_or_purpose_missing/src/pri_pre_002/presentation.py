"""Self-explaining, deterministic UI text for PRI-PRE-002."""

from __future__ import annotations

from .models import GateAction, GateDecision

ICONS = {
    GateAction.ALLOWED: "✅",
    GateAction.COMPLIANT: "✅",
    GateAction.FLAGGED: "🚩",
    GateAction.FLAGGED_UNKNOWN: "⛔",
}


def decision_card(decision: GateDecision) -> str:
    return (
        f"### {ICONS[decision.action]} {decision.project_id} — `{decision.action.value.upper()}`\n\n"
        f"- **Processes personal data:** {'Yes' if decision.processes_personal_data else 'No'}\n"
        f"- **Lawful basis valid:** {'Yes' if decision.lawful_basis_valid else 'No'}\n"
        f"- **Purpose documented:** {'Yes' if decision.purpose_documented else 'No'}\n"
        f"- **Reason:** {decision.reason}\n\n"
        "_The raw lawful-basis and purpose id values were not sent to the agent._"
    )


def scan_summary(decisions: list[GateDecision]) -> str:
    counts = {action: 0 for action in GateAction}
    for decision in decisions:
        counts[decision.action] += 1
    return (
        "## PRI-PRE-002 deterministic scan complete\n\n"
        f"✅ Allowed: **{counts[GateAction.ALLOWED]}** · "
        f"✅ Compliant: **{counts[GateAction.COMPLIANT]}** · "
        f"🚩 Flagged: **{counts[GateAction.FLAGGED]}** · "
        f"⛔ Flagged (unknown basis): **{counts[GateAction.FLAGGED_UNKNOWN]}**\n\n"
        "> The control decided from metadata. The agent may explain the result, but "
        "the real remediation flag is Azure Policy's audit evaluation, not the agent."
    )
