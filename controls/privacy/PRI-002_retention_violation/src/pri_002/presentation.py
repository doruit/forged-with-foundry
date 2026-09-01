"""Self-explaining, deterministic UI text for PRI-002."""

from __future__ import annotations

from .models import RetentionAction, RetentionDecision


ICONS = {
    RetentionAction.COMPLIANT: "✅",
    RetentionAction.REMEDIATION_REQUIRED: "🚨",
    RetentionAction.PROTECTED: "🛡️",
    RetentionAction.BLOCKED: "⛔",
}


def decision_card(decision: RetentionDecision) -> str:
    covered = "Yes" if decision.lifecycle_covered else "No"
    return (
        f"### {ICONS[decision.action]} {decision.record_id} — `{decision.action.value.upper()}`\n\n"
        f"- **Age at projected evaluation time:** {decision.age_days if decision.age_days is not None else 'unknown'} days\n"
        f"- **Retention:** {decision.retention_days if decision.retention_days is not None else 'unknown'} days"
        f" + {decision.grace_days if decision.grace_days is not None else 'unknown'} grace days\n"
        f"- **Lifecycle rule coverage:** {covered}\n"
        f"- **Legal hold / immutable:** {'Yes' if decision.legal_hold or decision.immutable else 'No'}\n"
        f"- **Reason:** {decision.reason}\n\n"
        "_Blob content was not downloaded or sent to the agent._"
    )


def scan_summary(decisions: list[RetentionDecision]) -> str:
    counts = {action: 0 for action in RetentionAction}
    for decision in decisions:
        counts[decision.action] += 1
    return (
        "## PRI-002 deterministic scan complete\n\n"
        f"✅ Compliant: **{counts[RetentionAction.COMPLIANT]}** · "
        f"🚨 Remediation required: **{counts[RetentionAction.REMEDIATION_REQUIRED]}** · "
        f"🛡️ Protected: **{counts[RetentionAction.PROTECTED]}** · "
        f"⛔ Blocked: **{counts[RetentionAction.BLOCKED]}**\n\n"
        "> The control decided from metadata. The agent may explain the result, but cannot "
        "authorize or perform deletion."
    )
