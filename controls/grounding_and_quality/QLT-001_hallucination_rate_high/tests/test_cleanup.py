"""Cleanup must refuse targets outside this control's explicit ownership."""

from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("qlt001_cleanup", Path(__file__).resolve().parents[1] / "infra/cleanup.py")
cleanup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cleanup)


def resources():
    prefix = "/subscriptions/test/resourceGroups/demo/providers/"
    tags = {"control-id": "QLT-001", "purpose": "synthetic-groundedness-demo"}
    workspace = {"id": prefix + "Microsoft.OperationalInsights/workspaces/log-qlt001-test",
                 "name": "log-qlt001-test", "type": "Microsoft.OperationalInsights/workspaces", "tags": tags.copy()}
    insights = {"id": prefix + "Microsoft.Insights/components/appi-qlt001-test",
                "name": "appi-qlt001-test", "type": "Microsoft.Insights/components", "tags": tags.copy(),
                "properties": {"WorkspaceResourceId": workspace["id"]}}
    return insights, workspace


def test_given_owned_resources_when_checked_then_accepted():
    cleanup.validate_resources("test", "demo", *resources())


class _FakeAgentDetail:
    def __init__(self, name, kind, principal_id):
        self.name = name
        self.versions = {"latest": {"definition": {"kind": kind}}}
        self.instance_identity = {"principal_id": principal_id}


class _FakeAgentsOperations:
    def __init__(self, details):
        self._details = details

    def get(self, agent_id):
        return self._details[agent_id]


class _FakeClient:
    def __init__(self, details):
        self.agents = _FakeAgentsOperations(details)


def test_given_the_real_fleet_agents_when_verified_then_accepted():
    principal_ids = [f"principal-{index}" for index in range(len(cleanup.AGENTS))]
    details = {
        agent_id: _FakeAgentDetail(agent_id, "prompt", principal_ids[index])
        for index, agent_id in enumerate(cleanup.AGENTS)
    }
    client = _FakeClient(details)

    verified = cleanup.verified_agents(client, principal_ids)

    assert set(verified) == set(cleanup.AGENTS)


def test_given_a_non_prompt_agent_when_verified_then_refused():
    agent_id = cleanup.AGENTS[0]
    details = {a: _FakeAgentDetail(a, "prompt", "p") for a in cleanup.AGENTS}
    details[agent_id] = _FakeAgentDetail(agent_id, "hosted", "p")
    client = _FakeClient(details)

    with pytest.raises(ValueError):
        cleanup.verified_agents(client, None)


def test_given_a_mismatched_principal_id_when_verified_then_refused():
    details = {a: _FakeAgentDetail(a, "prompt", "expected") for a in cleanup.AGENTS}
    client = _FakeClient(details)
    wrong_principal_ids = ["wrong"] * len(cleanup.AGENTS)

    with pytest.raises(ValueError):
        cleanup.verified_agents(client, wrong_principal_ids)


@pytest.mark.parametrize("mutation", ["tag", "name", "group", "type", "link", "purpose"])
def test_given_wrong_ownership_when_checked_then_refused(mutation):
    insights, workspace = deepcopy(resources())
    if mutation == "tag":
        insights["tags"]["control-id"] = "OTHER"
    elif mutation == "purpose":
        insights["tags"]["purpose"] = "production"
    elif mutation == "name":
        insights["name"] = "shared"
    elif mutation == "group":
        insights["id"] = insights["id"].replace("/demo/", "/shared/")
    elif mutation == "type":
        workspace["type"] = "Microsoft.Resources/resourceGroups"
    else:
        insights["properties"]["WorkspaceResourceId"] = "/shared/workspace"

    with pytest.raises(ValueError):
        cleanup.validate_resources("test", "demo", insights, workspace)
