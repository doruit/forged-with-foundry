"""Agent Control Specification (ACS) enforcement boundary for DAT-PRE-002.

The guarded classify action -- the real, asynchronous
`assignSensitivityLabel` Graph call -- is a real ACS
`pre_tool_call`/`post_tool_call` gate, not an unmediated direct call. Every
guarded classify escalates. The resolver never assumes an approval happened
just because it was called: it requires an explicit, single-use
`ApprovalTicket` created at the moment of the Chainlit "Classify before use"
click, and denies when that ticket is missing, was rejected, has expired, or
has already been consumed by a prior call. ACS's `action_identity` binds the
approval to the exact item id and required label it evaluated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Mapping

import yaml
from agent_control_specification import (
    AgentControl,
    ApprovalResolution,
    ApprovalResolver,
    Decision,
    InterventionPoint,
    InterventionPointResult,
    JsonValue,
)

_MANIFEST_PATH = Path(__file__).resolve().parents[2] / "policy" / "acs_manifest.yaml"
DEFAULT_APPROVAL_TTL = timedelta(minutes=5)


class GuardedClassifyPolicyDispatcher:
    """Every guarded classify action requires explicit human approval."""

    def evaluate(self, invocation: Mapping[str, JsonValue]) -> Mapping[str, JsonValue]:
        return {
            "decision": Decision.ESCALATE.value,
            "reason": "dat_pre_002_guarded_classify_requires_approval",
        }


@lru_cache(maxsize=1)
def get_control() -> AgentControl:
    """Return the process-wide ACS control instance (stateless; safe to share)."""
    manifest = yaml.safe_load(_MANIFEST_PATH.read_text(encoding="utf-8"))
    return AgentControl.from_native(manifest, policy_dispatcher=GuardedClassifyPolicyDispatcher())


@dataclass
class ApprovalTicket:
    """Explicit, single-use evidence that a human approved one guarded classify.

    Created only at the moment of a real approval event (e.g. the Chainlit
    button click), never inferred from which function calls the resolver.
    `claim()` is the single-use gate for the whole guarded action (`run_tool`
    calls the resolver at both `pre_tool_call` and `post_tool_call`, so the
    resolver itself must stay callable more than once per action); a second,
    separate guarded action must claim a new ticket.
    """

    approved: bool
    issued_at: datetime
    ttl: timedelta = DEFAULT_APPROVAL_TTL
    _claimed: bool = field(default=False, init=False, repr=False, compare=False)

    def claim(self) -> bool:
        """Consume this ticket for one guarded action; False if already used."""
        if self._claimed:
            return False
        self._claimed = True
        return True

    def resolver(self) -> ApprovalResolver:
        def _resolve(
            _point: InterventionPoint, result: InterventionPointResult
        ) -> ApprovalResolution:
            if not self.approved:
                return ApprovalResolution.deny()
            if datetime.now(UTC) - self.issued_at > self.ttl:
                return ApprovalResolution.deny()
            return ApprovalResolution.allow(result.action_identity)

        return _resolve


def denied_resolver(
    _point: InterventionPoint, _result: InterventionPointResult
) -> ApprovalResolution:
    """Explicit deny used when no approval ticket exists at all."""
    return ApprovalResolution.deny()


def resolver_for(ticket: "ApprovalTicket | None") -> ApprovalResolver:
    """Build the resolver for one guarded call from its approval ticket, if any."""
    if ticket is None:
        return denied_resolver
    return ticket.resolver()
