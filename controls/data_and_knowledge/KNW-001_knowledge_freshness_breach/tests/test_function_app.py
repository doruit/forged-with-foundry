import base64
import json
from datetime import UTC, datetime
from pathlib import Path
import sys
from types import SimpleNamespace

import azure.functions as func
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import function_app
from knw001.policy import FreshnessPolicy


OWNER_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
NOW = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)
POLICY = FreshnessPolicy("travel-policy", OWNER_ID, 30, "knw001-v1")


def principal(object_id=OWNER_ID):
    encoded = base64.b64encode(json.dumps({
        "claims": [{"typ": "oid", "val": object_id}]
    }).encode()).decode()
    return encoded


def request(*, identity=OWNER_ID, body=None):
    headers = {}
    if identity is not None:
        headers["X-MS-CLIENT-PRINCIPAL"] = principal(identity)
    payload = body if body is not None else {
        "confirm_review": True,
        "source_etag": '"etag-1"',
        "policy_version": "knw001-v1",
    }
    return func.HttpRequest(
        method="POST",
        url="https://function.example/api/review",
        headers=headers,
        params={},
        route_params={},
        body=json.dumps(payload).encode(),
    )


def setup_review_route(monkeypatch, *, current_etag='"etag-1"'):
    writes = []
    monkeypatch.setenv("KNW001_EASY_AUTH_CONFIGURED", "true")
    blob = SimpleNamespace(
        get_blob_properties=lambda: SimpleNamespace(etag=current_etag, last_modified=NOW)
    )
    reviews = SimpleNamespace(
        upload_blob=lambda **kwargs: writes.append(kwargs)
    )
    monkeypatch.setattr(function_app, "_policy", lambda: POLICY)
    monkeypatch.setattr(
        function_app,
        "_clients",
        lambda: (None, blob, reviews, None, None, None),
    )
    return writes


def test_review_endpoint_records_current_owner_attestation_without_etag_response(monkeypatch):
    writes = setup_review_route(monkeypatch)

    response = function_app.review_source(request())

    assert response.status_code == 201
    result = json.loads(response.get_body())
    assert result["record_id"]
    assert result["source_etag_sha256"]
    assert '"etag-1"' not in response.get_body().decode()
    assert len(writes) == 1


@pytest.mark.parametrize("identity", [None, "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"])
def test_review_endpoint_rejects_missing_or_wrong_owner_before_write(monkeypatch, identity):
    writes = setup_review_route(monkeypatch)

    response = function_app.review_source(request(identity=identity))

    assert response.status_code == 403
    assert writes == []


def test_review_endpoint_fails_closed_when_easy_auth_is_not_configured(monkeypatch):
    monkeypatch.delenv("KNW001_EASY_AUTH_CONFIGURED", raising=False)
    monkeypatch.setattr(
        function_app,
        "_clients",
        lambda: pytest.fail("Azure clients must not be constructed without Easy Auth."),
    )

    response = function_app.review_source(request())

    assert response.status_code == 503


def test_review_endpoint_rejects_stale_etag_without_write(monkeypatch):
    writes = setup_review_route(monkeypatch, current_etag='"etag-2"')

    response = function_app.review_source(request())

    assert response.status_code == 409
    assert writes == []


def test_review_endpoint_rejects_extra_free_text_fields(monkeypatch):
    writes = setup_review_route(monkeypatch)
    body = {
        "confirm_review": True,
        "source_etag": '"etag-1"',
        "policy_version": "knw001-v1",
        "review_notes": "sensitive text",
    }

    response = function_app.review_source(request(body=body))

    assert response.status_code == 400
    assert writes == []


def test_policy_settings_require_all_values_and_parse_age(monkeypatch):
    for name in (
        "KNW001_SOURCE_ID",
        "KNW001_OWNER_OBJECT_ID",
        "KNW001_MAX_REVIEW_AGE_DAYS",
        "KNW001_POLICY_VERSION",
    ):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ValueError, match="KNW001_SOURCE_ID"):
        function_app._policy()

    monkeypatch.setenv("KNW001_SOURCE_ID", "travel-policy")
    monkeypatch.setenv("KNW001_OWNER_OBJECT_ID", OWNER_ID)
    monkeypatch.setenv("KNW001_MAX_REVIEW_AGE_DAYS", "30")
    monkeypatch.setenv("KNW001_POLICY_VERSION", "knw001-v1")

    assert function_app._policy() == POLICY


def test_policy_settings_reject_noninteger_review_age(monkeypatch):
    monkeypatch.setenv("KNW001_SOURCE_ID", "travel-policy")
    monkeypatch.setenv("KNW001_OWNER_OBJECT_ID", OWNER_ID)
    monkeypatch.setenv("KNW001_MAX_REVIEW_AGE_DAYS", "thirty")
    monkeypatch.setenv("KNW001_POLICY_VERSION", "knw001-v1")

    with pytest.raises(ValueError):
        function_app._policy()

NOTIFIER_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
NOTIFICATION = {
    "control_id": "KNW-001",
    "policy_version": "knw001-v1",
    "correlation_id": "run-1",
    "timestamp": "2026-11-05T12:00:00Z",
    "source_id": "travel-policy",
    "decision": {"overall_state": "review_required", "reason": "Review is missing."},
    "accountable_role": "Knowledge Owner",
}


def notification_request(*, identity=NOTIFIER_ID, body=None):
    headers = {"X-MS-CLIENT-PRINCIPAL": principal(identity)} if identity else {}
    return func.HttpRequest(
        method="POST",
        url="https://function.example/api/notifications",
        headers=headers,
        params={},
        route_params={},
        body=json.dumps(NOTIFICATION if body is None else body).encode(),
    )


def setup_inbox(monkeypatch):
    records = []
    monkeypatch.setenv("KNW001_EASY_AUTH_CONFIGURED", "true")
    monkeypatch.setenv("KNW001_NOTIFIER_OBJECT_ID", NOTIFIER_ID)
    monkeypatch.setattr(
        function_app, "_evidence_writer",
        lambda: SimpleNamespace(write=records.append),
    )
    return records


def test_notification_inbox_records_minimized_receipt_from_monitor_identity(monkeypatch):
    records = setup_inbox(monkeypatch)

    response = function_app.notification_inbox(notification_request())

    assert response.status_code == 202
    [record] = records
    assert record["event_type"] == "notification_receipt"
    assert record["correlation_id"] == "run-1"
    assert record["notification_role"] == "Knowledge Owner"
    assert record["overall_state"] == "review_required"
    assert "reason" not in json.dumps(record)


@pytest.mark.parametrize("identity", [None, OWNER_ID])
def test_notification_inbox_rejects_other_senders_before_write(monkeypatch, identity):
    records = setup_inbox(monkeypatch)

    response = function_app.notification_inbox(notification_request(identity=identity))

    assert response.status_code == 403
    assert records == []


def test_notification_inbox_rejects_extra_payload_fields(monkeypatch):
    records = setup_inbox(monkeypatch)

    response = function_app.notification_inbox(
        notification_request(body={**NOTIFICATION, "question": "raw prompt"})
    )

    assert response.status_code == 400
    assert records == []


def test_notification_inbox_fails_closed_without_easy_auth(monkeypatch):
    records = setup_inbox(monkeypatch)
    monkeypatch.delenv("KNW001_EASY_AUTH_CONFIGURED")

    response = function_app.notification_inbox(notification_request())

    assert response.status_code == 503
    assert records == []
