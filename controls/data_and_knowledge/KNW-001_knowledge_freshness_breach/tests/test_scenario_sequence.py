"""Replay README Azure steps 3-7 in order through the real adapters.

The fakes model the two service behaviors the sequence depends on: every Blob
upload or metadata update changes the ETag and Last-Modified, and Search keeps
the old indexed timestamp until the indexer runs again.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from foundry_probe import build_observation
from knw001.monitor import run_monitor
from knw001.policy import FreshnessPolicy, SearchSnapshot
from knw001.review import record_review_attestation

START = datetime(2026, 11, 8, 9, 0, tzinfo=UTC)
SOURCE_ID = "vpn-reset-guide"
SOURCE_URI = "https://syntheticstorage.blob.core.windows.net/source/vpn-reset-guide.md"
OWNER = "owner-object-id"
POLICY = FreshnessPolicy(SOURCE_ID, OWNER, 30, "knw001-v1")
FUTURE_EXPIRY = "2027-06-30T00:00:00Z"
PAST_EXPIRY = "2026-01-01T00:00:00Z"
OWNER_ROLE = "Knowledge Owner"
OPERATOR_ROLE = "Control Operator"


class SourceBlob:
    def __init__(self) -> None:
        self.revision = 0
        self.properties = None

    def write(self, *, metadata: dict, at: datetime) -> None:
        self.revision += 1
        self.properties = SimpleNamespace(
            etag=f'"0x8DE{self.revision:04X}"', last_modified=at, metadata=dict(metadata)
        )

    def get_blob_properties(self):
        return self.properties


class ReviewStore:
    def __init__(self) -> None:
        self.blobs: dict[str, str] = {}

    def upload_blob(self, *, name: str, data: str, overwrite: bool) -> None:
        assert overwrite is False and name not in self.blobs
        self.blobs[name] = data

    def list_blobs(self, *, name_starts_with: str):
        return [SimpleNamespace(name=name) for name in sorted(self.blobs) if name.startswith(name_starts_with)]

    def get_blob_client(self, name: str):
        data = self.blobs[name].encode()
        return SimpleNamespace(download_blob=lambda: SimpleNamespace(readall=lambda: data))


class LaggingSearch:
    def __init__(self) -> None:
        self.indexed_last_modified = None

    def run_indexer(self, blob: SourceBlob) -> None:
        self.indexed_last_modified = blob.get_blob_properties().last_modified

    def snapshot(self, source_uri: str) -> SearchSnapshot:
        assert source_uri == SOURCE_URI
        return SearchSnapshot(True, self.indexed_last_modified, "success")


class DemoEnvironment:
    def __init__(self) -> None:
        self.now = START
        self.blob = SourceBlob()
        self.reviews = ReviewStore()
        self.search = LaggingSearch()

    def tick(self) -> datetime:
        self.now += timedelta(minutes=2)
        return self.now

    def upload(self, *, valid_until: str) -> None:
        self.blob.write(metadata={"valid_until": valid_until}, at=self.tick())

    def update_metadata(self, *, valid_until: str) -> None:
        self.blob.write(metadata={"valid_until": valid_until}, at=self.tick())

    def run_indexer(self) -> None:
        self.tick()
        self.search.run_indexer(self.blob)

    def confirm_review(self) -> str:
        attestation = record_review_attestation(
            policy=POLICY,
            blob_client=self.blob,
            reviews_container=self.reviews,
            authenticated_owner_object_id=OWNER,
            submitted_etag=self.blob.get_blob_properties().etag,
            submitted_policy_version=POLICY.version,
            recorded_at=self.tick(),
        )
        return attestation.record_id

    def run_monitor(self) -> tuple[dict, list[str]]:
        records: list[dict] = []
        decision, _ = run_monitor(
            policy=POLICY,
            source_id=SOURCE_ID,
            source_uri=SOURCE_URI,
            blob_client=self.blob,
            reviews_container=self.reviews,
            search_reader=self.search,
            evidence_writer=SimpleNamespace(write=records.append),
            accountable_role=OWNER_ROLE,
            notify=lambda payload: 202,
            evaluated_at=self.tick(),
        )
        evidence = records[0]
        assert evidence["event_type"] == "freshness_decision"
        assert evidence["decision"]["overall_state"] == decision.overall_state.value
        outcome_roles = [item["notification_role"] for item in records[1:]]
        assert outcome_roles == evidence["notification_roles"]
        return evidence, outcome_roles


def test_given_readme_steps_3_to_7_when_replayed_in_order_then_each_documented_decision_is_produced():
    demo = DemoEnvironment()

    # Step 3: revision 1 indexed without an owner review.
    demo.upload(valid_until=FUTURE_EXPIRY)
    demo.run_indexer()
    evidence, roles = demo.run_monitor()
    assert evidence["decision"]["overall_state"] == "review_required"
    assert evidence["decision"]["index_state"] == "current"
    assert roles == [OWNER_ROLE]

    # Step 4: the owner attests the current revision.
    record_id = demo.confirm_review()
    evidence, roles = demo.run_monitor()
    assert evidence["decision"]["overall_state"] == "fresh"
    assert evidence["review_record_id"] == record_id
    assert evidence["accountable_role"] == OWNER_ROLE
    assert roles == []

    # Step 5a: revision 2 uploaded; the old review no longer applies and Search lags.
    demo.upload(valid_until=FUTURE_EXPIRY)
    evidence, roles = demo.run_monitor()
    assert evidence["decision"]["overall_state"] == "review_required"
    assert evidence["decision"]["review_state"] == "review_required"
    assert evidence["decision"]["index_state"] == "sync_pending"
    assert roles == [OWNER_ROLE, OPERATOR_ROLE]

    # Step 5b: the owner reviews revision 2 before the indexer runs again.
    demo.confirm_review()
    evidence, roles = demo.run_monitor()
    assert evidence["decision"]["overall_state"] == "sync_pending"
    assert evidence["decision"]["review_state"] == "fresh"
    assert evidence["decision"]["index_state"] == "sync_pending"
    assert roles == [OPERATOR_ROLE]

    # Step 6: expired, re-indexed and reviewed; only the expiry still triggers.
    demo.update_metadata(valid_until=PAST_EXPIRY)
    demo.run_indexer()
    expired_record_id = demo.confirm_review()
    evidence, roles = demo.run_monitor()
    assert evidence["decision"]["overall_state"] == "review_required"
    assert evidence["decision"]["index_state"] == "current"
    assert evidence["review_record_id"] == expired_record_id
    assert evidence["decision"]["reason"].startswith(f"Review: Owner review {expired_record_id} is current")
    assert "Document valid-until date has passed." in evidence["decision"]["reason"]
    assert roles == [OWNER_ROLE]

    observation = build_observation(
        response=SimpleNamespace(id="resp-synthetic", status="completed", output=[]),
        agent_id="agent-synthetic",
        agent_name="knw001-probe-synthetic",
        agent_version="1",
        correlation_id="probe-synthetic",
        source_uri=SOURCE_URI,
        etag_before=demo.blob.get_blob_properties().etag,
        etag_after=demo.blob.get_blob_properties().etag,
        observed_at=demo.tick(),
    )
    assert observation["source_etag_sha256"] == evidence["source_etag_sha256"]

    # Step 7: malformed expiry metadata cannot be evaluated.
    demo.update_metadata(valid_until="next-quarter")
    evidence, roles = demo.run_monitor()
    assert evidence["decision"]["overall_state"] == "cannot_evaluate"
    assert evidence["decision"]["reason"] == "Document valid-until metadata is malformed."
    assert roles == [OPERATOR_ROLE]


def test_given_reviewed_source_when_only_expiry_metadata_changes_then_review_and_index_also_trigger():
    demo = DemoEnvironment()
    demo.upload(valid_until=FUTURE_EXPIRY)
    demo.run_indexer()
    demo.confirm_review()

    demo.update_metadata(valid_until=PAST_EXPIRY)
    evidence, roles = demo.run_monitor()

    assert evidence["decision"]["overall_state"] == "review_required"
    assert evidence["decision"]["reason"].startswith("Review: No owner review exists")
    assert evidence["decision"]["index_state"] == "sync_pending"
    assert roles == [OWNER_ROLE, OPERATOR_ROLE]
