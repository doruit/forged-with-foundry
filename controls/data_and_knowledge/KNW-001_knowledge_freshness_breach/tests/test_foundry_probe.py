from datetime import UTC, datetime
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import AzureAISearchQueryType
from foundry_probe import (
    AgentCleanupError,
    ProbeNotReadyError,
    build_definition,
    build_observation,
    is_retryable_project_lookup,
    main,
    run_probe,
)


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
            assert kwargs["extra_body"]["agent_reference"] == {
                "type": "agent_reference",
                "name": "knw001-probe-correlat",
                "version": "1",
            }
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

        def get_openai_client(self):
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


class NotFound(Exception):
    status_code = 404


def not_ready(message="Project not found"):
    return NotFound(f"Error code: 404 - {message}")


class Clock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def make_project(
    *, create_failures=(), respond_failures=(), delete_failures=(), created=None, deleted=None
):
    """Fake project whose calls raise the queued errors before they start succeeding."""
    create_queue = list(create_failures)
    respond_queue = list(respond_failures)
    delete_queue = list(delete_failures)
    created = [] if created is None else created
    deleted = [] if deleted is None else deleted
    response = SimpleNamespace(
        id="resp-synthetic-5",
        status="completed",
        output=[SimpleNamespace(type="azure_ai_search_call", id="call-synthetic-5")],
    )

    def create_version(**kwargs):
        created.append(kwargs["agent_name"])
        if create_queue:
            raise create_queue.pop(0)
        return SimpleNamespace(id="agent-id", name=kwargs["agent_name"], version="1")

    def respond(**kwargs):
        if respond_queue:
            raise respond_queue.pop(0)
        return response

    def delete(**kwargs):
        if delete_queue:
            raise delete_queue.pop(0)
        deleted.append(kwargs["agent_name"])

    openai = SimpleNamespace(responses=SimpleNamespace(create=respond), close=lambda: None)
    return SimpleNamespace(
        connections=SimpleNamespace(get=lambda name: SimpleNamespace(id=f"/connections/{name}")),
        agents=SimpleNamespace(create_version=create_version, delete=delete),
        get_openai_client=lambda **kwargs: openai,
    )


def probe(project, evidence=None, **overrides):
    return run_probe(
        project=project,
        blob_client=SimpleNamespace(get_blob_properties=lambda: SimpleNamespace(etag='"etag-1"')),
        evidence_writer=evidence or SimpleNamespace(write=lambda record: None),
        model_deployment="approved-synthetic-model",
        connection_name="knw001-search",
        index_name="knw001-knowledge",
        question="synthetic question",
        source_uri=SOURCE_URI,
        correlation_id="correlation-5",
        observed_at=NOW,
        **overrides,
    )


def test_probe_uses_sdk_project_responses_route_with_exact_agent_version():
    import json

    requests = []

    def respond(request):
        requests.append(request)
        assert request.url.path == "/api/projects/synthetic-project/openai/v1/responses"
        body = json.loads(request.content)
        assert body["agent_reference"] == {
            "type": "agent_reference",
            "name": "knw001-probe-correlat",
            "version": "1",
        }
        assert body["store"] is False
        assert body["tool_choice"] == "required"
        return httpx.Response(200, json={
            "id": "resp-synthetic-sdk",
            "status": "completed",
            "output": [],
        })

    with AIProjectClient(
        endpoint="https://synthetic.services.ai.azure.com/api/projects/synthetic-project",
        credential=SimpleNamespace(),
    ) as sdk:
        project = make_project()
        project.get_openai_client = lambda: sdk.get_openai_client(
            api_key="synthetic-test-key",
            http_client=httpx.Client(transport=httpx.MockTransport(respond)),
        )
        record = probe(project)

    assert len(requests) == 1
    assert record["response_id"] == "resp-synthetic-sdk"


def test_retryable_project_lookup_does_not_classify_wrong_routes_as_propagation():
    assert is_retryable_project_lookup(not_ready())
    assert not is_retryable_project_lookup(not_ready("Subdomain does not map to a resource."))
    assert not is_retryable_project_lookup(not_ready("Agent not found"))
    assert not is_retryable_project_lookup(RuntimeError("Project not found"))
    forbidden = NotFound("Project not found")
    forbidden.status_code = 403
    assert not is_retryable_project_lookup(forbidden)


def test_probe_waits_for_a_new_project_and_uses_a_fresh_agent_name_per_attempt():
    clock = Clock()
    created, deleted = [], []
    project = make_project(
        create_failures=[not_ready("Project not found"), not_ready()],
        created=created,
        deleted=deleted,
    )

    record = probe(
        project, wait_seconds=120, retry_interval_seconds=20,
        sleep=clock.sleep, monotonic=clock.monotonic,
    )

    assert record["response_status"] == "completed"
    assert record["agent_name"] == "knw001-probe-correlat-3"
    assert clock.sleeps == [20, 20]
    assert created == [
        "knw001-probe-correlat",
        "knw001-probe-correlat-2",
        "knw001-probe-correlat-3",
    ]
    assert deleted == ["knw001-probe-correlat-3"]


def test_probe_deletes_the_agent_of_a_not_ready_attempt_before_retrying():
    clock = Clock()
    created, deleted = [], []
    project = make_project(respond_failures=[not_ready()], created=created, deleted=deleted)

    probe(project, wait_seconds=120, sleep=clock.sleep, monotonic=clock.monotonic)

    assert created == ["knw001-probe-correlat", "knw001-probe-correlat-2"]
    assert deleted == ["knw001-probe-correlat", "knw001-probe-correlat-2"]


def test_probe_gives_up_with_a_clear_error_when_the_project_never_becomes_ready():
    clock = Clock()
    created = []
    project = make_project(create_failures=[not_ready("Project not found")] * 50, created=created)

    with pytest.raises(ProbeNotReadyError, match=r"Project not found.*4 attempts over 60 s"):
        probe(
            project, wait_seconds=60, retry_interval_seconds=20,
            sleep=clock.sleep, monotonic=clock.monotonic,
        )

    assert clock.sleeps == [20, 20, 20]
    assert len(created) == 4


@pytest.mark.parametrize("message", ["Agent not found", "Subdomain does not map to a resource."])
def test_probe_does_not_retry_other_not_found_errors(message):
    clock = Clock()
    project = make_project(respond_failures=[not_ready(message)])

    with pytest.raises(NotFound, match=message):
        probe(project, wait_seconds=120, sleep=clock.sleep, monotonic=clock.monotonic)

    assert clock.sleeps == []


@pytest.mark.parametrize("value", ["nan", "inf", "-inf", "-1"])
def test_cli_rejects_unbounded_or_negative_wait_before_service_access(value, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["foundry_probe.py", f"--wait-minutes={value}"])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert "Wait minutes must be finite and non-negative." in capsys.readouterr().err


def test_probe_without_a_wait_budget_raises_the_original_not_ready_error():
    project = make_project(create_failures=[not_ready("Project not found")])

    with pytest.raises(NotFound, match="Project not found"):
        probe(project)


def test_probe_retries_agent_deletion_until_the_project_accepts_it():
    clock = Clock()
    deleted = []
    project = make_project(delete_failures=[not_ready(), not_ready()], deleted=deleted)

    record = probe(project, sleep=clock.sleep, monotonic=clock.monotonic)

    assert record["response_status"] == "completed"
    assert deleted == ["knw001-probe-correlat"]
    assert clock.sleeps == [20, 20]


def test_probe_reports_a_temporary_agent_that_could_not_be_deleted():
    clock = Clock()
    records = []
    project = make_project(delete_failures=[not_ready()] * 50)

    with pytest.raises(AgentCleanupError, match="knw001-probe-correlat"):
        probe(
            project,
            evidence=SimpleNamespace(write=records.append),
            cleanup_wait_seconds=40,
            sleep=clock.sleep,
            monotonic=clock.monotonic,
        )

    assert len(records) == 1


def test_probe_stops_retrying_when_a_failed_attempt_leaves_an_agent_behind():
    clock = Clock()
    created = []
    project = make_project(
        respond_failures=[not_ready()],
        delete_failures=[RuntimeError("forbidden")],
        created=created,
    )

    with pytest.raises(AgentCleanupError, match="knw001-probe-correlat"):
        probe(project, wait_seconds=600, sleep=clock.sleep, monotonic=clock.monotonic)

    assert created == ["knw001-probe-correlat"]
    assert clock.sleeps == []