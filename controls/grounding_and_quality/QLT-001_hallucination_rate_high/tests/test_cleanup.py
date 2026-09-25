"""Cleanup must refuse targets outside this control's explicit ownership."""

from copy import deepcopy
import importlib.util
from pathlib import Path
import sys

import pytest

CONTROL = Path(__file__).resolve().parents[1]
sys.modules.pop("workload", None)
sys.path.insert(0, str(CONTROL))
SPEC = importlib.util.spec_from_file_location("qlt001_cleanup", CONTROL / "infra/cleanup.py")
cleanup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cleanup)
sys.path.remove(str(CONTROL))
sys.modules.pop("workload", None)


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


class _FakeRule:
    def __init__(self, agent_id, eval_id):
        self.filter = type("Filter", (), {"agent_name": agent_id})()
        self.action = type("Action", (), {"eval_id": eval_id})()


class _FakeEvaluationRules:
    def __init__(self, rules):
        self._rules = rules

    def get(self, rule_id):
        return self._rules[rule_id]


class _FakeEvals:
    def __init__(self, name):
        self._name = name

    def retrieve(self, eval_id):
        return type("Eval", (), {"name": self._name})()


class _FakeEvaluationClient:
    def __init__(self, rules, eval_name=cleanup.EVAL_NAME):
        self.evaluation_rules = _FakeEvaluationRules(rules)
        self._openai = type("OpenAI", (), {"evals": _FakeEvals(eval_name)})()

    def get_openai_client(self):
        return self._openai


def test_given_exact_fleet_rules_and_owned_eval_when_verified_then_accepted():
    eval_id = "eval-owned"
    rules = {
        f"{agent_id}-rule": _FakeRule(agent_id, eval_id)
        for agent_id in cleanup.AGENTS
    }

    actual_eval_id, rule_ids = cleanup.verified_evaluation_configuration(
        _FakeEvaluationClient(rules))

    assert actual_eval_id == eval_id
    assert rule_ids == tuple(f"{agent_id}-rule" for agent_id in cleanup.AGENTS)


def test_given_rules_with_different_evals_when_verified_then_refused():
    rules = {
        f"{agent_id}-rule": _FakeRule(agent_id, f"eval-{index}")
        for index, agent_id in enumerate(cleanup.AGENTS)
    }

    with pytest.raises(ValueError, match="do not share"):
        cleanup.verified_evaluation_configuration(_FakeEvaluationClient(rules))


def test_given_foreign_eval_name_when_verified_then_refused():
    rules = {
        f"{agent_id}-rule": _FakeRule(agent_id, "eval-foreign")
        for agent_id in cleanup.AGENTS
    }

    with pytest.raises(ValueError, match="not owned"):
        cleanup.verified_evaluation_configuration(
            _FakeEvaluationClient(rules, eval_name="another-project-eval"))


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
