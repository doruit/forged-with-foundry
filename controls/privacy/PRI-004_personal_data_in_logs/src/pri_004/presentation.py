"""Self-explaining, deterministic UI text for PRI-004."""

from __future__ import annotations

from .models import LogAction, LogDecision

ICONS = {
    LogAction.CLEAN: "✅",
    LogAction.PII_DETECTED: "⚠️",
    LogAction.BLOCKED: "⛔",
}


def decision_card(decision: LogDecision) -> str:
    categories = ", ".join(decision.pii_categories) or "none"
    return (
        f"### {ICONS[decision.action]} {decision.record_id} — `{decision.action.value.upper()}`\n\n"
        f"- **Field:** {decision.field_name}\n"
        f"- **PII categories:** {categories}\n"
        f"- **Reason:** {decision.reason}\n\n"
        "_The raw log message was never read by the agent or shown here._"
    )


def scan_summary(decisions: list[LogDecision]) -> str:
    counts = {action: 0 for action in LogAction}
    for decision in decisions:
        counts[decision.action] += 1
    return (
        "## PRI-004 deterministic scan complete\n\n"
        f"✅ Clean: **{counts[LogAction.CLEAN]}** · "
        f"⚠️ PII detected: **{counts[LogAction.PII_DETECTED]}** · "
        f"⛔ Blocked: **{counts[LogAction.BLOCKED]}**\n\n"
        "> The control decided from metadata. The agent may explain the result, but cannot "
        "mask, purge, or change a logging policy on its own."
    )
