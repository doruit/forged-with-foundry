"""Configure the control-owned Azure AI Search Blob indexer."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from urllib.parse import quote

import httpx
from azure.storage.blob import ContainerSasPermissions, generate_container_sas

from .azure_facts import SEARCH_API_VERSION, SEARCH_SCOPE

MAX_SAS_LIFETIME = timedelta(days=7)


def create_read_list_sas(
    *,
    blob_service,
    account_name: str,
    container_name: str,
    now: datetime | None = None,
    lifetime: timedelta = MAX_SAS_LIFETIME,
) -> tuple[str, datetime]:
    start = now or datetime.now(UTC)
    if start.tzinfo is None or start.utcoffset() is None:
        raise ValueError("SAS start time must be timezone-aware.")
    if lifetime <= timedelta(0) or lifetime > MAX_SAS_LIFETIME:
        raise ValueError("Blob indexer SAS lifetime must be at most seven days.")
    start = start.astimezone(UTC)
    sas_start = start - timedelta(minutes=5)
    expiry = start + lifetime - timedelta(minutes=5)
    key = blob_service.get_user_delegation_key(
        key_start_time=sas_start,
        key_expiry_time=expiry,
    )
    sas = generate_container_sas(
        account_name=account_name,
        container_name=container_name,
        user_delegation_key=key,
        permission=ContainerSasPermissions(read=True, list=True),
        start=sas_start,
        expiry=expiry,
    )
    return sas, expiry


def search_resources(
    *,
    data_source_name: str,
    index_name: str,
    indexer_name: str,
    storage_account_name: str,
    blob_endpoint: str,
    source_container: str,
    sas: str,
) -> tuple[dict, dict, dict]:
    connection_string = (
        f"BlobEndpoint={blob_endpoint.rstrip('/')};"
        f"AccountName={storage_account_name};SharedAccessSignature=?{sas.lstrip('?')}"
    )
    data_source = {
        "name": data_source_name,
        "type": "azureblob",
        "credentials": {"connectionString": connection_string},
        "container": {"name": source_container},
    }
    index = {
        "name": index_name,
        "vectorSearch": {
            "algorithms": [
                {
                    "name": "knw001-hnsw-cosine",
                    "kind": "hnsw",
                    "hnswParameters": {"metric": "cosine"},
                }
            ],
            "profiles": [
                {"name": "knw001-vector-profile", "algorithm": "knw001-hnsw-cosine"}
            ],
        },
        "fields": [
            {"name": "source_key", "type": "Edm.String", "key": True, "retrievable": True},
            {"name": "source_uri", "type": "Edm.String", "filterable": True, "retrievable": True},
            # Literal url/title fields: the Foundry Azure AI Search tool reads only these
            # names for url_citation annotations on the direct connection + index path.
            {"name": "url", "type": "Edm.String", "retrievable": True},
            {"name": "title", "type": "Edm.String", "retrievable": True},
            {
                "name": "metadata_storage_last_modified",
                "type": "Edm.DateTimeOffset",
                "filterable": True,
                "sortable": True,
                "retrievable": True,
            },
            {"name": "content", "type": "Edm.String", "searchable": True, "retrievable": True},
            {
                "name": "content_vector",
                "type": "Collection(Edm.Single)",
                "searchable": True,
                "retrievable": False,
                "dimensions": 1536,
                "vectorSearchProfile": "knw001-vector-profile",
            },
        ],
    }
    indexer = {
        "name": indexer_name,
        "dataSourceName": data_source_name,
        "targetIndexName": index_name,
        "schedule": {"interval": "PT24H"},
        "parameters": {
            "configuration": {
                "dataToExtract": "contentAndMetadata",
                "parsingMode": "default",
                "indexedFileNameExtensions": ".md,.txt",
            }
        },
        "fieldMappings": [
            {
                "sourceFieldName": "metadata_storage_path",
                "targetFieldName": "source_key",
                "mappingFunction": {"name": "base64Encode"},
            },
            {"sourceFieldName": "metadata_storage_path", "targetFieldName": "source_uri"},
            {"sourceFieldName": "metadata_storage_path", "targetFieldName": "url"},
            {"sourceFieldName": "metadata_storage_name", "targetFieldName": "title"},
            {
                "sourceFieldName": "metadata_storage_last_modified",
                "targetFieldName": "metadata_storage_last_modified",
            },
            {"sourceFieldName": "content", "targetFieldName": "content"},
        ],
    }
    return data_source, index, indexer


class AzureSearchSetup:
    def __init__(
        self,
        *,
        endpoint: str,
        credential,
        client: httpx.Client | None = None,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.credential = credential
        self.client = client or httpx.Client(timeout=30.0)

    def configure(self, data_source: dict, index: dict, indexer: dict) -> None:
        token = self.credential.get_token(SEARCH_SCOPE).token
        headers = {"Authorization": f"Bearer {token}"}
        self._put(f"datasources/{data_source['name']}", data_source, headers)
        self._put(f"indexes/{index['name']}", index, headers)
        self._put(f"indexers/{indexer['name']}", indexer, headers)

    def run_indexer(self, indexer_name: str) -> None:
        token = self.credential.get_token(SEARCH_SCOPE).token
        response = self.client.post(
            f"{self.endpoint}/indexers/{quote(indexer_name, safe='')}/run",
            params={"api-version": SEARCH_API_VERSION},
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()

    def _put(self, path: str, payload: dict, headers: dict[str, str]) -> None:
        response = self.client.put(
            f"{self.endpoint}/{path}",
            params={"api-version": SEARCH_API_VERSION},
            headers=headers,
            json=payload,
        )
        response.raise_for_status()