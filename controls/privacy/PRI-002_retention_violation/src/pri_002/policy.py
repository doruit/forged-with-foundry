"""Pure, deterministic PRI-002 retention policy evaluation."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

from .models import RetentionAction, RetentionDecision, RetentionPolicy, RetentionRecord


def _decision_id(record: RetentionRecord, evaluated_at: datetime) -> str:
    material = f"{record.record_id}|{record.etag}|{evaluated_at.isoformat()}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def evaluate_retention(
    record: RetentionRecord,
    policies: dict[str, RetentionPolicy],
    evaluated_at: datetime,
) -> RetentionDecision:
    """Evaluate one record without model reasoning or content access."""
    if evaluated_at.tzinfo is None:
        raise ValueError("evaluated_at must be timezone-aware")
    evaluated_at = evaluated_at.astimezone(UTC)
    decision_id = _decision_id(record, evaluated_at)

    policy = policies.get(record.retention_class or "")
    if policy is None:
        return RetentionDecision(
            decision_id=decision_id,
            control_id="PRI-002",
            action=RetentionAction.BLOCKED,
            record_id=record.record_id,
            blob_name=record.blob_name,
            etag=record.etag,
            retention_class=record.retention_class,
            retention_days=None,
            grace_days=None,
            age_days=None,
            deadline=None,
            lifecycle_covered=False,
            legal_hold=record.legal_hold,
            immutable=record.immutable,
            reason="Retention class is missing or unknown; automatic deletion is blocked.",
        )

    last_modified = record.last_modified.astimezone(UTC)
    age_days = max((evaluated_at - last_modified).days, 0)
    deadline = last_modified + timedelta(
        days=policy.retention_days + policy.grace_days
    )
    lifecycle_covered = record.lifecycle_tag == policy.retention_class

    if record.legal_hold or record.immutable:
        return RetentionDecision(
            decision_id=decision_id,
            control_id="PRI-002",
            action=RetentionAction.PROTECTED,
            record_id=record.record_id,
            blob_name=record.blob_name,
            etag=record.etag,
            retention_class=policy.retention_class,
            retention_days=policy.retention_days,
            grace_days=policy.grace_days,
            age_days=age_days,
            deadline=deadline,
            lifecycle_covered=lifecycle_covered,
            legal_hold=record.legal_hold,
            immutable=record.immutable,
            reason=(
                "The retention deadline passed, but a hold or immutability "
                "protection prevents deletion."
                if evaluated_at > deadline
                else "The record remains protected by a hold or immutability policy."
            ),
        )

    action = (
        RetentionAction.REMEDIATION_REQUIRED
        if evaluated_at > deadline
        else RetentionAction.COMPLIANT
    )
    if action is RetentionAction.REMEDIATION_REQUIRED:
        reason = (
            "The record remains active after its retention period and grace period. "
            + (
                "The lifecycle tag is missing or incorrect, so the Azure lifecycle rule does not cover it."
                if not lifecycle_covered
                else "The lifecycle rule covers it, but the projected enforcement outcome is overdue."
            )
        )
    else:
        reason = (
            "The record is still within its retention period and operational "
            "grace period."
        )

    return RetentionDecision(
        decision_id=decision_id,
        control_id="PRI-002",
        action=action,
        record_id=record.record_id,
        blob_name=record.blob_name,
        etag=record.etag,
        retention_class=policy.retention_class,
        retention_days=policy.retention_days,
        grace_days=policy.grace_days,
        age_days=age_days,
        deadline=deadline,
        lifecycle_covered=lifecycle_covered,
        legal_hold=False,
        immutable=False,
        reason=reason,
    )

def fail_closed(record_id: str, reason: str) -> RetentionDecision:
    return RetentionDecision(
        decision_id=hashlib.sha256(f"{record_id}|{reason}".encode()).hexdigest()[:16],
        control_id="PRI-002",
        action=RetentionAction.BLOCKED,
        record_id=record_id,
        blob_name="",
        etag="",
        retention_class=None,
        retention_days=None,
        grace_days=None,
        age_days=None,
        deadline=None,
        lifecycle_covered=False,
        legal_hold=False,
        immutable=False,
        reason=reason,
    )
