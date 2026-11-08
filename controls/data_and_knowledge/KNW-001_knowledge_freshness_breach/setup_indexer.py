from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
from datetime import UTC, datetime

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from knw001.search_setup import (
    AzureSearchSetup,
    create_read_list_sas,
    search_resources,
)


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"Set {name} before running indexer setup.")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Renew the Blob indexer credential, configure Search, and run the indexer."
    )
    parser.parse_args()

    credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
    blob_endpoint = required("KNW001_BLOB_ENDPOINT")
    storage_account_name = required("KNW001_STORAGE_ACCOUNT")
    source_container = required("KNW001_SOURCE_CONTAINER")
    index_name = required("KNW001_SEARCH_INDEX")
    indexer_name = required("KNW001_SEARCH_INDEXER")
    data_source_name = required("KNW001_SEARCH_DATASOURCE")

    blob_service = BlobServiceClient(blob_endpoint, credential=credential)
    sas, expiry = create_read_list_sas(
        blob_service=blob_service,
        account_name=storage_account_name,
        container_name=source_container,
        now=datetime.now(UTC),
    )
    data_source, index, indexer = search_resources(
        data_source_name=data_source_name,
        index_name=index_name,
        indexer_name=indexer_name,
        storage_account_name=storage_account_name,
        blob_endpoint=blob_endpoint,
        source_container=source_container,
        sas=sas,
    )
    search = AzureSearchSetup(
        endpoint=required("KNW001_SEARCH_ENDPOINT"),
        credential=credential,
    )
    search.configure(data_source, index, indexer)
    search.run_indexer(indexer_name)
    print(f"Search indexer configured and run requested; SAS expires {expiry.isoformat()}.")


if __name__ == "__main__":
    main()