"""Read KNW-001 source, review, and Search facts from Azure clients."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Protocol

import httpx

from .policy import BlobSnapshot, ReviewAttestation, SearchSnapshot

SEARCH_SCOPE = "https://search.azure.com/.default"
SEARCH_API_VERSION = "2024-07-01"


class TokenCredential(Protocol):
    def get_token(self, scope: str): ...


class SearchReader(Protocol):
    def snapshot(self, source_uri: str) -> SearchSnapshot: ...


class AzureSearchReader:
    def __init__(
        self,
        endpoint: str,
        index_name: str,
        indexer_name: str,
        credential: TokenCredential,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.index_name = index_name
        self.indexer_name = indexer_name
        self.credential = credential
        self.client = client or httpx.Client(timeout=15.0)

    def snapshot(self, source_uri: str) -> SearchSnapshot:
        try:
            token = self.credential.get_token(SEARCH_SCOPE).token
            headers = {"Authorization": f"Bearer {token}"}
            escaped_uri = source_uri.replace("'", "''")
            response = self.client.post(
                f"{self.endpoint}/indexes/{self.index_name}/docs/search",
                params={"api-version": SEARCH_API_VERSION},
                headers=headers,
                json={
                    "search": "*",
                    "filter": f"source_uri eq '{escaped_uri}'",
                    "select": "source_uri,metadata_storage_last_modified",
                    "top": 2,
                },
            )
            response.raise_for_status()
            results = response.json().get("value", [])
            if len(results) > 1:
                return SearchSnapshot(False, None, None)
            indexed_at = None
            if results:
                result = results[0]
                if result.get("source_uri") != source_uri:
                    return SearchSnapshot(False, None, None)
                value = result.get("metadata_storage_last_modified")
                indexed_at = datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None

            status_response = self.client.get(
                f"{self.endpoint}/indexers/{self.indexer_name}/status",
                params={"api-version": SEARCH_API_VERSION},
                headers=headers,
            )
            status_response.raise_for_status()
            last_result = status_response.json().get("lastResult") or {}
            errors = last_result.get("errors") or []
            return SearchSnapshot(
                query_succeeded=True,
                indexed_last_modified=indexed_at,
                indexer_status=last_result.get("status"),
                indexer_has_item_errors=bool(errors),
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError, AttributeError):
            return SearchSnapshot(False, None, None)


def _read_valid_until(metadata) -> tuple[datetime | None, bool]:
    if metadata is None:
        return None, False
    if not isinstance(metadata, dict):
        return None, True
    values = {key.lower(): value for key, value in metadata.items() if isinstance(key, str)}
    if "valid_until" not in values:
        return None, False
    value = values["valid_until"]
    if not isinstance(value, str) or not value.strip():
        return None, True
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None, True
    return parsed, False


def collect_freshness_facts(
    *,
    source_id: str,
    source_uri: str,
    blob_client,
    reviews_container,
    search_reader: SearchReader,
) -> tuple[BlobSnapshot | None, tuple[ReviewAttestation, ...] | None, SearchSnapshot]:
    try:
        properties = blob_client.get_blob_properties()
        valid_until, expiry_invalid = _read_valid_until(getattr(properties, "metadata", None))
        source = BlobSnapshot(
            source_id,
            properties.etag,
            properties.last_modified,
            valid_until=valid_until,
            expiry_metadata_invalid=expiry_invalid,
        )
    except Exception:
        source = None

    try:
        attestations = tuple(
            _read_attestation(reviews_container, item.name)
            for item in reviews_container.list_blobs(name_starts_with=f"{source_id}/")
        )
    except Exception:
        attestations = None

    try:
        search = search_reader.snapshot(source_uri)
    except Exception:
        search = SearchSnapshot(False, None, None)

    return source, attestations, search


def _read_attestation(container, name: str) -> ReviewAttestation:
    data = json.loads(container.get_blob_client(name).download_blob().readall())
    return ReviewAttestation(
        source_id=data["source_id"],
        source_etag=data["source_etag"],
        owner_object_id=data["owner_object_id"],
        policy_version=data["policy_version"],
        recorded_at=datetime.fromisoformat(data["recorded_at"].replace("Z", "+00:00")),
        record_id=data["record_id"],
    )