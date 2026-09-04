"""One-time human approval tokens bound to an evaluated PRI-004 decision version."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from .models import FieldPolicyApproval, LogDecision, PurgeApproval


class ApprovalError(RuntimeError):
    """Raised when a guarded action lacks valid, matching human approval."""


class PurgeApprovalRegistry:
    def __init__(self, ttl_minutes: int = 5) -> None:
        self._ttl = timedelta(minutes=ttl_minutes)
        self._grants: dict[str, PurgeApproval] = {}

    def issue(self, decision: LogDecision, now: datetime | None = None) -> PurgeApproval:
        now = (now or datetime.now(UTC)).astimezone(UTC)
        token = secrets.token_urlsafe(24)
        grant = PurgeApproval(
            token=token,
            decision_id=decision.decision_id,
            record_id=decision.record_id,
            message_hash=decision.message_hash,
            expires_at=now + self._ttl,
        )
        self._grants[token] = grant
        return grant

    def consume(
        self,
        token: str,
        decision: LogDecision,
        current_message_hash: str,
        now: datetime | None = None,
    ) -> PurgeApproval:
        now = (now or datetime.now(UTC)).astimezone(UTC)
        grant = self._grants.pop(token, None)
        if grant is None:
            raise ApprovalError("Approval is missing, invalid, or already used.")
        if grant.expires_at < now:
            raise ApprovalError("Approval expired; rescan and request approval again.")
        if (
            grant.decision_id != decision.decision_id
            or grant.record_id != decision.record_id
            or grant.message_hash != decision.message_hash
            or grant.message_hash != current_message_hash
        ):
            raise ApprovalError("Approval does not match the evaluated log record version.")
        return grant


class FieldPolicyApprovalRegistry:
    def __init__(self, ttl_minutes: int = 5) -> None:
        self._ttl = timedelta(minutes=ttl_minutes)
        self._grants: dict[str, FieldPolicyApproval] = {}

    def issue(self, decision: LogDecision, now: datetime | None = None) -> FieldPolicyApproval:
        now = (now or datetime.now(UTC)).astimezone(UTC)
        token = secrets.token_urlsafe(24)
        grant = FieldPolicyApproval(
            token=token,
            decision_id=decision.decision_id,
            field_name=decision.field_name,
            expires_at=now + self._ttl,
        )
        self._grants[token] = grant
        return grant

    def consume(
        self,
        token: str,
        field_name: str,
        now: datetime | None = None,
    ) -> FieldPolicyApproval:
        now = (now or datetime.now(UTC)).astimezone(UTC)
        grant = self._grants.pop(token, None)
        if grant is None:
            raise ApprovalError("Approval is missing, invalid, or already used.")
        if grant.expires_at < now:
            raise ApprovalError("Approval expired; rescan and request approval again.")
        if grant.field_name != field_name:
            raise ApprovalError("Approval does not match the requested field.")
        return grant
