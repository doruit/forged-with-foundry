"""Prove notification failures cannot change decisions or cause blind resends."""

import json
from pathlib import Path
import sys

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from demo import card, notify, save
import demo
from unittest.mock import MagicMock


@pytest.fixture
def evidence(tmp_path):
    path = tmp_path / "evidence.json"
    save(path, {"decision": "review_required", "correlation_id": "synthetic-run",
                "owner": "synthetic-owner@contoso.example", "target_percent": 35,
                "threshold_percent": 28, "periods": [
                    {"sequence": 1, "total": 5, "deflected": 1, "percent": 20},
                    {"sequence": 2, "total": 5, "deflected": 1, "percent": 20}],
                "notification": {"status": "not_requested", "delivery_verified": False}})
    return path


@pytest.mark.parametrize("status,expected", [(202, "accepted"), (400, "rejected"), (500, "rejected")])
def test_given_http_response_when_notified_then_decision_unchanged_and_delivery_unverified(evidence, status, expected):
    calls = []
    def post(url, **kwargs):
        calls.append(url)
        assert json.loads(evidence.read_text())["notification"]["status"] == "attempted"
        return httpx.Response(status)

    config = {"VAL001_TEAMS_WEBHOOK_URL": "https://test.logic.azure.com/test"}
    result = notify(evidence, config, post=post)
    repeated = notify(evidence, config, post=post)

    assert result["decision"] == "review_required"
    assert result["notification"]["status"] == expected
    assert result["notification"]["delivery_verified"] is False
    assert repeated == result and len(calls) == 1


def test_given_timeout_when_notified_then_unknown_and_no_retry(evidence):
    calls = []
    def post(url, **kwargs):
        calls.append(url)
        raise httpx.ReadTimeout("private endpoint details")

    config = {"VAL001_TEAMS_WEBHOOK_URL": "https://test.logic.azure.com/test"}
    notify(evidence, config, post=post)
    result = notify(evidence, config, post=post)

    assert result["notification"]["status"] == "delivery_unknown"
    assert len(calls) == 1 and "private endpoint" not in evidence.read_text()


def test_given_crashed_attempt_when_restarted_then_not_resent(evidence):
    record = json.loads(evidence.read_text())
    record["notification"]["status"] = "attempted"
    save(evidence, record)

    assert notify(evidence, {}) == record


def test_given_checked_receipt_when_recorded_then_verification_method_is_explicit(evidence):
    record = json.loads(evidence.read_text())
    record["notification"].update(status="accepted", http_status=202)
    save(evidence, record)

    result = demo.record_delivery(evidence, "synthetic-run", "run123", "123456")

    assert result["notification"]["delivery_verified"] is True
    assert result["notification"]["verification_method"].startswith("operator_checked_")


def test_given_unaccepted_attempt_when_receipt_recorded_then_rejected(evidence):
    with pytest.raises(ValueError, match="accepted notification"):
        demo.record_delivery(evidence, "synthetic-run", "run123", "123456")


@pytest.mark.parametrize("run_id,flow_run_id,message_id", [
    ("different-run", "run123", "123456"),
    ("synthetic-run", "run-123", "123456"),
    ("synthetic-run", "run123", "message-id"),
])
def test_given_untrusted_receipt_identifiers_when_recorded_then_rejected(
        evidence, run_id, flow_run_id, message_id):
    record = json.loads(evidence.read_text())
    record["notification"].update(status="accepted", http_status=202)
    save(evidence, record)

    with pytest.raises(ValueError):
        demo.record_delivery(evidence, run_id, flow_run_id, message_id)

    unchanged = json.loads(evidence.read_text())
    assert unchanged["notification"]["status"] == "accepted"
    assert unchanged["notification"]["delivery_verified"] is False


def test_given_notified_measurement_failure_when_rechecked_then_attempt_is_preserved():
    previous = {"decision": "cannot_evaluate", "notification": {"status": "delivery_unknown"}}
    current = {"decision": "cannot_evaluate", "notification": {"status": "not_requested"}}

    result = demo.preserve_notification(previous, current)

    assert result["notification"]["status"] == "delivery_unknown"


def test_given_failure_notification_when_measurement_recovers_then_history_is_retained():
    previous = {"decision": "cannot_evaluate", "notification": {"status": "accepted"}}
    current = {"decision": "review_required", "notification": {"status": "not_requested"}}

    result = demo.preserve_notification(previous, current)

    assert result["notification"]["status"] == "not_requested"
    assert result["prior_notifications"] == [previous]


def test_given_cannot_evaluate_when_notified_then_governance_operations_is_notified(evidence):
    record = json.loads(evidence.read_text())
    record["decision"] = "cannot_evaluate"
    record["reason"] = "telemetry_query_unavailable_or_partial"
    save(evidence, record)

    calls = []
    def post(url, **kwargs):
        calls.append(url)
        return httpx.Response(202)

    result = notify(evidence, {
        "VAL001_GOVERNANCE_TEAMS_WEBHOOK_URL": "https://test.logic.azure.com/governance",
    }, post=post)

    assert result["notification"]["status"] == "accepted"
    assert result["notification"]["recipient_role"] == "AI Governance Operations"
    assert len(calls) == 1
    assert "KPI measurement unavailable" in json.dumps(card(result))


def test_given_review_required_card_then_red_attention_signal_is_visible(evidence):
    payload = card(json.loads(evidence.read_text()))
    content = payload["attachments"][0]["content"]
    status = content["body"][0]
    icon = status["items"][0]["columns"][0]["items"][0]
    status_text = json.dumps(status, ensure_ascii=False)

    assert status["style"] == "attention"
    assert icon["text"] == "●"
    assert icon["color"] == "attention"
    assert "Value review required" in status_text


def test_given_cannot_evaluate_card_then_remediation_signal_is_visible(evidence):
    record = json.loads(evidence.read_text())
    record.update(decision="cannot_evaluate", reason="incomplete_telemetry")
    payload = card(record)
    content = payload["attachments"][0]["content"]
    status = content["body"][0]
    icon = status["items"][0]["columns"][0]["items"][0]
    status_text = json.dumps(status, ensure_ascii=False)

    assert status["style"] == "warning"
    assert icon["text"] == "⚠"
    assert icon["color"] == "warning"
    assert "Restore the measurement path" in status_text


def test_given_healthy_card_then_green_positive_signal_is_visible(evidence):
    record = json.loads(evidence.read_text())
    record["decision"] = "no_review_required"
    payload = card(record)
    status = payload["attachments"][0]["content"]["body"][0]
    icon = status["items"][0]["columns"][0]["items"][0]
    status_text = json.dumps(status, ensure_ascii=False)

    assert status["style"] == "good"
    assert icon["text"] == "●"
    assert icon["color"] == "good"
    assert "No sustained underperformance" in status_text
    assert "At least one measured period" in status_text


def test_given_extra_sensitive_fields_when_card_built_then_not_exported(evidence):
    record = json.loads(evidence.read_text())
    record.update(prompt="private prompt", token="private token", ticket_text="private ticket")

    assert "private" not in json.dumps(card(record))


def test_given_teams_auth_when_sending_then_audience_retains_trailing_slash(evidence, monkeypatch):
    credential = MagicMock()
    credential.get_token.return_value.token = "synthetic-token"
    credential_context = MagicMock()
    credential_context.__enter__.return_value = credential
    client_context = MagicMock()
    client_context.__enter__.return_value.post.return_value = httpx.Response(202)
    monkeypatch.setattr(demo, "AzureCliCredential", lambda **kwargs: credential_context)
    monkeypatch.setattr(demo.httpx, "Client", lambda **kwargs: client_context)

    notify(evidence, {"VAL001_TEAMS_WEBHOOK_URL": "https://test.logic.azure.com/test",
                      "AZURE_TENANT_ID": "synthetic-tenant"})

    credential.get_token.assert_called_once_with("https://service.flow.microsoft.com//.default")


@pytest.mark.parametrize("status,http_status,expected_calls", [
    ("rejected", 403, 1), ("rejected", 401, 1), ("rejected", 500, 0),
    ("delivery_unknown", None, 0), ("accepted", 202, 0), ("attempted", None, 0),
])
def test_given_explicit_recovery_when_retried_then_only_auth_rejection_is_retryable(
        evidence, status, http_status, expected_calls):
    record = json.loads(evidence.read_text())
    record["notification"].update(status=status, http_status=http_status)
    save(evidence, record)
    post = MagicMock(return_value=httpx.Response(202))

    result = notify(evidence, {"VAL001_TEAMS_WEBHOOK_URL": "https://test.logic.azure.com/test"},
                    post=post, retry_rejected=True)

    assert post.call_count == expected_calls
    if expected_calls:
        assert result["notification"]["previous_attempts"][0]["http_status"] == http_status