"""Verify each fleet profile's own declaration: schema shape, not model behavior.

``agent.py`` has no heavy import-time dependency (registration only imports
``azure.ai.projects.models`` inside ``register_agent``), so this test can
import it directly like any other module in this control.
"""

from pathlib import Path
import sys

import pytest

CONTROL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CONTROL))

import agent  # noqa: E402
from workload import CONTRACTOR, FLEET, PLATFORM, REGIONAL  # noqa: E402


class _FakeAgentsOperations:
    def __init__(self):
        self.calls = []

    def create_version(self, *, agent_name, definition):
        self.calls.append((agent_name, definition))
        return definition


class _FakeClient:
    def __init__(self):
        self.agents = _FakeAgentsOperations()


@pytest.mark.parametrize("profile", FLEET)
def test_given_a_fleet_profile_when_registered_then_uses_its_own_agent_id(profile):
    client = _FakeClient()

    agent.register_agent(client, profile, model="gpt-5-mini")

    ((name, definition),) = client.agents.calls
    assert name == profile.agent_id
    assert definition.kind == "prompt"
    assert definition.model == "gpt-5-mini"


@pytest.mark.parametrize("profile", FLEET)
def test_given_a_fleet_profile_when_registered_then_declares_the_kb_lookup_tool(profile):
    client = _FakeClient()

    agent.register_agent(client, profile, model="gpt-5-mini")

    ((_, definition),) = client.agents.calls
    (tool,) = definition.tools
    assert tool.name == "lookup_it_kb"
    assert set(tool.parameters["required"]) == {"topic", "window"}
    assert tool.parameters["properties"]["topic"]["enum"] == [
        "vpn_setup",
        "password_reset",
        "license_renewal",
    ]


@pytest.mark.parametrize("profile", FLEET)
def test_given_a_fleet_profile_when_registered_then_response_schema_requires_self_report(profile):
    client = _FakeClient()

    agent.register_agent(client, profile, model="gpt-5-mini")

    ((_, definition),) = client.agents.calls
    schema = definition.text.format.schema
    assert set(schema["required"]) == {
        "answer",
        "self_reported_confidence",
        "suggested_followups",
    }
    assert schema["properties"]["self_reported_confidence"]["minimum"] == 1
    assert schema["properties"]["self_reported_confidence"]["maximum"] == 5


@pytest.mark.parametrize("profile", [PLATFORM, REGIONAL])
def test_given_a_strict_profile_when_built_then_forbids_guessing_on_missing_articles(profile):
    assert "never invent" in agent.instructions_for(profile)


def test_given_the_contractor_profile_when_built_then_permits_labeled_assumptions():
    text = agent.instructions_for(CONTRACTOR)

    assert "reasonable assumption" in text
    assert "never invent" not in text
