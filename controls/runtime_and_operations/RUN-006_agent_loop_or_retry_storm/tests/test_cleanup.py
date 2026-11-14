"""Cleanup must treat only Azure 'not found' as absent, check ownership, and verify."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import importlib.util

# Load under a control-specific name: several controls ship an infra/cleanup.py.
_SPEC = importlib.util.spec_from_file_location(
    "run_006_cleanup", Path(__file__).resolve().parents[1] / "infra" / "cleanup.py"
)
cleanup = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(cleanup)

SUB = "/subscriptions/00000000-0000-0000-0000-000000000000"
RG = f"{SUB}/resourceGroups/rg/providers"
PROJECT = f"{RG}/Microsoft.CognitiveServices/accounts/acc/projects/run-006"
APPI = f"{RG}/Microsoft.Insights/components/run006-appi"
WORKSPACE = f"{RG}/Microsoft.OperationalInsights/workspaces/run006-logs"
RULE = f"{RG}/Microsoft.Insights/scheduledQueryRules/run006-loop"
GROUP = f"{RG}/Microsoft.Insights/actionGroups/run006-ai-ops-lead"
APPI_ROLE = f"{APPI}/providers/Microsoft.Authorization/roleAssignments/r1"
PROJECT_ROLE = f"{PROJECT}/providers/Microsoft.Authorization/roleAssignments/r2"
OWNED = [RULE, GROUP, APPI_ROLE, PROJECT_ROLE, APPI, WORKSPACE, PROJECT]
STATE = {"control_id": "RUN-006", "projectId": PROJECT, "ownedResources": OWNED}


def _result(code=0, stdout="", stderr=""):
    return subprocess.CompletedProcess([], code, stdout, stderr)


class FakeAzure:
    def __init__(self, *, tags=None, read_error=None):
        self.present = set(OWNED)
        self.tags = tags or {}
        self.read_error = read_error
        self.deleted: list[str] = []

    def _resource(self, url):
        path = url.split("https://management.azure.com", 1)[1].split("?", 1)[0]
        return path, "force=true" in url

    def __call__(self, *arguments):
        if arguments[:2] == ("account", "show"):
            return _result(stdout=json.dumps({"id": SUB.rsplit("/", 1)[1]}))
        method, url = arguments[2], arguments[-1]
        path, force = self._resource(url)
        if method == "get":
            if self.read_error:
                return _result(1, stderr=self.read_error)
            if path in self.present:
                return _result(stdout=json.dumps({"tags": {"control-id": self.tags.get(path, "RUN-006")}}))
            return _result(1, stderr="ERROR: Not Found(ResourceNotFound)")
        if method == "delete":
            if path == WORKSPACE:
                assert force, "workspace must be force-deleted so the name is not held in soft delete"
            self.present.discard(path)
            self.deleted.append(path)
            return _result()
        raise AssertionError(arguments)


def test_cleanup_deletes_every_owned_resource_and_verifies(monkeypatch):
    fake = FakeAzure()
    monkeypatch.setattr(cleanup, "az", fake)
    agent = []
    cleanup.cleanup(STATE, delete_agent=lambda: agent.append(1), sleep=lambda _s: None)
    assert agent == [1]
    assert fake.deleted == OWNED
    assert fake.present == set()


def test_foreign_tag_stops_cleanup_before_any_delete(monkeypatch):
    fake = FakeAzure(tags={APPI: "AUT-002"})
    monkeypatch.setattr(cleanup, "az", fake)
    with pytest.raises(cleanup.CleanupError, match="not owned"):
        cleanup.cleanup(STATE, delete_agent=lambda: pytest.fail("no deletes expected"))
    assert fake.deleted == []


def test_role_assignment_outside_owned_scopes_is_refused(monkeypatch):
    foreign = f"{RG}/Microsoft.Insights/components/shared/providers/Microsoft.Authorization/roleAssignments/x"
    state = {**STATE, "ownedResources": [foreign]}
    fake = FakeAzure()
    fake.present.add(foreign)
    monkeypatch.setattr(cleanup, "az", fake)
    with pytest.raises(cleanup.CleanupError, match="not owned"):
        cleanup.cleanup(state, delete_agent=lambda: None)


def test_cli_failure_is_not_treated_as_absent(monkeypatch):
    monkeypatch.setattr(cleanup, "az", FakeAzure(read_error="ERROR: AADSTS700082 token expired"))
    with pytest.raises(cleanup.CleanupError):
        cleanup.cleanup(STATE, delete_agent=lambda: None)


def test_resource_type_parsing():
    assert cleanup.resource_type(PROJECT) == "Microsoft.CognitiveServices/accounts/projects"
    assert cleanup.resource_type(APPI_ROLE) == "Microsoft.Authorization/roleAssignments"
    assert cleanup.resource_type(RULE) == "Microsoft.Insights/scheduledQueryRules"
