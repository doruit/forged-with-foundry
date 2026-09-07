"""Pure, deterministic PRI-003 DSR SLA evaluation."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

from .models import DSRAction, DSRDecision, DSRPolicy, DSRRecord, DSRStatus

DEFAULT_WARNING_DAYS = 7

_CLOSED_STATUSES = {DSRStatus.COMPLETED, DSRStatus.WITHDRAWN}


def _decision_id(record: DSRRecord, anchor: datetime) -> str:
    material = f"{record.request_id}|{record.etag}|{anchor.isoformat()}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def evaluate_dsr(
    record: DSRRecord,
    policies: dict[str, DSRPolicy],
    evaluated_at: datetime,
    warning_days: int = DEFAULT_WARNING_DAYS,
) -> DSRDecision:
    """Evaluate one DSR record without model reasoning or requester content access."""
    if evaluated_at.tzinfo is None:
        raise ValueError("evaluated_at must be timezone-aware")
    evaluated_at = evaluated_at.astimezone(UTC)
    decision_id = _decision_id(record, evaluated_at)

    policy = policies.get(record.request_type or "")
    if policy is None:
        return DSRDecision(
            decision_id=decision_id,
            control_id="PRI-003",
            action=DSRAction.BLOCKED,
            request_id=record.request_id,
            request_type=record.request_type,
            etag=record.etag,
            due_date=None,
            days_until_due=None,
            resolved=False,
            extension_granted=record.extension_granted,
            reason="DSR request type is missing or unknown; the SLA cannot be evaluated.",
        )

    received_date = record.received_date.astimezone(UTC)
    sla_days = policy.sla_days + (policy.extension_days if record.extension_granted else 0)
    due_date = received_date + timedelta(days=sla_days)
    days_until_due = (due_date - evaluated_at).days

    if record.status in _CLOSED_STATUSES:
        if record.completed_date is None:
            # A closed request with no completion evidence cannot be judged
            # against its deadline; failing closed avoids inferring the
            # outcome from whenever this scan happens to run.
            return DSRDecision(
                decision_id=decision_id,
                control_id="PRI-003",
                action=DSRAction.BLOCKED,
                request_id=record.request_id,
                request_type=policy.request_type,
                etag=record.etag,
                due_date=due_date,
                days_until_due=None,
                resolved=False,
                extension_granted=record.extension_granted,
                reason=(
                    "The request is marked closed but has no completion evidence "
                    "(completed_date); the SLA outcome cannot be determined."
                ),
            )
        completed_at = record.completed_date.astimezone(UTC)
        # Anchor the decision to the completion time, not this scan's clock,
        # so the outcome for an already-closed request never changes on rescan.
        historical_decision_id = _decision_id(record, completed_at)
        resolved_on_time = completed_at <= due_date
        return DSRDecision(
            decision_id=historical_decision_id,
            control_id="PRI-003",
            action=DSRAction.ON_TRACK if resolved_on_time else DSRAction.BREACHED,
            request_id=record.request_id,
            request_type=policy.request_type,
            etag=record.etag,
            due_date=due_date,
            days_until_due=(due_date - completed_at).days,
            resolved=True,
            extension_granted=record.extension_granted,
            reason=(
                "The request was closed within its SLA."
                if resolved_on_time
                else "The request closed after its SLA deadline; recorded for audit."
            ),
        )

    if evaluated_at > due_date:
        return DSRDecision(
            decision_id=decision_id,
            control_id="PRI-003",
            action=DSRAction.BREACHED,
            request_id=record.request_id,
            request_type=policy.request_type,
            etag=record.etag,
            due_date=due_date,
            days_until_due=days_until_due,
            resolved=False,
            extension_granted=record.extension_granted,
            reason="The SLA deadline passed and the request is still open; escalate to the DPO.",
        )

    if (due_date - evaluated_at) <= timedelta(days=warning_days):
        return DSRDecision(
            decision_id=decision_id,
            control_id="PRI-003",
            action=DSRAction.AT_RISK,
            request_id=record.request_id,
            request_type=policy.request_type,
            etag=record.etag,
            due_date=due_date,
            days_until_due=days_until_due,
            resolved=False,
            extension_granted=record.extension_granted,
            reason=f"The SLA deadline is within {warning_days} days; escalate to the DPO now.",
        )

    return DSRDecision(
        decision_id=decision_id,
        control_id="PRI-003",
        action=DSRAction.ON_TRACK,
        request_id=record.request_id,
        request_type=policy.request_type,
        etag=record.etag,
        due_date=due_date,
        days_until_due=days_until_due,
        resolved=False,
        extension_granted=record.extension_granted,
        reason="The request remains within its SLA window.",
    )


def evaluate_extension_request(
    record: DSRRecord, policies: dict[str, DSRPolicy]
) -> tuple[bool, str]:
    """Deterministically decide whether a due-date extension may be granted."""
    policy = policies.get(record.request_type or "")
    if policy is None:
        return False, "DSR request type is missing or unknown; the extension is refused."
    if record.status in _CLOSED_STATUSES:
        return False, (
            "The request is already closed; extending its due date would rewrite "
            "an already-recorded outcome and is refused."
        )
    if record.extension_granted:
        return False, "An extension was already granted; only one extension is permitted."
    if not policy.extension_allowed:
        return False, f"{policy.request_type} requests do not permit an SLA extension."
    return True, f"Extension permitted: {policy.extension_days} additional days."


def fail_closed(request_id: str, reason: str) -> DSRDecision:
    return DSRDecision(
        decision_id=hashlib.sha256(f"{request_id}|{reason}".encode()).hexdigest()[:16],
        control_id="PRI-003",
        action=DSRAction.BLOCKED,
        request_id=request_id,
        request_type=None,
        etag="",
        due_date=None,
        days_until_due=None,
        resolved=False,
        extension_granted=False,
        reason=reason,
    )
