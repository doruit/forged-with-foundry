"""Create an owner attestation for the current configured Blob revision."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

from .policy import BlobSnapshot, FreshnessPolicy, ReviewAttestation


def create_review_attestation(
    *,
    policy: FreshnessPolicy,
    source: BlobSnapshot,
    authenticated_owner_object_id: str,
    submitted_etag: str,
    submitted_policy_version: str,
    recorded_at: datetime | None = None,
    record_id: str | None = None,
) -> ReviewAttestation:
    if authenticated_owner_object_id != policy.owner_object_id:
        raise PermissionError("Only the configured Knowledge Owner may attest review.")
    if source.source_id != policy.source_id:
        raise ValueError("The source does not match the configured review policy.")
    if submitted_etag != source.etag:
        raise ValueError("The source changed after the review page was opened.")
    if submitted_policy_version != policy.version:
        raise ValueError("The review page uses a different policy version.")

    timestamp = recorded_at or datetime.now(UTC)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("Review time must be timezone-aware.")

    return ReviewAttestation(
        source_id=source.source_id,
        source_etag=source.etag,
        owner_object_id=authenticated_owner_object_id,
        policy_version=policy.version,
        recorded_at=timestamp.astimezone(UTC),
        record_id=record_id or str(uuid4()),
    )


def serialize_review_attestation(attestation: ReviewAttestation) -> dict[str, str]:
    return {
        "source_id": attestation.source_id,
        "source_etag": attestation.source_etag,
        "owner_object_id": attestation.owner_object_id,
        "policy_version": attestation.policy_version,
        "recorded_at": attestation.recorded_at.isoformat().replace("+00:00", "Z"),
        "record_id": attestation.record_id,
    }


def record_review_attestation(
    *,
    policy: FreshnessPolicy,
    blob_client,
    reviews_container,
    authenticated_owner_object_id: str,
    submitted_etag: str,
    submitted_policy_version: str,
    recorded_at: datetime | None = None,
    record_id: str | None = None,
) -> ReviewAttestation:
    properties = blob_client.get_blob_properties()
    source = BlobSnapshot(policy.source_id, properties.etag, properties.last_modified)
    attestation = create_review_attestation(
        policy=policy,
        source=source,
        authenticated_owner_object_id=authenticated_owner_object_id,
        submitted_etag=submitted_etag,
        submitted_policy_version=submitted_policy_version,
        recorded_at=recorded_at,
        record_id=record_id,
    )
    reviews_container.upload_blob(
        name=f"{policy.source_id}/{attestation.record_id}.json",
        data=json.dumps(serialize_review_attestation(attestation)),
        overwrite=False,
    )
    return attestation