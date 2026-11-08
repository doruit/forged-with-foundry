from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
import sys
from uuid import uuid4

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    AISearchIndexResource,
    AzureAISearchQueryType,
    AzureAISearchTool,
    AzureAISearchToolResource,
    PromptAgentDefinition,
)
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from knw001.monitor import BlobEvidenceWriter


def build_definition(*, model_deployment: str, connection_id: str, index_name: str):
    return PromptAgentDefinition(
        model=model_deployment,
        instructions=(
            "Answer the user's question only from the connected knowledge index. "
            "You must always provide citations for answers using the tool and render them "
            "as: `[message_idx:search_idx†source]`. If the index does not contain the answer, say so. "
            "Do not infer whether a source is fresh or approved."
        ),
        tools=[
            AzureAISearchTool(
                azure_ai_search=AzureAISearchToolResource(
                    indexes=[
                        AISearchIndexResource(
                            project_connection_id=connection_id,
                            index_name=index_name,
                            query_type=AzureAISearchQueryType.SIMPLE,
                        )
                    ]
                )
            )
        ],
    )


def _value(value, name: str, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _resource_uri(value: str) -> str:
    url = httpx.URL(value)
    return f"{url.scheme}://{url.host}{url.path.rstrip('/')}"


def build_observation(
    *,
    response,
    agent_id: str,
    agent_name: str,
    agent_version: str,
    correlation_id: str,
    source_uri: str,
    etag_before: str | None,
    etag_after: str | None,
    observed_at: datetime | None = None,
) -> dict:
    citations: list[str] = []
    output_items: list[dict[str, str | None]] = []
    search_call_ids: list[str] = []

    for item in _value(response, "output", []) or []:
        item_type = _value(item, "type")
        item_id = _value(item, "id")
        output_items.append({"id": item_id, "type": item_type})
        if isinstance(item_type, str) and "search" in item_type.lower():
            if isinstance(item_id, str):
                search_call_ids.append(item_id)
        for content in _value(item, "content", []) or []:
            for annotation in _value(content, "annotations", []) or []:
                if _value(annotation, "type") == "url_citation":
                    url = _value(annotation, "url")
                    if isinstance(url, str):
                        citations.append(url)

    response_status = _value(response, "status")
    completed = isinstance(response_status, str) and response_status.lower() == "completed"
    citation_hashes = sorted({hashlib.sha256(url.encode()).hexdigest() for url in citations})
    source_matches = False
    try:
        expected_uri = _resource_uri(source_uri)
        source_matches = any(_resource_uri(url) == expected_uri for url in citations)
    except (httpx.InvalidURL, ValueError):
        pass

    timestamp = observed_at or datetime.now(UTC)
    return {
        "control_id": "KNW-001",
        "policy_version": os.environ.get("KNW001_POLICY_VERSION", "knw001-v1"),
        "correlation_id": correlation_id,
        "timestamp": timestamp.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "event_type": "foundry_agent_observation",
        "agent_id": agent_id,
        "agent_name": agent_name,
        "agent_version": agent_version,
        "response_id": _value(response, "id"),
        "response_status": response_status,
        "response_completed": completed,
        "output_items": output_items,
        "search_call_ids": search_call_ids,
        "citation_url_sha256": citation_hashes,
        "citation_matches_configured_blob": source_matches,
        "source_uri_sha256": hashlib.sha256(source_uri.encode()).hexdigest(),
        "source_etag_sha256": hashlib.sha256(etag_before.encode()).hexdigest()
        if etag_before else None,
        "blob_etag_unchanged_during_probe": bool(etag_before and etag_before == etag_after),
        "accountable_role": "Knowledge Owner",
    }


def run_probe(
    *,
    project: AIProjectClient,
    blob_client,
    evidence_writer: BlobEvidenceWriter,
    model_deployment: str,
    connection_name: str,
    index_name: str,
    question: str,
    source_uri: str,
    correlation_id: str | None = None,
    observed_at: datetime | None = None,
) -> dict:
    run_id = correlation_id or str(uuid4())
    connection = project.connections.get(connection_name)
    agent_name = f"knw001-probe-{run_id[:8]}"
    agent = project.agents.create_version(
        agent_name=agent_name,
        definition=build_definition(
            model_deployment=model_deployment,
            connection_id=connection.id,
            index_name=index_name,
        ),
        description="Ephemeral KNW-001 knowledge retrieval observation.",
    )
    try:
        etag_before = blob_client.get_blob_properties().etag
        openai = project.get_openai_client(agent_name=agent.name)
        try:
            response = openai.responses.create(
                input=question,
                tool_choice="required",
                max_tool_calls=1,
                max_output_tokens=256,
                store=False,
                metadata={"knw001_correlation_id": run_id},
            )
        finally:
            openai.close()
        etag_after = blob_client.get_blob_properties().etag
        record = build_observation(
            response=response,
            agent_id=agent.id,
            agent_name=agent.name,
            agent_version=str(agent.version),
            correlation_id=run_id,
            source_uri=source_uri,
            etag_before=etag_before,
            etag_after=etag_after,
            observed_at=observed_at,
        )
        evidence_writer.write(record)
        return record
    finally:
        project.agents.delete(agent_name=agent.name, force=True)


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"Required application setting {name} is missing.")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run one Foundry knowledge retrieval observation and remove its temporary agent."
    )
    parser.parse_args()
    credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
    blob_endpoint = _required("KNW001_BLOB_ENDPOINT")
    source_container = _required("KNW001_SOURCE_CONTAINER")
    source_blob = _required("KNW001_SOURCE_BLOB")
    blob_service = BlobServiceClient(blob_endpoint, credential=credential)
    source_client = blob_service.get_blob_client(source_container, source_blob)
    evidence_writer = BlobEvidenceWriter(
        blob_service.get_container_client(_required("KNW001_EVIDENCE_CONTAINER"))
    )
    source_uri = source_client.url
    project_endpoint = _required("KNW001_FOUNDRY_PROJECT_ENDPOINT")
    question = _required("KNW001_AGENT_QUESTION")

    try:
        with AIProjectClient(endpoint=project_endpoint, credential=credential) as project:
            record = run_probe(
                project=project,
                blob_client=source_client,
                evidence_writer=evidence_writer,
                model_deployment=_required("KNW001_FOUNDRY_MODEL"),
                connection_name=_required("KNW001_FOUNDRY_SEARCH_CONNECTION"),
                index_name=_required("KNW001_SEARCH_INDEX"),
                question=question,
                source_uri=source_uri,
            )
        print(json.dumps(record, sort_keys=True))
    finally:
        blob_service.close()
        credential.close()


if __name__ == "__main__":
    main()