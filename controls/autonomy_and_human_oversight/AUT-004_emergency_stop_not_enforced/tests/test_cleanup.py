"""AUT-004 cleanup: ownership first, only explicit not-found counts as absent."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location("aut_004_cleanup", Path(__file__).resolve().parents[1] / "infra" / "cleanup.py")
cleanup = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(cleanup)

SUB = "00000000-0000-0000-0000-000000000000"
RG = f"/subscriptions/{SUB}/resourceGroups/rg/providers"
ACCOUNT = f"{RG}/Microsoft.CognitiveServices/accounts/acc"
STATE = {
    "control_id": "AUT-004", "subscription_id": SUB, "agentVersion": "1",
    "projectId": f"{ACCOUNT}/projects/aut-004", "webAppId": f"{RG}/Microsoft.Web/sites/aut004-x",
    "planId": f"{RG}/Microsoft.Web/serverfarms/aut004-x-plan",
    "identityId": f"{RG}/Microsoft.ManagedIdentity/userAssignedIdentities/aut004-x-identity",
    "storeId": f"{RG}/Microsoft.AppConfiguration/configurationStores/aut004-x-switch",
    "workspaceId": f"{RG}/Microsoft.OperationalInsights/workspaces/aut004-x-logs",
    "identityPrincipalId": "mi", "operator_principal_id": "op",
    "application_object_id": "app-1", "service_principal_id": "sp-1", "application_client_id": "client-1",
}
STATE["roleAssignmentIds"] = [f"{STATE['storeId']}/providers/Microsoft.Authorization/roleAssignments/r1",
                              f"{ACCOUNT}/providers/Microsoft.Authorization/roleAssignments/r2"]


def _ok(body):
    return subprocess.CompletedProcess([], 0, json.dumps(body), "")


def _missing():
    return subprocess.CompletedProcess([], 1, "", "ERROR: Not Found(ResourceNotFound)")


class FakeAzure:
    def __init__(self, *, tag="AUT-004", notes=None, read_error=None, sp_tags=("ForgedWithFoundry", "AUT-004")):
        self.present = {STATE[k] for k in cleanup.DELETE_ORDER} | set(STATE["roleAssignmentIds"]) | {"app-1", "sp-1"}
        self.tag, self.read_error, self.deleted, self.sp_tags = tag, read_error, [], list(sp_tags)
        self.notes = notes or f"Forged with Foundry AUT-004; resource={STATE['webAppId']}"

    def _target(self, url):
        path = url.split("https://management.azure.com", 1)[-1].split("?", 1)[0]
        return path if path.startswith("/subscriptions") else url.rsplit("/", 1)[-1]

    def __call__(self, *arguments):
        if arguments[:2] == ("account", "show"):
            return _ok({"id": SUB})
        method, target = arguments[2], self._target(arguments[-1])
        if method == "get":
            if self.read_error:
                return subprocess.CompletedProcess([], 1, "", self.read_error)
            if target not in self.present:
                return _missing()
            if target == "app-1":
                return _ok({"notes": self.notes})
            if target == "sp-1":
                return _ok({"appId": "client-1", "tags": self.sp_tags})
            if "roleAssignments" in target:
                return _ok({"properties": {"principalId": "mi"}})
            return _ok({"tags": {"control-id": self.tag}})
        self.present.discard(target)
        self.deleted.append(target)
        return _ok({})


def test_cleanup_removes_everything_owned(monkeypatch):
    fake = FakeAzure()
    monkeypatch.setattr(cleanup, "az", fake)
    agent = []
    cleanup.cleanup(STATE, delete_agent=agent.append, sleep=lambda _s: None)
    assert agent and fake.present == set()


@pytest.mark.parametrize("kwargs", [{"tag": "AUT-002"}, {"notes": "someone else's app"}, {"sp_tags": ["SomeOtherApp"]}])
def test_foreign_resources_stop_cleanup_before_any_delete(monkeypatch, kwargs):
    fake = FakeAzure(**kwargs)
    monkeypatch.setattr(cleanup, "az", fake)
    with pytest.raises(cleanup.CleanupError):
        cleanup.cleanup(STATE, delete_agent=lambda _s: pytest.fail("no deletes"))
    assert fake.deleted == []


def test_role_assignment_outside_owned_scopes_is_refused(monkeypatch):
    state = {**STATE, "roleAssignmentIds": [f"{RG}/Microsoft.Web/sites/other/providers/Microsoft.Authorization/roleAssignments/x"]}
    monkeypatch.setattr(cleanup, "az", FakeAzure())
    with pytest.raises(cleanup.CleanupError, match="outside"):
        cleanup.cleanup(state, delete_agent=lambda _s: None)


def test_cli_error_is_not_treated_as_absent(monkeypatch):
    monkeypatch.setattr(cleanup, "az", FakeAzure(read_error="ERROR: AADSTS700082 token expired"))
    with pytest.raises(cleanup.CleanupError):
        cleanup.cleanup(STATE, delete_agent=lambda _s: None)


def test_app_configuration_entity_not_found_counts_as_absent():
    result = subprocess.CompletedProcess([], 1, "", 'ERROR: Not Found({"error":{"code":"EntityNotFound"}})')
    assert cleanup._missing(result)
