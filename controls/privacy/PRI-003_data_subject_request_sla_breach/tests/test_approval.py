from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from src.pri_003.approval import ExtensionApprovalError, ExtensionApprovalRegistry
from src.pri_003.models import DSRAction, DSRDecision

NOW = datetime(2026, 1, 31, tzinfo=UTC)
DECISION = DSRDecision(
    decision_id="decision-1",
    control_id="PRI-003",
    action=DSRAction.BREACHED,
    request_id="synthetic-request",
    request_type="access",
    etag='"etag-1"',
    due_date=NOW - timedelta(days=13),
    days_until_due=-13,
    resolved=False,
    extension_granted=False,
    reason="Synthetic overdue request.",
)


def test_approval_is_bound_to_exact_record_version_and_one_time_use():
    registry = ExtensionApprovalRegistry()
    grant = registry.issue(DECISION, NOW)
    registry.consume(grant.token, DECISION, NOW)
    with pytest.raises(ExtensionApprovalError, match="already used"):
        registry.consume(grant.token, DECISION, NOW)


def test_mismatched_etag_invalidates_approval():
    registry = ExtensionApprovalRegistry()
    grant = registry.issue(DECISION, NOW)
    changed = replace(DECISION, etag='"etag-2"')
    with pytest.raises(ExtensionApprovalError, match="does not match"):
        registry.consume(grant.token, changed, NOW)


def test_expired_approval_is_rejected():
    registry = ExtensionApprovalRegistry(ttl_minutes=5)
    grant = registry.issue(DECISION, NOW)
    with pytest.raises(ExtensionApprovalError, match="expired"):
        registry.consume(grant.token, DECISION, NOW + timedelta(minutes=6))
