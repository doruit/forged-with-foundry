"""Registered Foundry prompt agent whose function calls the host routes through ACS."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from azure.ai.projects.models import FunctionTool, PromptAgentDefinition

from . import AGENT_ID
from .tools import ORDERS, TICKETS, TOOL_NAMES

INSTRUCTIONS = (
    "You are Contoso's support refunds agent. You work only on synthetic demo data. "
    "Look up the order with lookup_order before deciding. "
    "Call issue_refund only for an order whose lookup shows eligible_for_refund true. "
    "If issue_refund returns an error, do not retry it; tell the customer a specialist will follow up. "
    "Finish by calling reply_to_ticket once with a short summary for the ticket. "
    "Never claim a refund that a tool did not confirm."
)

_ORDER = {"type": "string", "enum": sorted(ORDERS)}
TOOL_PARAMETERS: dict[str, dict[str, Any]] = {
    "lookup_order": {
        "type": "object",
        "properties": {"order_id": _ORDER},
        "required": ["order_id"],
        "additionalProperties": False,
    },
    "issue_refund": {
        "type": "object",
        "properties": {"order_id": _ORDER},
        "required": ["order_id"],
        "additionalProperties": False,
    },
    "reply_to_ticket": {
        "type": "object",
        "properties": {
            "ticket_id": {"type": "string", "enum": list(TICKETS)},
            "summary": {"type": "string"},
        },
        "required": ["ticket_id", "summary"],
        "additionalProperties": False,
    },
}
TOOL_DESCRIPTIONS = {
    "lookup_order": "Look up one synthetic order and whether it is eligible for a refund.",
    "issue_refund": "Issue a refund for one eligible synthetic order.",
    "reply_to_ticket": "Record a reply on the synthetic support ticket.",
}


def agent_definition(model: str) -> PromptAgentDefinition:
    return PromptAgentDefinition(
        model=model,
        instructions=INSTRUCTIONS,
        tools=[
            FunctionTool(
                name=name,
                description=TOOL_DESCRIPTIONS[name],
                parameters=TOOL_PARAMETERS[name],
                strict=True,
            )
            for name in TOOL_NAMES
        ],
    )


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_tool_argument")
        result[key] = value
    return result


@dataclass(frozen=True)
class FunctionCall:
    name: str
    call_id: str
    args: dict[str, Any]


def parse_function_call(name: str, call_id: str, arguments: str) -> FunctionCall:
    if name not in TOOL_NAMES:
        raise ValueError("unknown_tool")
    if not isinstance(call_id, str) or not call_id:
        raise ValueError("missing_call_id")
    args = json.loads(arguments, object_pairs_hook=_unique_object)
    schema = TOOL_PARAMETERS[name]
    if not isinstance(args, dict) or set(args) != set(schema["required"]):
        raise ValueError("unexpected_tool_arguments")
    for key, rule in schema["properties"].items():
        if not isinstance(args[key], str) or ("enum" in rule and args[key] not in rule["enum"]):
            raise ValueError("unexpected_tool_arguments")
    return FunctionCall(name, call_id, args)


class AgentSession(Protocol):
    source: str

    def start(self, prompt: str) -> list[FunctionCall]: ...

    def submit(self, outputs: list[tuple[str, dict[str, Any]]]) -> list[FunctionCall]: ...

    def final_text(self) -> str: ...

    def correlation(self) -> dict[str, object]: ...

    def close(self) -> None: ...


class FoundryAgentSession:
    """Drive a registered prompt agent with the Responses API."""

    source = "foundry"

    def __init__(self, openai_client: Any, *, model: str, agent_version: str) -> None:
        self.client = openai_client
        self.model = model
        self.reference = {"type": "agent_reference", "name": AGENT_ID, "version": agent_version}
        self.response_ids: list[str] = []
        self.responses_created = 0
        self.responses_deleted = 0
        self.responses_delete_failed = 0
        self._last: Any = None

    @classmethod
    def from_environment(cls, credential: Any, environ: dict[str, str]) -> FoundryAgentSession:
        from azure.ai.projects import AIProjectClient

        project = AIProjectClient(endpoint=environ["AZURE_AI_PROJECT_ENDPOINT"], credential=credential)
        model, version = environ["AZURE_OPENAI_CHAT_DEPLOYMENT"], environ["AUT004_AGENT_VERSION"]
        deployed = project.agents.get_version(AGENT_ID, version).definition.as_dict()
        expected = agent_definition(model).as_dict()
        if any(deployed.get(key) != expected.get(key) for key in ("model", "instructions", "tools")):
            raise ValueError("deployed_agent_definition_drift")
        return cls(project.get_openai_client(), model=model, agent_version=version)

    def _calls(self, response: Any) -> list[FunctionCall]:
        self._last = response
        self.response_ids.append(response.id)
        self.responses_created += 1
        return [
            parse_function_call(item.name, item.call_id, item.arguments)
            for item in response.output
            if item.type == "function_call"
        ]

    def start(self, prompt: str) -> list[FunctionCall]:
        return self._calls(
            self.client.responses.create(
                model=self.model, input=prompt, extra_body={"agent_reference": self.reference}
            )
        )

    def submit(self, outputs: list[tuple[str, dict[str, Any]]]) -> list[FunctionCall]:
        return self._calls(
            self.client.responses.create(
                model=self.model,
                previous_response_id=self._last.id,
                input=[
                    {"type": "function_call_output", "call_id": call_id, "output": json.dumps(output)}
                    for call_id, output in outputs
                ],
                extra_body={"agent_reference": self.reference},
            )
        )

    def final_text(self) -> str:
        return self._last.output_text if self._last is not None else ""

    def correlation(self) -> dict[str, object]:
        return {
            "agent_name": AGENT_ID,
            "agent_version": self.reference["version"],
            "model_responses": self.responses_created,
            "stored_responses_deleted": self.responses_deleted,
            "stored_responses_delete_failed": self.responses_delete_failed,
        }

    def close(self) -> None:
        """Delete stored responses; they contain synthetic prompts only.

        A failed delete is counted, never raised, so it cannot block evidence
        or replace an earlier error.
        """
        for response_id in list(self.response_ids):
            try:
                self.client.responses.delete(response_id)
            except Exception:  # noqa: BLE001
                self.responses_delete_failed += 1
                continue
            self.response_ids.remove(response_id)
            self.responses_deleted += 1


class ScriptedSession:
    """Credential-free replay of fixed function calls for regression tests.

    Replay proves the gate's behaviour on a given call sequence, not what a
    real model would choose.
    """

    source = "scripted_replay"

    def __init__(self, rounds: list[list[tuple[str, dict[str, Any]]]]) -> None:
        self._rounds = list(rounds)
        self._index = 0
        self.model_calls = 0

    def _next(self) -> list[FunctionCall]:
        self.model_calls += 1
        if self._index >= len(self._rounds):
            return []
        calls = [
            parse_function_call(name, f"call_{self._index + 1}_{position + 1}", json.dumps(args))
            for position, (name, args) in enumerate(self._rounds[self._index])
        ]
        self._index += 1
        return calls

    def start(self, prompt: str) -> list[FunctionCall]:
        return self._next()

    def submit(self, outputs: list[tuple[str, dict[str, Any]]]) -> list[FunctionCall]:
        return self._next()

    def final_text(self) -> str:
        return "(scripted replay: no model text)"

    def correlation(self) -> dict[str, object]:
        return {
            "agent_name": AGENT_ID,
            "agent_version": None,
            "model_responses": self.model_calls,
            "stored_responses_deleted": 0,
            "stored_responses_delete_failed": 0,
        }

    def close(self) -> None:
        return None
