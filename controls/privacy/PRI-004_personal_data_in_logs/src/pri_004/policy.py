"""Pure, deterministic PRI-004 log-PII evaluation and guarded remediation checks."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from .models import LogAction, LogDecision, LogRecord


def compute_message_hash(message: str) -> str:
    """Content guard substituting for Log Analytics' lack of a native ETag."""
    return hashlib.sha256(message.encode("utf-8")).hexdigest()[:16]


def _decision_id(record: LogRecord, message_hash: str, evaluated_at: datetime) -> str:
    material = f"{record.record_id}|{message_hash}|{evaluated_at.isoformat()}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def evaluate_log_entry(
    record: LogRecord,
    pii_categories: tuple[str, ...] | None,
    evaluated_at: datetime,
) -> LogDecision:
    """Evaluate one log record without model reasoning; categories come from a prior scan."""
    if evaluated_at.tzinfo is None:
        raise ValueError("evaluated_at must be timezone-aware")
    evaluated_at = evaluated_at.astimezone(UTC)
    message_hash = compute_message_hash(record.message)
    decision_id = _decision_id(record, message_hash, evaluated_at)

    if record.detector_unavailable or pii_categories is None:
        return LogDecision(
            decision_id=decision_id,
            control_id="PRI-004",
            action=LogAction.BLOCKED,
            record_id=record.record_id,
            field_name=record.field_name,
            message_hash=message_hash,
            pii_categories=(),
            reason="PII detection was unavailable; the record cannot be cleared automatically.",
        )

    if pii_categories:
        return LogDecision(
            decision_id=decision_id,
            control_id="PRI-004",
            action=LogAction.PII_DETECTED,
            record_id=record.record_id,
            field_name=record.field_name,
            message_hash=message_hash,
            pii_categories=pii_categories,
            reason=f"Personal data detected in field '{record.field_name}'.",
        )

    return LogDecision(
        decision_id=decision_id,
        control_id="PRI-004",
        action=LogAction.CLEAN,
        record_id=record.record_id,
        field_name=record.field_name,
        message_hash=message_hash,
        pii_categories=(),
        reason="No personal data detected in this log entry.",
    )


def evaluate_purge_request(decision: LogDecision, current_message_hash: str) -> tuple[bool, str]:
    """Deterministically decide whether a real Data Purge request may be submitted."""
    if decision.action is not LogAction.PII_DETECTED:
        return False, "Only records with detected personal data are eligible for purge."
    if current_message_hash != decision.message_hash:
        return False, (
            "The log record's content no longer matches the evaluated decision; rescan first."
        )
    return True, "Purge permitted for the evaluated, unchanged record."


def evaluate_field_policy_change(field_name: str, already_suppressed: bool) -> tuple[bool, str]:
    """Deterministically decide whether a field-suppression logging policy may be applied."""
    if already_suppressed:
        return False, f"Field '{field_name}' is already suppressed for future ingestion."
    return True, f"Field '{field_name}' will be redacted client-side before future ingestion."


def fail_closed(record_id: str, field_name: str, reason: str) -> LogDecision:
    return LogDecision(
        decision_id=hashlib.sha256(f"{record_id}|{field_name}|{reason}".encode()).hexdigest()[:16],
        control_id="PRI-004",
        action=LogAction.BLOCKED,
        record_id=record_id,
        field_name=field_name,
        message_hash="",
        pii_categories=(),
        reason=reason,
    )
