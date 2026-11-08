from datetime import UTC, datetime
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from azure.ai.projects.models import AzureAISearchQueryType
from foundry_probe import build_definition, build_observation, run_probe


NOW = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)
SOURCE_URI = "https://syntheticstorage.blob.core.windows.net/source/travel-policy.md"


def test_agent_definition_uses_foundry_prompt_agent_and_native_search_tool():
    definition = build_definition(
        model_deployment="approved-synthetic-model",
        connection_id="/connections/knw001-search",
        index_name="knw001-knowledge",
    ).as_dict()

    assert definition["kind"] == "prompt"
    assert definition["model"] == "approved-synthetic-model"
    assert "Do not infer whether a source is fresh or approved." in definition["instructions"]
    search_tool = definition["tools"][0]
    assert search_tool["type"] == "azure_ai_search"
    index = search_tool["azure_ai_search"]["indexes"][0]
    assert index["index_name"] == "knw001-knowledge"
    assert index["project_connection_id"] == "/connections/knw001-search"
    assert index["query_type"] == AzureAISearchQueryType.SIMPLE.value


def test_observation_keeps_service_ids_and_citation_digest_but_not_answer_text():
    response = SimpleNamespace(
        id="resp-synthetic-1",
        status="completed",
        output=[
            SimpleNamespace(type="azure_ai_search_call", id="call-synthetic-1"),
            SimpleNamespace(
                type="message",
                id="msg-synthetic-1",
                content=[SimpleNamespace(
                    text="This answer must not be persisted.",
                    annotations=[SimpleNamespace(
                        type="url_citation",
                        url=f"{SOURCE_URI}?temporary-signature=excluded",
                    )],
                )],
            ),
        ],
    )

    record = build_observation(
        response=response,
        agent_id="agent-synthetic-1",
        agent_name="knw001-probe-synthetic",
        agent_version="1",
        correlation_id="correlation-synthetic-1",
        source_uri=SOURCE_URI,
        etag_before='"synthetic-etag"',
        etag_after='"synthetic-etag"',
        observed_at=NOW,
    )

    assert record["response_completed"] is True
    assert record["response_id"] == "resp-synthetic-1"
    assert record["search_call_ids"] == ["call-synthetic-1"]
    assert record["citation_matches_configured_blob"] is True
    assert record["blob_etag_unchanged_during_probe"] is True
    assert "temporary-signature" not in repr(record)
    assert "This answer must not be persisted" not in repr(record)


@pytest.mark.parametrize("status", ["failed", "incomplete"])
def test_incomplete_agent_response_is_not_a_successful_observation(status):
    record = build_observation(
        response=SimpleNamespace(id="resp-synthetic-2", status=status, output=[]),
        agent_id="agent-synthetic-1",
        agent_name="knw001-probe-synthetic",
        agent_version="1",
        correlation_id="correlation-synthetic-2",
        source_uri=SOURCE_URI,
        etag_before='"etag-1"',
        etag_after='"etag-2"',
        observed_at=NOW,
    )

    assert record["response_completed"] is False
    assert record["citation_matches_configured_blob"] is False
    assert record["blob_etag_unchanged_during_probe"] is False


def test_probe_creates_agent_calls_search_records_metadata_and_deletes_agent():
    response = SimpleNamespace(
        id="resp-synthetic-3",
        status="completed",
        output=[SimpleNamespace(type="azure_ai_search_call", id="call-synthetic-3")],
    )

    class OpenAI:
        def __init__(self):
            self.closed = False
            self.responses = self

        def create(self, **kwargs):
            assert kwargs["tool_choice"] == "required"
            assert kwargs["max_tool_calls"] == 1
            assert kwargs["max_output_tokens"] == 256
            assert kwargs["store"] is False
            assert kwargs["metadata"]["knw001_correlation_id"] == "correlation-3"
            assert "private question" in kwargs["input"]
            return response

        def close(self):
            self.closed = True

    class Agents:
        def __init__(self):
            self.deleted = []

        def create_version(self, **kwargs):
            assert kwargs["definition"].kind == "prompt"
            return SimpleNamespace(id="agent-id", name=kwargs["agent_name"], version="1")

        def delete(self, **kwargs):
            self.deleted.append(kwargs)

    class Evidence:
        def __init__(self):
            self.records = []

        def write(self, record):
            self.records.append(record)

    class Project:
        def __init__(self):
            self.agents = Agents()
            self.openai = OpenAI()
            self.connections = SimpleNamespace(
                get=lambda name: SimpleNamespace(id=f"/connections/{name}")
            )

        def get_openai_client(self, *, agent_name):
            assert agent_name.startswith("knw001-probe-")
            return self.openai

    project = Project()
    evidence = Evidence()
    etags = iter(['"etag-1"', '"etag-1"'])
    blob = SimpleNamespace(
        get_blob_properties=lambda: SimpleNamespace(etag=next(etags))
    )

    record = run_probe(
        project=project,
        blob_client=blob,
        evidence_writer=evidence,
        model_deployment="approved-synthetic-model",
        connection_name="knw001-search",
        index_name="knw001-knowledge",
        question="A private question that must not be stored.",
        source_uri=SOURCE_URI,
        correlation_id="correlation-3",
        observed_at=NOW,
    )

    assert record["response_id"] == "resp-synthetic-3"
    assert evidence.records == [record]
    assert project.openai.closed is True
    assert project.agents.deleted == [{"agent_name": "knw001-probe-correlat", "force": True}]
    assert "private question" not in repr(record)


def test_probe_deletes_temporary_agent_when_foundry_call_fails():
    deleted = []

    class OpenAI:
        responses = SimpleNamespace(
            create=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("service unavailable"))
        )
        closed = False

        def close(self):
            self.closed = True

    openai = OpenAI()
    project = SimpleNamespace(
        connections=SimpleNamespace(
            get=lambda name: SimpleNamespace(id=f"/connections/{name}")
        ),
        agents=SimpleNamespace(
            create_version=lambda **kwargs: SimpleNamespace(
                id="agent-id", name=kwargs["agent_name"], version="1"
            ),
            delete=lambda **kwargs: deleted.append(kwargs),
        ),
        get_openai_client=lambda **kwargs: openai,
    )
    blob = SimpleNamespace(
        get_blob_properties=lambda: SimpleNamespace(etag='"etag-1"')
    )

    with pytest.raises(RuntimeError, match="service unavailable"):
        run_probe(
            project=project,
            blob_client=blob,
            evidence_writer=SimpleNamespace(write=lambda record: None),
            model_deployment="approved-synthetic-model",
            connection_name="knw001-search",
            index_name="knw001-knowledge",
            question="synthetic question",
            source_uri=SOURCE_URI,
            correlation_id="correlation-4",
            observed_at=NOW,
        )

    assert openai.closed is True
    assert deleted == [{"agent_name": "knw001-probe-correlat", "force": True}]