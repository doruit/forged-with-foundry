from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from src.pri_004.approval import (
    ApprovalError,
    FieldPolicyApprovalRegistry,
    PurgeApprovalRegistry,
)
from src.pri_004.models import LogAction, LogDecision

NOW = datetime(2026, 9, 4, tzinfo=UTC)
DECISION = LogDecision(
    decision_id="decision-1",
    control_id="PRI-004",
    action=LogAction.PII_DETECTED,
    record_id="pri004-demo-1",
    field_name="Message",
    message_hash="hash-1",
    pii_categories=("PhoneNumber",),
    reason="Synthetic detection.",
)


def test_purge_approval_is_bound_to_exact_record_version_and_one_time_use():
    registry = PurgeApprovalRegistry()
    grant = registry.issue(DECISION, NOW)
    registry.consume(grant.token, DECISION, DECISION.message_hash, NOW)
    with pytest.raises(ApprovalError, match="already used"):
        registry.consume(grant.token, DECISION, DECISION.message_hash, NOW)


def test_purge_approval_rejected_when_current_hash_differs():
    registry = PurgeApprovalRegistry()
    grant = registry.issue(DECISION, NOW)
    with pytest.raises(ApprovalError, match="does not match"):
        registry.consume(grant.token, DECISION, "changed-hash", NOW)


def test_purge_approval_rejected_when_decision_changed():
    registry = PurgeApprovalRegistry()
    grant = registry.issue(DECISION, NOW)
    changed = replace(DECISION, message_hash="different-hash")
    with pytest.raises(ApprovalError, match="does not match"):
        registry.consume(grant.token, changed, changed.message_hash, NOW)


def test_purge_approval_expires():
    registry = PurgeApprovalRegistry(ttl_minutes=5)
    grant = registry.issue(DECISION, NOW)
    with pytest.raises(ApprovalError, match="expired"):
        registry.consume(grant.token, DECISION, DECISION.message_hash, NOW + timedelta(minutes=6))


def test_purge_approval_rejects_unknown_token():
    registry = PurgeApprovalRegistry()
    with pytest.raises(ApprovalError, match="missing"):
        registry.consume("unknown-token", DECISION, DECISION.message_hash, NOW)


def test_field_policy_approval_is_bound_to_field_and_one_time_use():
    registry = FieldPolicyApprovalRegistry()
    grant = registry.issue(DECISION, NOW)
    registry.consume(grant.token, "Message", NOW)
    with pytest.raises(ApprovalError, match="already used"):
        registry.consume(grant.token, "Message", NOW)


def test_field_policy_approval_rejected_for_different_field():
    registry = FieldPolicyApprovalRegistry()
    grant = registry.issue(DECISION, NOW)
    with pytest.raises(ApprovalError, match="does not match"):
        registry.consume(grant.token, "OtherField", NOW)


def test_field_policy_approval_expires():
    registry = FieldPolicyApprovalRegistry(ttl_minutes=5)
    grant = registry.issue(DECISION, NOW)
    with pytest.raises(ApprovalError, match="expired"):
        registry.consume(grant.token, "Message", NOW + timedelta(minutes=6))
