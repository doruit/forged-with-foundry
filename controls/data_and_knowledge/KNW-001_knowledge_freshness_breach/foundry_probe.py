from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from datetime import UTC, datetime
from pathlib import Path
import sys
import time
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

PROJECT_LOOKUP_MESSAGE = "Project not found"
DEFAULT_WAIT_MINUTES = 20.0
RETRY_INTERVAL_SECONDS = 20.0
CLEANUP_WAIT_SECONDS = 300.0


class ProbeNotReadyError(RuntimeError):
    """The Foundry project still rejected agent calls when the wait budget ended."""


class AgentCleanupError(RuntimeError):
    """The temporary agent could not be deleted and needs manual removal."""


def is_retryable_project_lookup(error: BaseException) -> bool:
    return getattr(error, "status_code", None) == 404 and PROJECT_LOOKUP_MESSAGE in str(error)


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


def _delete_agent(
    project: AIProjectClient,
    agent_name: str,
    *,
    wait_seconds: float,
    interval_seconds: float,
    sleep,
    monotonic,
) -> None:
    deadline = monotonic() + wait_seconds
    while True:
        try:
            project.agents.delete(agent_name=agent_name, force=True)
            return
        except Exception as error:
            if not is_retryable_project_lookup(error) or monotonic() + interval_seconds > deadline:
                raise AgentCleanupError(
                    f"Temporary agent {agent_name} was not deleted ({type(error).__name__}). "
                    "Delete it in the Foundry portal, or run the control cleanup action."
                ) from error
            sleep(interval_seconds)


def _probe_once(
    *,
    project: AIProjectClient,
    blob_client,
    evidence_writer: BlobEvidenceWriter,
    model_deployment: str,
    connection_name: str,
    index_name: str,
    question: str,
    source_uri: str,
    run_id: str,
    agent_name: str,
    observed_at: datetime | None,
    cleanup_wait_seconds: float,
    interval_seconds: float,
    sleep,
    monotonic,
) -> dict:
    connection = project.connections.get(connection_name)
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
        openai = project.get_openai_client()
        try:
            response = openai.responses.create(
                input=question,
                tool_choice="required",
                max_tool_calls=1,
                max_output_tokens=256,
                store=False,
                metadata={"knw001_correlation_id": run_id},
                extra_body={
                    "agent_reference": {
                        "type": "agent_reference",
                        "name": agent.name,
                        "version": str(agent.version),
                    }
                },
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
        _delete_agent(
            project,
            agent.name,
            wait_seconds=cleanup_wait_seconds,
            interval_seconds=interval_seconds,
            sleep=sleep,
            monotonic=monotonic,
        )


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
    wait_seconds: float = 0.0,
    retry_interval_seconds: float = RETRY_INTERVAL_SECONDS,
    cleanup_wait_seconds: float = CLEANUP_WAIT_SECONDS,
    sleep=time.sleep,
    monotonic=time.monotonic,
) -> dict:
    run_id = correlation_id or str(uuid4())
    started = monotonic()
    attempt = 0
    while True:
        attempt += 1
        # Each attempt uses a new agent name, so it never reuses a path that already failed.
        agent_name = f"knw001-probe-{run_id[:8]}" + (f"-{attempt}" if attempt > 1 else "")
        try:
            return _probe_once(
                project=project,
                blob_client=blob_client,
                evidence_writer=evidence_writer,
                model_deployment=model_deployment,
                connection_name=connection_name,
                index_name=index_name,
                question=question,
                source_uri=source_uri,
                run_id=run_id,
                agent_name=agent_name,
                observed_at=observed_at,
                cleanup_wait_seconds=cleanup_wait_seconds,
                interval_seconds=retry_interval_seconds,
                sleep=sleep,
                monotonic=monotonic,
            )
        except Exception as error:
            if not is_retryable_project_lookup(error) or wait_seconds <= 0:
                raise
            if monotonic() + retry_interval_seconds > started + wait_seconds:
                raise ProbeNotReadyError(
                    f"Foundry still answered 404 ({PROJECT_LOOKUP_MESSAGE}) after {attempt} attempts over "
                    f"{monotonic() - started:.0f} s. Verify the project endpoint and service "
                    "availability before retrying; waiting does not repair a wrong endpoint."
                ) from error
            print(
                f"Foundry project lookup failed (attempt {attempt}: {PROJECT_LOOKUP_MESSAGE}); "
                f"retrying in {retry_interval_seconds:.0f} s.",
                file=sys.stderr,
            )
            sleep(retry_interval_seconds)


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"Required application setting {name} is missing.")
    return value


def _wait_minutes(value: str) -> float:
    minutes = float(value)
    if not math.isfinite(minutes) or minutes < 0:
        raise argparse.ArgumentTypeError("Wait minutes must be finite and non-negative.")
    return minutes


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run one Foundry knowledge retrieval observation and remove its temporary agent."
    )
    parser.add_argument(
        "--wait-minutes",
        type=_wait_minutes,
        default=DEFAULT_WAIT_MINUTES,
        help=(
            "Retry budget for HTTP 404 'Project not found'; this does not establish "
            "that the cause is propagation delay. Other errors are not retried. "
            "Use 0 to try once. Default: %(default)s."
        ),
    )
    args = parser.parse_args()
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
                wait_seconds=args.wait_minutes * 60,
            )
        print(json.dumps(record, sort_keys=True))
    except (ProbeNotReadyError, AgentCleanupError) as error:
        raise SystemExit(f"foundry_probe: {error}") from None
    finally:
        blob_service.close()
        credential.close()


if __name__ == "__main__":
    main()