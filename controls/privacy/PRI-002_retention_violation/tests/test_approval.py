from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from src.pri_002.approval import ApprovalError, ApprovalRegistry
from src.pri_002.models import RetentionAction, RetentionDecision

NOW = datetime(2026, 1, 31, tzinfo=UTC)
DECISION = RetentionDecision(
    decision_id="decision-1",
    control_id="PRI-002",
    action=RetentionAction.REMEDIATION_REQUIRED,
    record_id="synthetic-record",
    blob_name="records/synthetic-record.json",
    etag='"etag-1"',
    retention_class="customer-conversation-30d",
    retention_days=30,
    grace_days=2,
    age_days=45,
    deadline=NOW - timedelta(days=13),
    lifecycle_covered=False,
    legal_hold=False,
    immutable=False,
    reason="Synthetic overdue record.",
)


def test_approval_is_bound_to_exact_blob_version_and_one_time_use():
    registry = ApprovalRegistry()
    approval = registry.issue(DECISION, NOW)
    registry.consume(approval.token, DECISION, NOW)
    with pytest.raises(ApprovalError, match="already used"):
        registry.consume(approval.token, DECISION, NOW)


def test_mismatched_etag_invalidates_approval():
    registry = ApprovalRegistry()
    approval = registry.issue(DECISION, NOW)
    changed = replace(DECISION, etag='"etag-2"')
    with pytest.raises(ApprovalError, match="does not match"):
        registry.consume(approval.token, changed, NOW)


def test_expired_approval_is_rejected():
    registry = ApprovalRegistry(ttl_minutes=5)
    approval = registry.issue(DECISION, NOW)
    with pytest.raises(ApprovalError, match="expired"):
        registry.consume(approval.token, DECISION, NOW + timedelta(minutes=6))
