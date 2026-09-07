from datetime import UTC, datetime, timedelta

from src.pri_003.models import DSRAction, DSRPolicy, DSRRecord, DSRStatus
from src.pri_003.policy import evaluate_dsr, evaluate_extension_request

NOW = datetime(2026, 1, 31, tzinfo=UTC)
POLICIES = {
    "access": DSRPolicy("access", sla_days=30, extension_days=60, extension_allowed=True),
    "rectification": DSRPolicy("rectification", sla_days=30, extension_days=60, extension_allowed=True),
    "erasure": DSRPolicy("erasure", sla_days=30, extension_days=0, extension_allowed=False),
}


def record(
    *,
    request_type: str | None,
    received_days_ago: int,
    status: DSRStatus = DSRStatus.OPEN,
    extension_granted: bool = False,
    completed_date: datetime | None = None,
):
    return DSRRecord(
        request_id="synthetic-request",
        request_type=request_type,
        received_date=NOW - timedelta(days=received_days_ago),
        status=status,
        etag='"etag-1"',
        extension_granted=extension_granted,
        completed_date=completed_date,
    )


def test_request_within_sla_is_on_track():
    decision = evaluate_dsr(record(request_type="access", received_days_ago=5), POLICIES, NOW)
    assert decision.action is DSRAction.ON_TRACK


def test_request_near_deadline_is_at_risk():
    decision = evaluate_dsr(
        record(request_type="rectification", received_days_ago=25), POLICIES, NOW
    )
    assert decision.action is DSRAction.AT_RISK


def test_open_request_past_deadline_is_breached():
    decision = evaluate_dsr(record(request_type="erasure", received_days_ago=40), POLICIES, NOW)
    assert decision.action is DSRAction.BREACHED
    assert decision.resolved is False


def test_completed_request_closed_after_deadline_is_breached_and_resolved():
    # Received 50 days ago (30-day SLA, due 20 days before NOW) and completed
    # 15 days after that deadline.
    decision = evaluate_dsr(
        record(
            request_type="access",
            received_days_ago=50,
            status=DSRStatus.COMPLETED,
            completed_date=NOW - timedelta(days=5),
        ),
        POLICIES,
        NOW,
    )
    assert decision.action is DSRAction.BREACHED
    assert decision.resolved is True


def test_completed_request_closed_within_deadline_is_on_track():
    # Received 50 days ago (30-day SLA, due 20 days before NOW) and completed
    # 25 days before that deadline.
    decision = evaluate_dsr(
        record(
            request_type="access",
            received_days_ago=50,
            status=DSRStatus.COMPLETED,
            completed_date=NOW - timedelta(days=45),
        ),
        POLICIES,
        NOW,
    )
    assert decision.action is DSRAction.ON_TRACK
    assert decision.resolved is True


def test_completed_request_without_completion_date_fails_closed():
    decision = evaluate_dsr(
        record(
            request_type="access",
            received_days_ago=50,
            status=DSRStatus.COMPLETED,
        ),
        POLICIES,
        NOW,
    )
    assert decision.action is DSRAction.BLOCKED
    assert decision.resolved is False


def test_closed_request_outcome_is_stable_across_rescans():
    """A closed request's outcome must not depend on when it is rescanned."""
    closed = record(
        request_type="access",
        received_days_ago=50,
        status=DSRStatus.COMPLETED,
        completed_date=NOW - timedelta(days=5),
    )
    today = evaluate_dsr(closed, POLICIES, NOW)
    much_later = evaluate_dsr(closed, POLICIES, NOW + timedelta(days=365))
    assert today.action is much_later.action is DSRAction.BREACHED
    assert today.resolved is much_later.resolved is True
    assert today.decision_id == much_later.decision_id


def test_unknown_request_type_fails_closed():
    decision = evaluate_dsr(
        record(request_type="unknown", received_days_ago=10), POLICIES, NOW
    )
    assert decision.action is DSRAction.BLOCKED
    assert decision.due_date is None


def test_extension_allowed_for_access_without_prior_extension():
    allowed, _ = evaluate_extension_request(
        record(request_type="access", received_days_ago=25), POLICIES
    )
    assert allowed is True


def test_extension_denied_for_erasure():
    allowed, reason = evaluate_extension_request(
        record(request_type="erasure", received_days_ago=40), POLICIES
    )
    assert allowed is False
    assert "erasure" in reason


def test_extension_denied_when_already_granted():
    allowed, reason = evaluate_extension_request(
        record(request_type="access", received_days_ago=25, extension_granted=True), POLICIES
    )
    assert allowed is False
    assert "already granted" in reason


def test_extension_denied_when_request_already_closed():
    allowed, reason = evaluate_extension_request(
        record(request_type="access", received_days_ago=50, status=DSRStatus.COMPLETED),
        POLICIES,
    )
    assert allowed is False
    assert "already closed" in reason


def test_agent_payload_excludes_etag():
    payload = evaluate_dsr(
        record(request_type="access", received_days_ago=5), POLICIES, NOW
    ).safe_dict()
    assert "etag" not in payload
