import json
import base64
from datetime import UTC, datetime, timedelta
from pathlib import Path
import sys
from types import SimpleNamespace

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from knw001.azure_facts import (
    SEARCH_API_VERSION,
    SEARCH_SCOPE,
    AzureSearchReader,
    collect_freshness_facts,
)
from knw001.auth import authenticated_object_id
from knw001.monitor import BlobEvidenceWriter, HttpNotificationSink, run_monitor
from knw001.policy import (
    BlobSnapshot,
    FreshnessPolicy,
    SearchSnapshot,
    State,
    evaluate_freshness,
)
from knw001.review import (
    create_review_attestation,
    record_review_attestation,
    serialize_review_attestation,
)
from knw001.search_setup import (
    AzureSearchSetup,
    create_read_list_sas,
    search_resources,
)


NOW = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)
SOURCE_ID = "travel-policy"
SOURCE_URI = "https://example.blob.core.windows.net/source/travel-policy.md"
POLICY = FreshnessPolicy(SOURCE_ID, "owner-object-id", 30, "knw001-v1")


class FakeReviews:
    def __init__(self, record):
        self.record = record

    def list_blobs(self, *, name_starts_with):
        assert name_starts_with == f"{SOURCE_ID}/"
        return [SimpleNamespace(name=f"{SOURCE_ID}/review-1.json")]

    def get_blob_client(self, name):
        return SimpleNamespace(
            download_blob=lambda: SimpleNamespace(
                readall=lambda: json.dumps(self.record).encode()
            )
        )


class FakeSearch:
    def __init__(self, snapshot):
        self.result = snapshot

    def snapshot(self, source_uri):
        assert source_uri == SOURCE_URI
        return self.result


def attestation():
    return {
        "source_id": SOURCE_ID,
        "source_etag": '"etag-1"',
        "owner_object_id": "owner-object-id",
        "policy_version": "knw001-v1",
        "recorded_at": "2026-11-04T12:00:00Z",
        "record_id": "review-1",
    }


def test_collected_azure_facts_reach_existing_freshness_policy():
    source, reviews, search = collect_freshness_facts(
        source_id=SOURCE_ID,
        source_uri=SOURCE_URI,
        blob_client=SimpleNamespace(
            get_blob_properties=lambda: SimpleNamespace(etag='"etag-1"', last_modified=NOW)
        ),
        reviews_container=FakeReviews(attestation()),
        search_reader=FakeSearch(SearchSnapshot(True, NOW, "success")),
    )

    result = evaluate_freshness(POLICY, source, reviews, search, NOW)

    assert result.overall_state is State.FRESH
    assert result.source_id == SOURCE_ID
    assert result.index_state is State.CURRENT


def test_expired_blob_valid_until_metadata_triggers_owner_review():
    source, reviews, search = collect_freshness_facts(
        source_id=SOURCE_ID,
        source_uri=SOURCE_URI,
        blob_client=SimpleNamespace(
            get_blob_properties=lambda: SimpleNamespace(
                etag='"etag-1"',
                last_modified=NOW,
                metadata={"valid_until": "2026-11-05T11:59:59Z"},
            )
        ),
        reviews_container=FakeReviews(attestation()),
        search_reader=FakeSearch(SearchSnapshot(True, NOW, "success")),
    )

    result = evaluate_freshness(POLICY, source, reviews, search, NOW)

    assert source.valid_until == datetime(2026, 11, 5, 11, 59, 59, tzinfo=UTC)
    assert result.overall_state is State.REVIEW_REQUIRED
    assert result.index_state is State.CURRENT
    assert "valid-until date has passed" in result.reason


def test_expired_instruction_notifies_owner_and_records_valid_until():
    class EmptyReviews:
        def list_blobs(self, *, name_starts_with):
            return []

    class Evidence:
        def __init__(self):
            self.records = []

        def write(self, record):
            self.records.append(record)

    evidence = Evidence()
    notifications = []
    decision, action = run_monitor(
        policy=POLICY,
        source_id=SOURCE_ID,
        source_uri=SOURCE_URI,
        blob_client=SimpleNamespace(
            get_blob_properties=lambda: SimpleNamespace(
                etag='"etag-1"',
                last_modified=NOW,
                metadata={"valid_until": "2026-11-04T23:59:59Z"},
            )
        ),
        reviews_container=EmptyReviews(),
        search_reader=FakeSearch(SearchSnapshot(True, NOW, "success")),
        evidence_writer=evidence,
        accountable_role="Knowledge Owner",
        notify=lambda payload: notifications.append(payload) or 202,
        evaluated_at=NOW,
        correlation_id="expired-instruction-1",
    )

    assert decision.overall_state is State.REVIEW_REQUIRED
    assert action["status"] == "accepted"
    assert notifications[0]["accountable_role"] == "Knowledge Owner"
    assert evidence.records[0]["source_valid_until"] == "2026-11-04T23:59:59+00:00"


def test_expired_instruction_and_search_outage_notify_owner_and_operator():
    class EmptyReviews:
        def list_blobs(self, *, name_starts_with):
            return []

    class Evidence:
        def __init__(self):
            self.records = []

        def write(self, record):
            self.records.append(record)

    evidence = Evidence()
    notifications = []
    decision, action = run_monitor(
        policy=POLICY,
        source_id=SOURCE_ID,
        source_uri=SOURCE_URI,
        blob_client=SimpleNamespace(
            get_blob_properties=lambda: SimpleNamespace(
                etag='"etag-1"',
                last_modified=NOW,
                metadata={"valid_until": "2026-11-04T23:59:59Z"},
            )
        ),
        reviews_container=EmptyReviews(),
        search_reader=FakeSearch(SearchSnapshot(False, None, None)),
        evidence_writer=evidence,
        accountable_role="Knowledge Owner",
        operator_role="Control Operator",
        notify=lambda payload: notifications.append(payload) or 202,
        evaluated_at=NOW,
        correlation_id="expired-with-search-outage-1",
    )

    assert decision.overall_state is State.CANNOT_EVALUATE
    assert decision.review_state is State.REVIEW_REQUIRED
    assert decision.index_state is State.CANNOT_EVALUATE
    assert [item["accountable_role"] for item in notifications] == [
        "Knowledge Owner", "Control Operator"
    ]
    assert [item["accountable_role"] for item in evidence.records[1:]] == [
        "Knowledge Owner", "Control Operator"
    ]
    assert action["status"] == "accepted"


@pytest.mark.parametrize("metadata", [
    {"valid_until": "not-a-date"},
    {"valid_until": ""},
])
def test_invalid_blob_valid_until_metadata_cannot_be_fresh(metadata):
    source, reviews, search = collect_freshness_facts(
        source_id=SOURCE_ID,
        source_uri=SOURCE_URI,
        blob_client=SimpleNamespace(
            get_blob_properties=lambda: SimpleNamespace(
                etag='"etag-1"', last_modified=NOW, metadata=metadata
            )
        ),
        reviews_container=FakeReviews(attestation()),
        search_reader=FakeSearch(SearchSnapshot(True, NOW, "success")),
    )

    result = evaluate_freshness(POLICY, source, reviews, search, NOW)

    assert result.overall_state is State.CANNOT_EVALUATE
    assert "valid-until metadata is malformed" in result.reason


def test_unreadable_review_record_fails_closed():
    source, reviews, search = collect_freshness_facts(
        source_id=SOURCE_ID,
        source_uri=SOURCE_URI,
        blob_client=SimpleNamespace(
            get_blob_properties=lambda: SimpleNamespace(etag='"etag-1"', last_modified=NOW)
        ),
        reviews_container=FakeReviews({"source_id": SOURCE_ID}),
        search_reader=FakeSearch(SearchSnapshot(True, NOW, "success")),
    )

    result = evaluate_freshness(POLICY, source, reviews, search, NOW)

    assert result.overall_state is State.CANNOT_EVALUATE


def test_blob_or_search_outage_cannot_be_reported_fresh():
    def fail():
        raise RuntimeError("service unavailable")

    source, reviews, search = collect_freshness_facts(
        source_id=SOURCE_ID,
        source_uri=SOURCE_URI,
        blob_client=SimpleNamespace(get_blob_properties=fail),
        reviews_container=FakeReviews(attestation()),
        search_reader=FakeSearch(SearchSnapshot(False, None, None)),
    )

    result = evaluate_freshness(POLICY, source, reviews, search, NOW)

    assert result.overall_state is State.CANNOT_EVALUATE


class FakeCredential:
    def __init__(self):
        self.scope = None

    def get_token(self, scope):
        self.scope = scope
        return SimpleNamespace(token="synthetic-token")


class FakeResponse:
    def __init__(self, body, status_code=200):
        self.body = body
        self.status_code = status_code

    def raise_for_status(self):
        return None

    def json(self):
        return self.body


class FakeHttpClient:
    def __init__(self):
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append(("post", url, kwargs))
        return FakeResponse({"value": [{
            "source_uri": SOURCE_URI,
            "metadata_storage_last_modified": "2026-11-05T12:00:00Z",
        }]})

    def get(self, url, **kwargs):
        self.calls.append(("get", url, kwargs))
        return FakeResponse({"lastResult": {"status": "success", "errors": []}})

    def put(self, url, **kwargs):
        self.calls.append(("put", url, kwargs))
        return FakeResponse({})


def test_search_reader_uses_entra_and_requests_per_source_metadata():
    credential = FakeCredential()
    client = FakeHttpClient()
    reader = AzureSearchReader(
        "https://search.example", "knowledge", "knowledge-indexer", credential, client=client
    )

    result = reader.snapshot(SOURCE_URI)

    assert result == SearchSnapshot(True, NOW, "success", indexer_has_item_errors=False)
    assert credential.scope == SEARCH_SCOPE
    method, url, request = client.calls[0]
    assert method == "post"
    assert url.endswith("/indexes/knowledge/docs/search")
    assert request["params"]["api-version"] == SEARCH_API_VERSION
    assert request["headers"]["Authorization"] == "Bearer synthetic-token"
    assert request["json"]["filter"] == f"source_uri eq '{SOURCE_URI}'"


def test_search_reader_fails_closed_when_path_is_ambiguous():
    class AmbiguousClient(FakeHttpClient):
        def post(self, url, **kwargs):
            return FakeResponse({"value": [
                {"metadata_storage_path": SOURCE_URI},
                {"source_uri": SOURCE_URI},
            ]})

    reader = AzureSearchReader(
        "https://search.example", "knowledge", "knowledge-indexer",
        FakeCredential(), client=AmbiguousClient(),
    )

    assert reader.snapshot(SOURCE_URI) == SearchSnapshot(False, None, None)


def test_review_attestation_binds_authenticated_owner_current_etag_and_policy():
    source = BlobSnapshot(SOURCE_ID, '"etag-1"', NOW)

    review = create_review_attestation(
        policy=POLICY,
        source=source,
        authenticated_owner_object_id="owner-object-id",
        submitted_etag='"etag-1"',
        submitted_policy_version="knw001-v1",
        recorded_at=NOW,
        record_id="review-1",
    )

    assert review.recorded_at == NOW
    assert serialize_review_attestation(review) == {
        "source_id": SOURCE_ID,
        "source_etag": '"etag-1"',
        "owner_object_id": "owner-object-id",
        "policy_version": "knw001-v1",
        "recorded_at": "2026-11-05T12:00:00Z",
        "record_id": "review-1",
    }


def test_review_attestation_rejects_wrong_owner_etag_or_policy():
    source = BlobSnapshot(SOURCE_ID, '"etag-1"', NOW)
    args = {
        "policy": POLICY,
        "source": source,
        "authenticated_owner_object_id": "owner-object-id",
        "submitted_etag": '"etag-1"',
        "submitted_policy_version": "knw001-v1",
    }

    with pytest.raises(PermissionError):
        create_review_attestation(**{**args, "authenticated_owner_object_id": "other-owner"})
    with pytest.raises(ValueError, match="source changed"):
        create_review_attestation(**{**args, "submitted_etag": '"etag-2"'})
    with pytest.raises(ValueError, match="different policy"):
        create_review_attestation(**{**args, "submitted_policy_version": "old-policy"})


def test_record_review_writes_only_after_reading_current_blob_properties():
    writes = []
    blob = SimpleNamespace(
        get_blob_properties=lambda: SimpleNamespace(etag='"etag-1"', last_modified=NOW)
    )
    reviews = SimpleNamespace(upload_blob=lambda **kwargs: writes.append(kwargs))

    attestation = record_review_attestation(
        policy=POLICY,
        blob_client=blob,
        reviews_container=reviews,
        authenticated_owner_object_id="owner-object-id",
        submitted_etag='"etag-1"',
        submitted_policy_version="knw001-v1",
        recorded_at=NOW,
        record_id="review-1",
    )

    assert attestation.record_id == "review-1"
    assert writes[0]["name"] == f"{SOURCE_ID}/review-1.json"
    assert writes[0]["overwrite"] is False
    assert "review notes" not in writes[0]["data"]


def test_record_review_does_not_write_if_source_revision_changed():
    writes = []
    blob = SimpleNamespace(
        get_blob_properties=lambda: SimpleNamespace(etag='"etag-2"', last_modified=NOW)
    )
    reviews = SimpleNamespace(upload_blob=lambda **kwargs: writes.append(kwargs))

    with pytest.raises(ValueError, match="source changed"):
        record_review_attestation(
            policy=POLICY,
            blob_client=blob,
            reviews_container=reviews,
            authenticated_owner_object_id="owner-object-id",
            submitted_etag='"etag-1"',
            submitted_policy_version="knw001-v1",
            recorded_at=NOW,
            record_id="review-1",
        )

    assert writes == []


def test_easyauth_principal_provides_canonical_entra_object_id():
    principal = base64.b64encode(json.dumps({
        "claims": [{
            "typ": "http://schemas.microsoft.com/identity/claims/objectidentifier",
            "val": "Aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        }]
    }).encode()).decode()

    assert authenticated_object_id(principal) == "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


@pytest.mark.parametrize("principal", [
    None,
    "not-base64",
    base64.b64encode(b"[]").decode(),
    base64.b64encode(json.dumps({"claims": []}).encode()).decode(),
    base64.b64encode(json.dumps({"claims": [{"typ": "oid", "val": "not-a-uuid"}]}).encode()).decode(),
    base64.b64encode(json.dumps({"claims": [None]}).encode()).decode(),
])
def test_invalid_or_missing_easyauth_identity_is_rejected(principal):
    with pytest.raises(PermissionError):
        authenticated_object_id(principal)


def test_multiple_distinct_object_id_claims_are_rejected():
    principal = base64.b64encode(json.dumps({
        "claims": [
            {"typ": "oid", "val": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"},
            {"typ": "oid", "val": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"},
        ]
    }).encode()).decode()

    with pytest.raises(PermissionError):
        authenticated_object_id(principal)


def test_nonfresh_decision_persists_minimized_evidence_and_acceptance_event():
    class EmptyReviews:
        def list_blobs(self, *, name_starts_with):
            return []

    class Evidence:
        def __init__(self):
            self.records = []

        def write(self, record):
            self.records.append(record)

    sent = []
    evidence = Evidence()
    decision, action = run_monitor(
        policy=POLICY,
        source_id=SOURCE_ID,
        source_uri=SOURCE_URI,
        blob_client=SimpleNamespace(
            get_blob_properties=lambda: SimpleNamespace(etag='"etag-1"', last_modified=NOW)
        ),
        reviews_container=EmptyReviews(),
        search_reader=FakeSearch(SearchSnapshot(True, NOW, "success")),
        evidence_writer=evidence,
        accountable_role="Knowledge Owner",
        notify=lambda payload: sent.append(payload) or 202,
        evaluated_at=NOW,
        correlation_id="correlation-1",
    )

    assert decision.overall_state is State.REVIEW_REQUIRED
    assert action["status"] == "accepted"
    assert action["notifications"] == [{
        "status": "accepted",
        "http_status": 202,
        "notification_role": "Knowledge Owner",
    }]
    assert [record["event_type"] for record in evidence.records] == [
        "freshness_decision", "notification_outcome"
    ]
    decision_record = evidence.records[0]
    assert decision_record["source_etag_sha256"]
    assert '"etag-1"' not in json.dumps(decision_record)
    assert SOURCE_URI not in json.dumps(decision_record)
    assert decision_record["accountable_role"] == "Knowledge Owner"
    assert sent[0]["correlation_id"] == "correlation-1"
    assert '"etag-1"' not in json.dumps(sent[0])
    assert "delivered" not in action["status"]


def test_index_lag_notification_routes_to_operator():
    class CurrentReview:
        def list_blobs(self, *, name_starts_with):
            return [SimpleNamespace(name=f"{SOURCE_ID}/review-1.json")]

        def get_blob_client(self, name):
            return SimpleNamespace(
                download_blob=lambda: SimpleNamespace(
                    readall=lambda: json.dumps(attestation()).encode()
                )
            )

    class Evidence:
        def write(self, record):
            return None

    sent = []
    decision, _ = run_monitor(
        policy=POLICY,
        source_id=SOURCE_ID,
        source_uri=SOURCE_URI,
        blob_client=SimpleNamespace(
            get_blob_properties=lambda: SimpleNamespace(etag='"etag-1"', last_modified=NOW)
        ),
        reviews_container=CurrentReview(),
        search_reader=FakeSearch(SearchSnapshot(
            True, NOW - timedelta(minutes=1), "success"
        )),
        evidence_writer=Evidence(),
        accountable_role="Data Owner",
        operator_role="Control Operator",
        notify=lambda payload: sent.append(payload) or 202,
        evaluated_at=NOW,
        correlation_id="correlation-lag",
    )

    assert decision.overall_state is State.SYNC_PENDING
    assert sent[0]["accountable_role"] == "Control Operator"


def test_evidence_writer_creates_control_local_run_path():
    writes = []
    writer = BlobEvidenceWriter(SimpleNamespace(
        upload_blob=lambda **kwargs: writes.append(kwargs)
    ))

    writer.write({
        "correlation_id": "correlation-1",
        "event_type": "freshness_decision",
        "timestamp": "2026-11-05T12:00:00Z",
    })

    assert writes[0]["name"] == "2026-11-05/correlation-1/freshness_decision.json"
    assert writes[0]["overwrite"] is False


    def test_notification_outcomes_for_distinct_roles_get_distinct_evidence_paths():
        writes = []
        writer = BlobEvidenceWriter(SimpleNamespace(
            upload_blob=lambda **kwargs: writes.append(kwargs)
        ))

        for role in ("Knowledge Owner", "Control Operator"):
            writer.write({
                "correlation_id": "correlation-1",
                "event_type": "notification_outcome",
                "timestamp": "2026-11-05T12:00:00Z",
                "notification_role": role,
            })

        assert len({write["name"] for write in writes}) == 2


def test_http_notification_sink_requires_https_and_requests_bearer_token():
    credential = FakeCredential()
    client = FakeHttpClient()
    sink = HttpNotificationSink(
        "https://notify.example/path", "https://notify.example/.default",
        credential, client=client,
    )

    assert sink.send({"control_id": "KNW-001"}) == 200
    assert credential.scope == "https://notify.example/.default"
    assert client.calls[0][2]["headers"]["Authorization"] == "Bearer synthetic-token"
    with pytest.raises(ValueError, match="HTTPS"):
        HttpNotificationSink("http://notify.example", "scope", credential, client=client)


def test_search_resources_use_a_filterable_source_uri_and_24_hour_indexer():
    data_source, index, indexer = search_resources(
        data_source_name="knowledge-source",
        index_name="knowledge-index",
        indexer_name="knowledge-indexer",
        storage_account_name="syntheticstorage",
        blob_endpoint="https://syntheticstorage.blob.core.windows.net/",
        source_container="source",
        sas="?synthetic-sas",
    )

    assert data_source["container"] == {"name": "source"}
    assert "SharedAccessSignature=?synthetic-sas" in data_source["credentials"]["connectionString"]
    fields = {field["name"]: field for field in index["fields"]}
    assert fields["source_key"]["key"] is True
    assert fields["source_uri"]["filterable"] is True
    assert fields["metadata_storage_last_modified"]["type"] == "Edm.DateTimeOffset"
    assert fields["content_vector"]["type"] == "Collection(Edm.Single)"
    assert fields["content_vector"]["dimensions"] == 1536
    assert fields["content_vector"]["retrievable"] is False
    assert index["vectorSearch"]["profiles"][0]["name"] == "knw001-vector-profile"
    assert indexer["schedule"]["interval"] == "PT24H"
    mappings = {m["targetFieldName"]: m["sourceFieldName"] for m in indexer["fieldMappings"]}
    assert mappings["source_uri"] == "metadata_storage_path"
    # Foundry url_citation reads literal url/title fields; url must equal the monitored Blob URI.
    assert mappings["url"] == "metadata_storage_path"
    assert mappings["title"] == "metadata_storage_name"
    assert fields["url"]["retrievable"] is True and fields["title"]["retrievable"] is True


def test_user_delegation_sas_is_read_list_only_and_expires_within_seven_days(monkeypatch):
    import knw001.search_setup as setup

    captured = {}
    monkeypatch.setattr(
        setup,
        "generate_container_sas",
        lambda **kwargs: captured.update(kwargs) or "synthetic-sas",
    )
    blob_service = SimpleNamespace(
        get_user_delegation_key=lambda **kwargs: captured.update(key_request=kwargs) or "delegation-key"
    )

    sas, expiry = create_read_list_sas(
        blob_service=blob_service,
        account_name="syntheticstorage",
        container_name="source",
        now=NOW,
    )

    permissions = captured["permission"]
    assert sas == "synthetic-sas"
    assert expiry - captured["start"] == timedelta(days=7)
    assert expiry == NOW + timedelta(days=7) - timedelta(minutes=5)
    assert permissions.read is True
    assert permissions.list is True
    assert permissions.write is False
    assert permissions.delete is False
    assert captured["container_name"] == "source"


@pytest.mark.parametrize("lifetime", [
    timedelta(0),
    timedelta(days=8),
])
def test_user_delegation_sas_rejects_nonpositive_or_overlong_lifetime(lifetime):
    with pytest.raises(ValueError, match="at most seven days"):
        create_read_list_sas(
            blob_service=SimpleNamespace(),
            account_name="syntheticstorage",
            container_name="source",
            now=NOW,
            lifetime=lifetime,
        )


def test_search_setup_uses_entra_and_does_not_print_the_sas(capsys):
    credential = FakeCredential()
    client = FakeHttpClient()
    setup = AzureSearchSetup(
        endpoint="https://search.example", credential=credential, client=client
    )
    data_source, index, indexer = search_resources(
        data_source_name="knowledge-source",
        index_name="knowledge-index",
        indexer_name="knowledge-indexer",
        storage_account_name="syntheticstorage",
        blob_endpoint="https://syntheticstorage.blob.core.windows.net",
        source_container="source",
        sas="synthetic-secret",
    )

    setup.configure(data_source, index, indexer)
    setup.run_indexer("knowledge-indexer")

    assert credential.scope == SEARCH_SCOPE
    assert [call[0] for call in client.calls] == ["put", "put", "put", "post"]
    assert all(call[2]["params"]["api-version"] == SEARCH_API_VERSION for call in client.calls)
    assert "synthetic-secret" in client.calls[0][2]["json"]["credentials"]["connectionString"]
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""