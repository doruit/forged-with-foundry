from datetime import UTC, datetime, timedelta
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from knw001.policy import (
    BlobSnapshot,
    FreshnessPolicy,
    ReviewAttestation,
    SearchSnapshot,
    State,
    evaluate_freshness,
)


NOW = datetime(2026, 10, 27, 12, 0, tzinfo=UTC)
POLICY = FreshnessPolicy(
    source_id="travel-policy",
    owner_object_id="owner-object-id",
    maximum_review_age_days=30,
    version="knw001-v1",
)
SOURCE = BlobSnapshot(
    source_id="travel-policy",
    etag='"blob-etag-2"',
    last_modified=NOW - timedelta(days=2),
)
REVIEW = ReviewAttestation(
    source_id="travel-policy",
    source_etag='"blob-etag-2"',
    owner_object_id="owner-object-id",
    policy_version="knw001-v1",
    recorded_at=NOW - timedelta(days=3),
    record_id="review-1",
)
SEARCH_CURRENT = SearchSnapshot(
    query_succeeded=True,
    indexed_last_modified=SOURCE.last_modified,
    indexer_status="success",
)


def evaluate(
    *,
    policy=POLICY,
    source=SOURCE,
    attestations=(REVIEW,),
    search=SEARCH_CURRENT,
    evaluated_at=NOW,
):
    return evaluate_freshness(policy, source, attestations, search, evaluated_at)


def test_current_review_and_search_document_are_fresh():
    result = evaluate()

    assert result.overall_state is State.FRESH
    assert result.review_state is State.FRESH
    assert result.index_state is State.CURRENT
    assert result.review_age_days == 3


def test_expired_review_requires_owner_review_even_when_index_is_current():
    stale_review = ReviewAttestation(
        **{**REVIEW.__dict__, "recorded_at": NOW - timedelta(days=31)}
    )

    result = evaluate(attestations=(stale_review,))

    assert result.overall_state is State.REVIEW_REQUIRED
    assert result.review_state is State.REVIEW_REQUIRED
    assert result.index_state is State.CURRENT


def test_content_etag_change_invalidates_prior_review():
    changed_source = BlobSnapshot(
        source_id=SOURCE.source_id,
        etag='"blob-etag-3"',
        last_modified=NOW,
    )

    result = evaluate(source=changed_source)

    assert result.overall_state is State.REVIEW_REQUIRED
    assert result.review_state is State.REVIEW_REQUIRED


def test_metadata_only_etag_change_conservatively_invalidates_review():
    changed_source = BlobSnapshot(
        source_id=SOURCE.source_id,
        etag='"blob-metadata-etag"',
        last_modified=SOURCE.last_modified,
    )

    result = evaluate(source=changed_source)

    assert result.review_state is State.REVIEW_REQUIRED


def test_missing_review_is_a_review_requirement():
    result = evaluate(attestations=())

    assert result.overall_state is State.REVIEW_REQUIRED
    assert result.review_state is State.REVIEW_REQUIRED


def test_wrong_owner_attestation_cannot_pass():
    wrong_owner = ReviewAttestation(
        **{**REVIEW.__dict__, "owner_object_id": "unexpected-owner"}
    )

    result = evaluate(attestations=(wrong_owner,))

    assert result.overall_state is State.CANNOT_EVALUATE
    assert result.review_state is State.CANNOT_EVALUATE


@pytest.mark.parametrize(
    "invalid_policy",
    [
        None,
        FreshnessPolicy("", "owner-object-id", 30, "knw001-v1"),
        FreshnessPolicy("travel-policy", "", 30, "knw001-v1"),
        FreshnessPolicy("travel-policy", "owner-object-id", 0, "knw001-v1"),
        FreshnessPolicy("travel-policy", "owner-object-id", True, "knw001-v1"),
        FreshnessPolicy("travel-policy", "owner-object-id", 30, ""),
    ],
)
def test_missing_or_invalid_policy_fails_closed(invalid_policy):
    result = evaluate(policy=invalid_policy)

    assert result.overall_state is State.CANNOT_EVALUATE


def test_unavailable_attestation_store_fails_closed():
    result = evaluate(attestations=None)

    assert result.overall_state is State.CANNOT_EVALUATE
    assert result.review_state is State.CANNOT_EVALUATE


@pytest.mark.parametrize(
    "bad_timestamp",
    [
        datetime(2026, 10, 25, 12, 0),
        NOW + timedelta(seconds=1),
    ],
)
def test_naive_or_future_review_timestamp_fails_closed(bad_timestamp):
    invalid_review = ReviewAttestation(
        **{**REVIEW.__dict__, "recorded_at": bad_timestamp}
    )

    result = evaluate(attestations=(invalid_review,))

    assert result.overall_state is State.CANNOT_EVALUATE


def test_missing_blob_or_mismatched_policy_source_fails_closed():
    assert evaluate(source=None).overall_state is State.CANNOT_EVALUATE
    mismatched_source = BlobSnapshot(
        source_id="another-source",
        etag=SOURCE.etag,
        last_modified=SOURCE.last_modified,
    )
    assert evaluate(source=mismatched_source).overall_state is State.CANNOT_EVALUATE


def test_missing_index_document_is_sync_pending():
    search = SearchSnapshot(True, None, "success")

    result = evaluate(search=search)

    assert result.overall_state is State.SYNC_PENDING
    assert result.index_state is State.SYNC_PENDING


def test_stale_search_document_is_sync_pending_without_review_breach():
    search = SearchSnapshot(
        query_succeeded=True,
        indexed_last_modified=SOURCE.last_modified - timedelta(minutes=5),
        indexer_status="success",
    )

    result = evaluate(search=search)

    assert result.overall_state is State.SYNC_PENDING
    assert result.review_state is State.FRESH
    assert result.index_state is State.SYNC_PENDING


@pytest.mark.parametrize(
    "search",
    [
        None,
        SearchSnapshot(False, SOURCE.last_modified, "success"),
        SearchSnapshot(True, SOURCE.last_modified, "error"),
        SearchSnapshot(True, SOURCE.last_modified, "success", indexer_has_item_errors=True),
        SearchSnapshot(True, SOURCE.last_modified, "success", metadata_field_present=False),
        SearchSnapshot(True, NOW + timedelta(seconds=1), "success"),
    ],
)
def test_search_failure_or_ambiguous_metadata_fails_closed(search):
    result = evaluate(search=search)

    assert result.overall_state is State.CANNOT_EVALUATE
    assert result.index_state is State.CANNOT_EVALUATE


def test_review_breach_takes_precedence_over_index_lag_but_preserves_both_states():
    stale_review = ReviewAttestation(
        **{**REVIEW.__dict__, "recorded_at": NOW - timedelta(days=40)}
    )
    stale_search = SearchSnapshot(
        True,
        SOURCE.last_modified - timedelta(minutes=1),
        "success",
    )

    result = evaluate(attestations=(stale_review,), search=stale_search)

    assert result.overall_state is State.REVIEW_REQUIRED
    assert result.review_state is State.REVIEW_REQUIRED
    assert result.index_state is State.SYNC_PENDING