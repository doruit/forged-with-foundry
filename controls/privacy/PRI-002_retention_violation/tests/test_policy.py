from datetime import UTC, datetime, timedelta

from src.pri_002.models import RetentionAction, RetentionPolicy, RetentionRecord
from src.pri_002.policy import evaluate_retention

NOW = datetime(2026, 1, 31, tzinfo=UTC)
POLICY = RetentionPolicy("customer-conversation-30d", 30, 2)
POLICIES = {POLICY.retention_class: POLICY}


def record(*, age_days: int, lifecycle_covered: bool = True, legal_hold: bool = False):
    return RetentionRecord(
        record_id="synthetic-record",
        blob_name="records/synthetic-record.json",
        etag='"etag-1"',
        last_modified=NOW - timedelta(days=age_days),
        retention_class=POLICY.retention_class,
        lifecycle_tag=POLICY.retention_class if lifecycle_covered else None,
        legal_hold=legal_hold,
    )


def test_record_within_retention_is_compliant():
    decision = evaluate_retention(record(age_days=10), POLICIES, NOW)
    assert decision.action is RetentionAction.COMPLIANT


def test_overdue_mistagged_record_requires_remediation():
    decision = evaluate_retention(
        record(age_days=45, lifecycle_covered=False), POLICIES, NOW
    )
    assert decision.action is RetentionAction.REMEDIATION_REQUIRED
    assert decision.lifecycle_covered is False
    assert "lifecycle tag" in decision.reason


def test_legal_hold_prevents_automatic_deletion():
    decision = evaluate_retention(record(age_days=45, legal_hold=True), POLICIES, NOW)
    assert decision.action is RetentionAction.PROTECTED


def test_unknown_retention_class_fails_closed():
    unknown = RetentionRecord(
        record_id="unknown",
        blob_name="records/unknown.json",
        etag='"etag-2"',
        last_modified=NOW - timedelta(days=45),
        retention_class=None,
        lifecycle_tag=None,
    )
    decision = evaluate_retention(unknown, POLICIES, NOW)
    assert decision.action is RetentionAction.BLOCKED


def test_agent_payload_excludes_blob_locator_and_etag():
    payload = evaluate_retention(record(age_days=45), POLICIES, NOW).safe_dict()
    assert "blob_name" not in payload
    assert "etag" not in payload
