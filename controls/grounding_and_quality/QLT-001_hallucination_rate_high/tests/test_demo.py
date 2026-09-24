"""Prove notification failures cannot change decisions or cause blind resends."""

import json
from pathlib import Path
import sys
from unittest.mock import MagicMock

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from demo import card, notify, save  # noqa: E402
import demo  # noqa: E402

PLATFORM_ID = "it-helpdesk-kb-assistant-platform"
REGIONAL_ID = "it-helpdesk-kb-assistant-regional"
CONTRACTOR_ID = "it-helpdesk-kb-assistant-contractor"


def _agent_measurement(agent_id, *, total, ungrounded, critical_run_ids, average_score):
    return {"agent_id": agent_id, "total": total, "ungrounded": ungrounded,
            "ungrounded_run_ids": ["run-2"] if ungrounded else [],
            "critical_run_ids": critical_run_ids,
            "rate_percent": (ungrounded / total) * 100, "average_score": average_score}


@pytest.fixture
def evidence(tmp_path):
    path = tmp_path / "evidence.json"
    per_agent = {
        PLATFORM_ID: _agent_measurement(PLATFORM_ID, total=3, ungrounded=0, critical_run_ids=[], average_score=0.95),
        REGIONAL_ID: _agent_measurement(REGIONAL_ID, total=3, ungrounded=0, critical_run_ids=[], average_score=0.85),
        CONTRACTOR_ID: _agent_measurement(CONTRACTOR_ID, total=3, ungrounded=1, critical_run_ids=["run-2"], average_score=0.4),
    }
    save(path, {"decision": "quality_review_required", "correlation_id": "synthetic-window",
                "threshold_percent": 5.0, "window": {"number": 3},
                "fleet": {"per_agent": per_agent, "fleet_average_score": 0.73,
                          "best_agent": {"agent_id": PLATFORM_ID, "average_score": 0.95},
                          "worst_agent": {"agent_id": CONTRACTOR_ID, "average_score": 0.4},
                          "any_agent_breach": True},
                "notification": {"status": "not_requested", "delivery_verified": False}})
    return path


@pytest.mark.parametrize("status,expected", [(202, "accepted"), (400, "rejected"), (500, "rejected")])
def test_given_http_response_when_notified_then_decision_unchanged_and_delivery_unverified(evidence, status, expected):
    calls = []
    def post(url, **kwargs):
        calls.append(url)
        assert json.loads(evidence.read_text())["notification"]["status"] == "attempted"
        return httpx.Response(status)

    config = {"QLT001_TEAMS_WEBHOOK_URL": "https://test.logic.azure.com/test"}
    result = notify(evidence, config, post=post)
    repeated = notify(evidence, config, post=post)

    assert result["decision"] == "quality_review_required"
    assert result["notification"]["status"] == expected
    assert result["notification"]["delivery_verified"] is False
    assert repeated == result and len(calls) == 1


def test_given_timeout_when_notified_then_unknown_and_no_retry(evidence):
    calls = []
    def post(url, **kwargs):
        calls.append(url)
        raise httpx.ReadTimeout("private endpoint details")

    config = {"QLT001_TEAMS_WEBHOOK_URL": "https://test.logic.azure.com/test"}
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

    result = demo.record_delivery(evidence, "synthetic-window", "run123", "123456")

    assert result["notification"]["delivery_verified"] is True
    assert result["notification"]["verification_method"].startswith("operator_checked_")


def test_given_unaccepted_attempt_when_receipt_recorded_then_rejected(evidence):
    with pytest.raises(ValueError, match="accepted notification"):
        demo.record_delivery(evidence, "synthetic-window", "run123", "123456")


def test_given_cannot_evaluate_when_notified_then_governance_operations_is_notified(evidence):
    record = json.loads(evidence.read_text())
    record["decision"] = "cannot_evaluate"
    record["reason"] = "evaluation_retrieval_unavailable_or_partial"
    save(evidence, record)

    calls = []
    def post(url, **kwargs):
        calls.append(url)
        return httpx.Response(202)

    result = notify(evidence, {
        "QLT001_GOVERNANCE_TEAMS_WEBHOOK_URL": "https://test.logic.azure.com/governance",
    }, post=post)

    assert result["notification"]["status"] == "accepted"
    assert result["notification"]["recipient_role"] == "AI Governance Operations"
    assert len(calls) == 1
    assert "measurement unavailable" in json.dumps(card(result))


def test_given_quality_review_card_then_red_attention_signal_is_visible(evidence):
    payload = card(json.loads(evidence.read_text()))
    content = payload["attachments"][0]["content"]
    status = content["body"][0]
    icon = status["items"][0]["columns"][0]["items"][0]
    status_text = json.dumps(status, ensure_ascii=False)

    assert status["style"] == "attention"
    assert icon["text"] == "●"
    assert icon["color"] == "attention"
    assert "quality review required" in status_text.lower()


def test_given_healthy_card_then_green_positive_signal_is_visible(evidence):
    record = json.loads(evidence.read_text())
    healthy_per_agent = {
        PLATFORM_ID: _agent_measurement(PLATFORM_ID, total=3, ungrounded=0, critical_run_ids=[], average_score=0.95),
        REGIONAL_ID: _agent_measurement(REGIONAL_ID, total=3, ungrounded=0, critical_run_ids=[], average_score=0.9),
        CONTRACTOR_ID: _agent_measurement(CONTRACTOR_ID, total=3, ungrounded=0, critical_run_ids=[], average_score=0.85),
    }
    record.update(decision="no_review_required", window={"number": 1},
                  fleet={"per_agent": healthy_per_agent, "fleet_average_score": 0.9,
                         "best_agent": {"agent_id": PLATFORM_ID, "average_score": 0.95},
                         "worst_agent": {"agent_id": CONTRACTOR_ID, "average_score": 0.85},
                         "any_agent_breach": False})
    payload = card(record)
    status = payload["attachments"][0]["content"]["body"][0]
    icon = status["items"][0]["columns"][0]["items"][0]
    status_text = json.dumps(status, ensure_ascii=False)

    assert status["style"] == "good"
    assert icon["color"] == "good"
    assert "no sustained fleet hallucination rate breach" in status_text.lower()


def test_given_extra_sensitive_fields_when_card_built_then_not_exported(evidence):
    record = json.loads(evidence.read_text())
    record.update(prompt="private prompt", token="private token", kb_article="private kb content")

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

    notify(evidence, {"QLT001_TEAMS_WEBHOOK_URL": "https://test.logic.azure.com/test",
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

    result = notify(evidence, {"QLT001_TEAMS_WEBHOOK_URL": "https://test.logic.azure.com/test"},
                    post=post, retry_rejected=True)

    assert post.call_count == expected_calls
    if expected_calls:
        assert result["notification"]["previous_attempts"][0]["http_status"] == http_status
