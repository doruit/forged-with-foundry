"""One-time human approval tokens bound to an evaluated DSR record version."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from .models import DSRDecision, ExtensionGrant


class ExtensionApprovalError(RuntimeError):
    """Raised when a due-date extension lacks valid, matching human approval."""


class ExtensionApprovalRegistry:
    def __init__(self, ttl_minutes: int = 5) -> None:
        self._ttl = timedelta(minutes=ttl_minutes)
        self._grants: dict[str, ExtensionGrant] = {}

    def issue(self, decision: DSRDecision, now: datetime | None = None) -> ExtensionGrant:
        now = (now or datetime.now(UTC)).astimezone(UTC)
        token = secrets.token_urlsafe(24)
        grant = ExtensionGrant(
            token=token,
            decision_id=decision.decision_id,
            request_id=decision.request_id,
            etag=decision.etag,
            expires_at=now + self._ttl,
        )
        self._grants[token] = grant
        return grant

    def consume(
        self,
        token: str,
        decision: DSRDecision,
        now: datetime | None = None,
    ) -> ExtensionGrant:
        now = (now or datetime.now(UTC)).astimezone(UTC)
        grant = self._grants.pop(token, None)
        if grant is None:
            raise ExtensionApprovalError("Approval is missing, invalid, or already used.")
        if grant.expires_at < now:
            raise ExtensionApprovalError("Approval expired; rescan and request approval again.")
        if (
            grant.decision_id != decision.decision_id
            or grant.request_id != decision.request_id
            or grant.etag != decision.etag
        ):
            raise ExtensionApprovalError(
                "Approval does not match the evaluated DSR record version."
            )
        return grant
