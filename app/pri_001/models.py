"""Small data contracts shared by the PRI-001 enforcement boundary and UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class PolicyAction(StrEnum):
    ALLOW = "allow"
    REDACT_AND_ESCALATE = "redact_and_escalate"
    BLOCK = "block"


@dataclass(frozen=True)
class PiiFinding:
    """PII metadata safe for UI and audit output; entity values are excluded."""

    category: str
    confidence: float | None = None


@dataclass(frozen=True)
class PolicyDecision:
    control_id: str
    action: PolicyAction
    pii_count: int
    categories: tuple[str, ...]
    escalate: bool
    accountable_role: str = "Privacy Officer"
    reason: str = ""


@dataclass(frozen=True)
class TextEnforcementResult:
    decision: PolicyDecision
    redacted_text: str
    findings: tuple[PiiFinding, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class DocumentEnforcementResult:
    decision: PolicyDecision
    redacted_name: str
    redacted_bytes: bytes
    findings: tuple[PiiFinding, ...] = field(default_factory=tuple)
    safe_text_for_agent: str | None = None
