"""Self-explaining, deterministic UI text for DAT-PRE-002."""

from __future__ import annotations

from .models import ClassificationAction, ClassificationDecision

ICONS = {
    ClassificationAction.COMPLIANT: "✅",
    ClassificationAction.FLAGGED: "⚠️",
    ClassificationAction.BLOCKED: "⛔",
}


def decision_card(decision: ClassificationDecision) -> str:
    category = decision.content_category or "unknown"
    return (
        f"### {ICONS[decision.action]} {decision.file_name} — `{decision.action.value.upper()}`\n\n"
        f"- **Content category:** {category}\n"
        f"- **Reason:** {decision.reason}\n\n"
        "_File content was never read by the agent or shown here — only the platform's own "
        "sensitivity-label state._"
    )


def scan_summary(decisions: list[ClassificationDecision]) -> str:
    counts = {action: 0 for action in ClassificationAction}
    for decision in decisions:
        counts[decision.action] += 1
    return (
        "## DAT-PRE-002 deterministic scan complete\n\n"
        f"✅ Compliant: **{counts[ClassificationAction.COMPLIANT]}** · "
        f"⚠️ Flagged: **{counts[ClassificationAction.FLAGGED]}** · "
        f"⛔ Blocked: **{counts[ClassificationAction.BLOCKED]}**\n\n"
        "> The control read this from real Microsoft Purview sensitivity-label state through "
        "Microsoft Graph. The agent may explain the result, but cannot classify a file on its own."
    )
