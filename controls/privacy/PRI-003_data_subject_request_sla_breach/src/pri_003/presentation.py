"""Self-explaining, deterministic UI text for PRI-003."""

from __future__ import annotations

from .models import DSRAction, DSRDecision


ICONS = {
    DSRAction.ON_TRACK: "✅",
    DSRAction.AT_RISK: "⚠️",
    DSRAction.BREACHED: "🚨",
    DSRAction.BLOCKED: "⛔",
}


def decision_card(decision: DSRDecision) -> str:
    due = decision.due_date.date().isoformat() if decision.due_date else "unknown"
    days = decision.days_until_due if decision.days_until_due is not None else "unknown"
    return (
        f"### {ICONS[decision.action]} {decision.request_id} — `{decision.action.value.upper()}`\n\n"
        f"- **Request type:** {decision.request_type or 'unknown'}\n"
        f"- **Due date:** {due}\n"
        f"- **Days until due:** {days}\n"
        f"- **Closed already:** {'Yes' if decision.resolved else 'No'}\n"
        f"- **Extension already granted:** {'Yes' if decision.extension_granted else 'No'}\n"
        f"- **Reason:** {decision.reason}\n\n"
        "_No requester name, email, or request content was read or sent to the agent._"
    )


def scan_summary(decisions: list[DSRDecision]) -> str:
    counts = {action: 0 for action in DSRAction}
    for decision in decisions:
        counts[decision.action] += 1
    return (
        "## PRI-003 deterministic scan complete\n\n"
        f"✅ On track: **{counts[DSRAction.ON_TRACK]}** · "
        f"⚠️ At risk: **{counts[DSRAction.AT_RISK]}** · "
        f"🚨 Breached: **{counts[DSRAction.BREACHED]}** · "
        f"⛔ Blocked: **{counts[DSRAction.BLOCKED]}**\n\n"
        "> The control decided from metadata. The agent may explain the result, but cannot "
        "authorize an escalation or an extension."
    )
