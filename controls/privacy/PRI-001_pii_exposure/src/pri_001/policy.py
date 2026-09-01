"""Deterministic PRI-001 policy evaluation.

Governance is deliberately outside the agent: this module has no model or agent
imports and bases decisions only on structured Azure AI Language results.
"""

from __future__ import annotations

from collections.abc import Iterable

from .models import PiiFinding, PolicyAction, PolicyDecision


def evaluate_pii_policy(findings: Iterable[PiiFinding]) -> PolicyDecision:
    findings = tuple(findings)
    categories = tuple(sorted({finding.category for finding in findings}))
    if findings:
        return PolicyDecision(
            control_id="PRI-001",
            action=PolicyAction.REDACT_AND_ESCALATE,
            pii_count=len(findings),
            categories=categories,
            escalate=True,
            reason="One or more structured PII detections require immediate escalation.",
        )

    return PolicyDecision(
        control_id="PRI-001",
        action=PolicyAction.ALLOW,
        pii_count=0,
        categories=(),
        escalate=False,
        reason="No PII entities were detected.",
    )


def fail_closed(reason: str) -> PolicyDecision:
    return PolicyDecision(
        control_id="PRI-001",
        action=PolicyAction.BLOCK,
        pii_count=0,
        categories=(),
        escalate=False,
        reason=reason,
    )
