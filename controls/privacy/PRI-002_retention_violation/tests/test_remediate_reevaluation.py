"""Regression tests: an ETag match alone must not be enough to authorize deletion.

Blob index tags (legal hold, lifecycle tag) are a separate index from blob
properties and are not reflected in the blob's ETag. These tests fake the
Azure Blob SDK boundary to prove `remediate()` re-fetches tags and refuses to
delete when they no longer justify remediation, even though the ETag is
unchanged from the scan.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from src.pri_002.acs_gate import ApprovalTicket
from src.pri_002.models import RetentionPolicy, RetentionRecord
from src.pri_002.policy import evaluate_retention

NOW = datetime(2026, 1, 31, tzinfo=UTC)
POLICY = RetentionPolicy("customer-conversation-30d", 30, 2)
POLICIES = {POLICY.retention_class: POLICY}
ETAG = '"etag-1"'


@dataclass
class _FakeBlobClient:
    tags: dict[str, str]
    deleted: bool = False
    _properties_calls: int = 0

    async def get_blob_properties(self):
        self._properties_calls += 1
        if self.deleted:
            from azure.core.exceptions import ResourceNotFoundError

            raise ResourceNotFoundError("gone")
        return SimpleNamespace(etag=ETAG, has_legal_hold=False, immutability_policy=None)

    async def get_blob_tags(self):
        return self.tags

    async def delete_blob(self, **_kwargs):
        self.deleted = True


class _FakeService:
    def __init__(self, blob_client: _FakeBlobClient) -> None:
        self._blob_client = blob_client

    def get_blob_client(self, _container: str, _blob_name: str) -> _FakeBlobClient:
        return self._blob_client

    async def close(self) -> None:
        return None


class _FakeCredential:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False


@pytest.fixture
def store(monkeypatch):
    monkeypatch.setenv("PRI002_STORAGE_BLOB_ENDPOINT", "https://fake.blob.core.windows.net")
    monkeypatch.setenv("PRI002_CONTAINER", "pri-002-retention-demo")
    from src.pri_002 import storage as storage_module

    instance = storage_module.RetentionStore()
    monkeypatch.setattr(storage_module, "DefaultAzureCredential", _FakeCredential)
    return instance, storage_module


def _scanned_decision():
    record = RetentionRecord(
        record_id="synthetic-record",
        blob_name="records/synthetic-record.json",
        etag=ETAG,
        last_modified=NOW - timedelta(days=45),
        retention_class=POLICY.retention_class,
        lifecycle_tag=None,  # missing at scan time -> remediation required
        legal_hold=False,
    )
    return evaluate_retention(record, POLICIES, NOW)


def test_legal_hold_applied_after_scan_blocks_deletion_despite_unchanged_etag(store):
    instance, storage_module = store
    decision = _scanned_decision()
    fake_blob = _FakeBlobClient(
        tags={
            "RetentionClass": POLICY.retention_class,
            "DemoAgeDays": "45",
            "DemoLegalHold": "true",  # legal hold applied after the scan
        }
    )
    monkeypatch_service = _FakeService(fake_blob)
    storage_module.BlobServiceClient = lambda *_a, **_k: monkeypatch_service  # type: ignore[assignment]

    approval = ApprovalTicket(approved=True, issued_at=datetime.now(UTC))
    result = asyncio.run(instance.remediate(decision, approval))

    assert result.status == "blocked"
    assert fake_blob.deleted is False


def test_retention_class_removed_after_scan_blocks_deletion_despite_unchanged_etag(store):
    """The retention class tag governs which policy applies; removing it after
    the scan must block deletion even though the ETag did not change."""
    instance, storage_module = store
    decision = _scanned_decision()
    fake_blob = _FakeBlobClient(
        tags={
            # RetentionClass removed/renamed after the scan: unknown to POLICIES.
            "DemoAgeDays": "45",
            "DemoLegalHold": "false",
        }
    )
    monkeypatch_service = _FakeService(fake_blob)
    storage_module.BlobServiceClient = lambda *_a, **_k: monkeypatch_service  # type: ignore[assignment]

    approval = ApprovalTicket(approved=True, issued_at=datetime.now(UTC))
    result = asyncio.run(instance.remediate(decision, approval))

    assert result.status == "blocked"
    assert fake_blob.deleted is False


def test_unchanged_tags_still_allow_deletion(store):
    instance, storage_module = store
    decision = _scanned_decision()
    fake_blob = _FakeBlobClient(
        tags={
            "RetentionClass": POLICY.retention_class,
            "DemoAgeDays": "45",
            "DemoLegalHold": "false",
        }
    )
    monkeypatch_service = _FakeService(fake_blob)
    storage_module.BlobServiceClient = lambda *_a, **_k: monkeypatch_service  # type: ignore[assignment]

    approval = ApprovalTicket(approved=True, issued_at=datetime.now(UTC))
    result = asyncio.run(instance.remediate(decision, approval))

    assert result.status == "deleted_from_active_namespace"
    assert result.verified_absent is True
    assert fake_blob.deleted is True


def test_missing_approval_is_blocked_before_any_azure_call(store):
    instance, storage_module = store
    decision = _scanned_decision()

    async def _unexpected_call(*_a, **_k):
        raise AssertionError("no Azure call should happen without an approval")

    storage_module.BlobServiceClient = _unexpected_call  # type: ignore[assignment]

    result = asyncio.run(instance.remediate(decision, None))

    assert result.status == "blocked"


def test_replayed_approval_is_blocked_on_second_remediation(store):
    instance, storage_module = store
    decision = _scanned_decision()
    fake_blob = _FakeBlobClient(
        tags={
            "RetentionClass": POLICY.retention_class,
            "DemoAgeDays": "45",
            "DemoLegalHold": "false",
        }
    )
    monkeypatch_service = _FakeService(fake_blob)
    storage_module.BlobServiceClient = lambda *_a, **_k: monkeypatch_service  # type: ignore[assignment]

    approval = ApprovalTicket(approved=True, issued_at=datetime.now(UTC))
    first = asyncio.run(instance.remediate(decision, approval))
    assert first.status == "deleted_from_active_namespace"

    def _unexpected_call(*_a, **_k):
        raise AssertionError("a replayed ticket must not reach Azure again")

    storage_module.BlobServiceClient = _unexpected_call  # type: ignore[assignment]
    second = asyncio.run(instance.remediate(decision, approval))

    assert second.status == "blocked"
