"""One-time human approval tokens bound to an evaluated Blob version."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from .models import Approval, RetentionDecision


class ApprovalError(RuntimeError):
    """Raised when destructive remediation lacks valid human approval."""


class ApprovalRegistry:
    def __init__(self, ttl_minutes: int = 5) -> None:
        self._ttl = timedelta(minutes=ttl_minutes)
        self._approvals: dict[str, Approval] = {}

    def issue(self, decision: RetentionDecision, now: datetime | None = None) -> Approval:
        now = (now or datetime.now(UTC)).astimezone(UTC)
        token = secrets.token_urlsafe(24)
        approval = Approval(
            token=token,
            decision_id=decision.decision_id,
            blob_name=decision.blob_name,
            etag=decision.etag,
            expires_at=now + self._ttl,
        )
        self._approvals[token] = approval
        return approval

    def consume(
        self,
        token: str,
        decision: RetentionDecision,
        now: datetime | None = None,
    ) -> Approval:
        now = (now or datetime.now(UTC)).astimezone(UTC)
        approval = self._approvals.pop(token, None)
        if approval is None:
            raise ApprovalError("Approval is missing, invalid, or already used.")
        if approval.expires_at < now:
            raise ApprovalError("Approval expired; rescan and request approval again.")
        if (
            approval.decision_id != decision.decision_id
            or approval.blob_name != decision.blob_name
            or approval.etag != decision.etag
        ):
            raise ApprovalError("Approval does not match the evaluated Blob version.")
        return approval
