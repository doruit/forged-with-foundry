from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.aut_002.foundry import FoundrySession, RECORD_ID, TOOL_NAME, tool_request


def response(*, name: str = TOOL_NAME, arguments: str = '{"record_id":"synthetic-record-001"}') -> SimpleNamespace:
    return SimpleNamespace(id="resp-synthetic", output=[SimpleNamespace(
        type="function_call", name=name, call_id="call-synthetic", arguments=arguments,
    )])


def test_real_call_shape_is_required() -> None:
    request = tool_request(response())
    assert request.args() == {"record_id": RECORD_ID}
    assert request.call_id == "call-synthetic"


@pytest.mark.parametrize("result", [
    SimpleNamespace(id="resp-synthetic", output=[]),
    response(name="unguarded_delete"), response(arguments="{}"), response(arguments="bad"),
    response(arguments='{"record_id":"other-record"}'),
    response(arguments='{"record_id":"other-record","record_id":"synthetic-record-001"}'),
])
def test_invalid_call_never_reaches_execution(result: SimpleNamespace) -> None:
    with pytest.raises(ValueError):
        tool_request(result)


def test_tool_result_returns_to_exact_call_and_agent_version() -> None:
    client = Mock()
    client.responses.create.return_value = SimpleNamespace(id="resp-final", output_text="Verified result")
    reference = {"name": "synthetic-agent", "type": "agent_reference", "version": "1"}
    session = FoundrySession(client, reference, "synthetic-model")
    request = tool_request(response())
    session.complete(request, {"executed": True, "verified": True})
    supplied = client.responses.create.call_args.kwargs
    assert supplied["previous_response_id"] == request.response_id
    assert supplied["input"][0]["call_id"] == request.call_id
    assert supplied["extra_body"]["agent_reference"] == reference
    assert supplied["tool_choice"] == "none"


def test_permission_diagnostic_excludes_principal_and_prompt():
    import httpx
    from openai import PermissionDeniedError

    error = PermissionDeniedError("not for display", response=httpx.Response(403, request=httpx.Request("POST", "https://synthetic.example/responses")),
                                  body={"message": "synthetic-principal cannot Microsoft.CognitiveServices/accounts/AIServices/responses/write; synthetic-private-prompt"})
    client = Mock()
    client.responses.create.side_effect = error
    session = FoundrySession(client, {"name": "synthetic"}, "synthetic")
    with pytest.raises(PermissionDeniedError) as raised:
        session.request("private")
    assert raised.value.required_permission == "Microsoft.CognitiveServices/accounts/AIServices/responses/write"
    assert "synthetic-principal" not in raised.value.required_permission