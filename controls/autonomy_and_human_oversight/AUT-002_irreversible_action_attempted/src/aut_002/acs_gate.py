"""ACS enforcement boundary for AUT-002."""

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


class IrreversibleActionPolicyDispatcher:
    """Every invocation of the protected tool requires human approval."""

    def evaluate(self, invocation: Mapping[str, JsonValue]) -> Mapping[str, JsonValue]:
        return {
            "decision": Decision.ESCALATE.value,
            "reason": "aut_002_irreversible_action_requires_approval",
            "message": "An Ops Manager must approve this exact action before execution.",
        }


@lru_cache(maxsize=1)
def get_control() -> AgentControl:
    manifest = yaml.safe_load(_MANIFEST_PATH.read_text(encoding="utf-8"))
    return AgentControl.from_native(
        manifest,
        policy_dispatcher=IrreversibleActionPolicyDispatcher(),
    )


@dataclass
class ApprovalTicket:
    """Single-use approval evidence bound to ACS's action identity."""

    approved: bool
    issued_at: datetime
    ttl: timedelta = DEFAULT_APPROVAL_TTL
    _action_identity: str | None = field(default=None, init=False, repr=False)
    _completed: bool = field(default=False, init=False, repr=False)

    def resolver(self) -> ApprovalResolver:
        def _resolve(
            point: InterventionPoint,
            result: InterventionPointResult,
        ) -> ApprovalResolution:
            if (
                self._completed
                or not self.approved
                or datetime.now(UTC) - self.issued_at > self.ttl
            ):
                return ApprovalResolution.deny()

            if point == InterventionPoint.PRE_TOOL_CALL and self._action_identity is None:
                self._action_identity = result.action_identity
            if point == InterventionPoint.PRE_TOOL_CALL and self._action_identity != result.action_identity:
                return ApprovalResolution.deny()

            if point == InterventionPoint.POST_TOOL_CALL:
                if self._action_identity is None:
                    return ApprovalResolution.deny()
                self._completed = True
            return ApprovalResolution.allow(result.action_identity)

        return _resolve


def denied_resolver(
    _point: InterventionPoint,
    _result: InterventionPointResult,
) -> ApprovalResolution:
    """Explicit resolver used when no human approval exists."""

    return ApprovalResolution.deny()


def resolver_for(ticket: ApprovalTicket | None) -> ApprovalResolver:
    if ticket is None:
        return denied_resolver
    return ticket.resolver()