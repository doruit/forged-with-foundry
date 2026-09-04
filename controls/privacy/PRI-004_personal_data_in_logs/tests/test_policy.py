from datetime import UTC, datetime

from src.pri_004.models import LogAction, LogRecord
from src.pri_004.policy import (
    compute_message_hash,
    evaluate_field_policy_change,
    evaluate_log_entry,
    evaluate_purge_request,
)

NOW = datetime(2026, 9, 4, tzinfo=UTC)


def record(
    *,
    message: str = "user visited the dashboard",
    field_name: str = "Message",
    detector_unavailable: bool = False,
):
    return LogRecord(
        record_id="pri004-demo-1",
        field_name=field_name,
        message=message,
        source="checkout-service",
        time_generated=NOW,
        detector_unavailable=detector_unavailable,
    )


def test_clean_record_has_no_pii():
    decision = evaluate_log_entry(record(), pii_categories=(), evaluated_at=NOW)
    assert decision.action is LogAction.CLEAN


def test_pii_detected_when_categories_present():
    decision = evaluate_log_entry(
        record(message="call me at 555-0100"),
        pii_categories=("PhoneNumber",),
        evaluated_at=NOW,
    )
    assert decision.action is LogAction.PII_DETECTED
    assert decision.pii_categories == ("PhoneNumber",)


def test_detector_unavailable_blocks_regardless_of_categories():
    decision = evaluate_log_entry(
        record(detector_unavailable=True), pii_categories=(), evaluated_at=NOW
    )
    assert decision.action is LogAction.BLOCKED


def test_missing_categories_blocks():
    decision = evaluate_log_entry(record(), pii_categories=None, evaluated_at=NOW)
    assert decision.action is LogAction.BLOCKED


def test_naive_datetime_is_rejected():
    try:
        evaluate_log_entry(record(), pii_categories=(), evaluated_at=datetime(2026, 9, 4))
    except ValueError:
        return
    raise AssertionError("expected ValueError for naive evaluated_at")


def test_purge_allowed_when_hash_matches_and_pii_detected():
    r = record(message="call me at 555-0100")
    decision = evaluate_log_entry(r, pii_categories=("PhoneNumber",), evaluated_at=NOW)
    allowed, _ = evaluate_purge_request(decision, compute_message_hash(r.message))
    assert allowed is True


def test_purge_denied_when_action_not_pii_detected():
    r = record()
    decision = evaluate_log_entry(r, pii_categories=(), evaluated_at=NOW)
    allowed, reason = evaluate_purge_request(decision, compute_message_hash(r.message))
    assert allowed is False
    assert "eligible" in reason


def test_purge_denied_when_hash_mismatch():
    r = record(message="call me at 555-0100")
    decision = evaluate_log_entry(r, pii_categories=("PhoneNumber",), evaluated_at=NOW)
    allowed, reason = evaluate_purge_request(decision, compute_message_hash("changed content"))
    assert allowed is False
    assert "no longer matches" in reason


def test_field_policy_allowed_when_not_already_suppressed():
    allowed, _ = evaluate_field_policy_change("Message", already_suppressed=False)
    assert allowed is True


def test_field_policy_denied_when_already_suppressed():
    allowed, reason = evaluate_field_policy_change("Message", already_suppressed=True)
    assert allowed is False
    assert "already suppressed" in reason


def test_safe_dict_excludes_raw_message():
    decision = evaluate_log_entry(
        record(message="call me at 555-0100"),
        pii_categories=("PhoneNumber",),
        evaluated_at=NOW,
    )
    safe = decision.safe_dict()
    assert "message" not in safe
    assert "message_hash" not in safe
    assert safe["pii_categories"] == ["PhoneNumber"]
