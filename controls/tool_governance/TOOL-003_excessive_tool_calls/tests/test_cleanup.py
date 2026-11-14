"""Cleanup must treat only Azure 'not found' as absent and fail on anything else."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import importlib.util

# Load under a control-specific name: several controls ship an infra/cleanup.py.
_SPEC = importlib.util.spec_from_file_location(
    "tool_003_cleanup", Path(__file__).resolve().parents[1] / "infra" / "cleanup.py"
)
cleanup = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(cleanup)

SUB = "00000000-0000-0000-0000-000000000000"
PROJECT = f"/subscriptions/{SUB}/resourceGroups/rg/providers/Microsoft.CognitiveServices/accounts/acc/projects/tool-003"
ROLE = f"{PROJECT}/providers/Microsoft.Authorization/roleAssignments/abc"
STATE = {"control_id": "TOOL-003", "projectId": PROJECT, "roleAssignmentId": ROLE}


def _result(code=0, stdout="", stderr=""):
    return subprocess.CompletedProcess([], code, stdout, stderr)


class FakeAzure:
    def __init__(self, *, tag="TOOL-003", read_error=None):
        self.present = {PROJECT: True, ROLE: True}
        self.tag = tag
        self.read_error = read_error
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, *arguments):
        self.calls.append(arguments)
        if arguments[:2] == ("account", "show"):
            return _result(stdout=json.dumps({"id": SUB}))
        if arguments[0] == "rest":
            if self.read_error:
                return _result(1, stderr=self.read_error)
            resource = next(key for key in sorted(self.present, key=len, reverse=True) if key in arguments[-1])
            if self.present[resource]:
                return _result(stdout=json.dumps({"tags": {"control-id": self.tag}}))
            return _result(1, stderr="ERROR: Not Found(ResourceNotFound)")
        if arguments[:3] == ("role", "assignment", "delete"):
            self.present[ROLE] = False
            return _result()
        if arguments[:2] == ("resource", "delete"):
            self.present[PROJECT] = False
            return _result()
        raise AssertionError(arguments)


def test_cleanup_deletes_owned_resources_and_verifies_absence(monkeypatch):
    fake = FakeAzure()
    monkeypatch.setattr(cleanup, "az", fake)
    deleted = []
    cleanup.cleanup(STATE, delete_agent=lambda: deleted.append("agent"))
    assert deleted == ["agent"]
    assert fake.present == {PROJECT: False, ROLE: False}


def test_cli_failure_is_not_treated_as_absent(monkeypatch):
    monkeypatch.setattr(cleanup, "az", FakeAzure(read_error="ERROR: AADSTS700082: refresh token expired"))
    with pytest.raises(cleanup.CleanupError):
        cleanup.cleanup(STATE, delete_agent=lambda: None)


def test_project_without_control_tag_is_never_deleted(monkeypatch):
    fake = FakeAzure(tag="AUT-002")
    monkeypatch.setattr(cleanup, "az", fake)
    with pytest.raises(cleanup.CleanupError, match="not tagged"):
        cleanup.cleanup(STATE, delete_agent=lambda: pytest.fail("agent must not be deleted"))
    assert fake.present[PROJECT] is True


def test_signed_out_cli_stops_cleanup(monkeypatch):
    monkeypatch.setattr(cleanup, "az", lambda *a: _result(1, stderr="Please run 'az login'"))
    with pytest.raises(cleanup.CleanupError, match="not signed in"):
        cleanup.cleanup(STATE, delete_agent=lambda: None)


def test_main_keeps_state_when_cleanup_fails(monkeypatch, tmp_path):
    state = tmp_path / "deployment.json"
    state.write_text(json.dumps(STATE))
    monkeypatch.setattr(cleanup, "STATE_PATH", state)
    monkeypatch.setattr(cleanup, "az", FakeAzure(read_error="ERROR: throttled"))
    monkeypatch.setitem(sys.modules, "agent_registry", type(sys)("agent_registry"))
    sys.modules["agent_registry"].delete_agent = lambda _state: None
    assert cleanup.main() == 1
    assert state.is_file()
