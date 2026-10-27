"""Deterministic owner-review and search-index freshness policy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Sequence


class State(StrEnum):
    FRESH = "fresh"
    REVIEW_REQUIRED = "review_required"
    SYNC_PENDING = "sync_pending"
    CANNOT_EVALUATE = "cannot_evaluate"
    CURRENT = "current"


@dataclass(frozen=True)
class FreshnessPolicy:
    source_id: str
    owner_object_id: str
    maximum_review_age_days: int
    version: str


@dataclass(frozen=True)
class BlobSnapshot:
    source_id: str
    etag: str
    last_modified: datetime


@dataclass(frozen=True)
class ReviewAttestation:
    source_id: str
    source_etag: str
    owner_object_id: str
    policy_version: str
    recorded_at: datetime
    record_id: str


@dataclass(frozen=True)
class SearchSnapshot:
    query_succeeded: bool
    indexed_last_modified: datetime | None
    indexer_status: str | None
    metadata_field_present: bool = True
    indexer_has_item_errors: bool = False


@dataclass(frozen=True)
class FreshnessDecision:
    overall_state: State
    review_state: State
    index_state: State
    reason: str
    review_age_days: float | None
    policy_version: str | None
    source_id: str | None


def _aware_utc(value: datetime) -> datetime | None:
    if value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(UTC)


def _cannot_evaluate(
    reason: str,
    *,
    policy: FreshnessPolicy | None,
    source: BlobSnapshot | None,
    review_state: State = State.CANNOT_EVALUATE,
    index_state: State = State.CANNOT_EVALUATE,
    review_age_days: float | None = None,
) -> FreshnessDecision:
    return FreshnessDecision(
        overall_state=State.CANNOT_EVALUATE,
        review_state=review_state,
        index_state=index_state,
        reason=reason,
        review_age_days=review_age_days,
        policy_version=policy.version if policy else None,
        source_id=source.source_id if source else None,
    )


def evaluate_freshness(
    policy: FreshnessPolicy | None,
    source: BlobSnapshot | None,
    attestations: Sequence[ReviewAttestation] | None,
    search: SearchSnapshot | None,
    evaluated_at: datetime,
) -> FreshnessDecision:
    """Evaluate owner-review age and index synchronization independently.

    A missing attestation is a review requirement. Unavailable or malformed
    evidence is not healthy and returns cannot_evaluate.
    """
    now = _aware_utc(evaluated_at)
    if now is None:
        return _cannot_evaluate(
            "Evaluation time is missing a timezone.", policy=policy, source=source
        )
    if policy is None or not all(
        isinstance(value, str) and value.strip()
        for value in (
            policy.source_id,
            policy.owner_object_id,
            policy.version,
        )
    ) or type(policy.maximum_review_age_days) is not int or policy.maximum_review_age_days < 1:
        return _cannot_evaluate(
            "Freshness policy is missing or invalid.", policy=policy, source=source
        )
    if (
        source is None
        or not source.source_id
        or not source.etag
        or source.source_id != policy.source_id
    ):
        return _cannot_evaluate(
            "Configured Blob source is missing, invalid, or mismatched.",
            policy=policy,
            source=source,
        )
    if _aware_utc(source.last_modified) is None:
        return _cannot_evaluate(
            "Blob Last-Modified is missing a timezone.", policy=policy, source=source
        )
    if attestations is None:
        return _cannot_evaluate(
            "Review-attestation store is unavailable.", policy=policy, source=source
        )

    matching = [
        item
        for item in attestations
        if item.source_id == source.source_id
        and item.source_etag == source.etag
        and item.policy_version == policy.version
    ]
    if not matching:
        review_state = State.REVIEW_REQUIRED
        review_reason = "No owner review exists for the current Blob ETag and policy version."
        review_age_days = None
    else:
        if any(item.owner_object_id != policy.owner_object_id for item in matching):
            return _cannot_evaluate(
                "A matching review record was created by an unexpected owner.",
                policy=policy,
                source=source,
            )
        timestamps = [_aware_utc(item.recorded_at) for item in matching]
        if any(value is None for value in timestamps):
            return _cannot_evaluate(
                "A matching review record has an invalid timestamp.",
                policy=policy,
                source=source,
            )
        latest_index = max(range(len(matching)), key=lambda index: timestamps[index])
        latest = matching[latest_index]
        recorded_at = timestamps[latest_index]
        if recorded_at > now:
            return _cannot_evaluate(
                "Owner review timestamp is in the future.",
                policy=policy,
                source=source,
            )
        review_age_days = (now - recorded_at).total_seconds() / 86400
        if review_age_days > policy.maximum_review_age_days:
            review_state = State.REVIEW_REQUIRED
            review_reason = "Owner review exceeds the configured maximum age."
        else:
            review_state = State.FRESH
            review_reason = f"Owner review {latest.record_id} is current for the Blob ETag."

    index_state, index_reason = _evaluate_index(source, search, policy, now)
    if State.CANNOT_EVALUATE in (review_state, index_state):
        overall_state = State.CANNOT_EVALUATE
    elif review_state is State.REVIEW_REQUIRED:
        overall_state = State.REVIEW_REQUIRED
    elif index_state is State.SYNC_PENDING:
        overall_state = State.SYNC_PENDING
    else:
        overall_state = State.FRESH

    return FreshnessDecision(
        overall_state=overall_state,
        review_state=review_state,
        index_state=index_state,
        reason=f"Review: {review_reason} Index: {index_reason}",
        review_age_days=review_age_days,
        policy_version=policy.version,
        source_id=source.source_id,
    )


def _evaluate_index(
    source: BlobSnapshot,
    search: SearchSnapshot | None,
    policy: FreshnessPolicy,
    now: datetime,
) -> tuple[State, str]:
    if search is None or not search.query_succeeded:
        return State.CANNOT_EVALUATE, "Azure AI Search query failed or was unavailable."
    if not search.metadata_field_present:
        return State.CANNOT_EVALUATE, "Indexed source timestamp field is not configured."
    if search.indexer_status not in {"success", "inProgress", "running", "reset"}:
        return State.CANNOT_EVALUATE, "Azure AI Search indexer state is missing or failed."
    if search.indexer_has_item_errors:
        return State.CANNOT_EVALUATE, "Azure AI Search reported an item-level indexing error."
    if search.indexed_last_modified is None:
        return State.SYNC_PENDING, "Source document is not present in the Search index yet."
    indexed_at = _aware_utc(search.indexed_last_modified)
    source_modified = _aware_utc(source.last_modified)
    if indexed_at is None or source_modified is None:
        return State.CANNOT_EVALUATE, "Source or indexed modification timestamp is invalid."
    if indexed_at > now or source_modified > now:
        return State.CANNOT_EVALUATE, "Source or indexed modification timestamp is in the future."
    if indexed_at < source_modified:
        return State.SYNC_PENDING, "Search index modification time is older than the Blob source."
    return State.CURRENT, f"Indexed modification time matches or exceeds the Blob time for policy {policy.version}."