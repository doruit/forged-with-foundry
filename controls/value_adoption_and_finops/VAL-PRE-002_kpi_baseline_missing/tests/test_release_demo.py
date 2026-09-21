"""Execute the workflow candidate step and test Azure orchestration without credentials."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

CONTROL_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = CONTROL_DIR.parents[2]
WORKFLOW_PATH = REPOSITORY_ROOT / ".github/workflows/val-pre-002-baseline-gate-demo.yml"
WORKFLOW = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
SUBPROCESS_ENV = {
    **os.environ,
    "PATH": f"{Path(sys.executable).parent}{os.pathsep}{os.environ.get('PATH', '')}",
}


@pytest.mark.skipif(shutil.which("conftest") is None, reason="conftest is not installed")
@pytest.mark.parametrize(
    "scenario,allowed",
    [
        ("measured", True), ("net_new", True), ("invalid_value", False),
        ("invalid_date", False), ("missing_evidence", False), ("empty_evidence", False),
        ("missing_control", False), ("missing_contract", False), ("missing_agent", False),
        ("validator_error", False), ("conftest_error", False),
    ],
)
def test_given_candidate_when_workflow_gate_runs_then_only_valid_candidate_reaches_deployment(
    tmp_path: Path, scenario: str, allowed: bool,
) -> None:
    for directory in ("schemas", "policy", "examples"):
        (tmp_path / directory).symlink_to(REPOSITORY_ROOT / directory, target_is_directory=True)
    shutil.copytree(REPOSITORY_ROOT / "scripts", tmp_path / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    candidate = tmp_path / "candidate"
    shutil.copytree(CONTROL_DIR / "candidate", candidate)
    contract_path = candidate / ".fwf/agents/helpdesk-tier1-triage/governance.yaml"
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    entry = contract["spec"]["controls"][0]
    if scenario == "net_new":
        entry["evidence"]["baseline"] = {"status": "net_new"}
    elif scenario == "invalid_value":
        entry["evidence"]["baseline"]["value"] = "not-a-number"
    elif scenario == "invalid_date":
        entry["evidence"]["baseline"]["measuredDate"] = "2026-02-30"
    elif scenario == "missing_evidence":
        del entry["evidence"]
    elif scenario == "empty_evidence":
        entry["evidence"] = {}
    elif scenario == "missing_control":
        sibling = CONTROL_DIR.parent / "VAL-PRE-001_value_hypothesis_missing/fixtures/complete-workload"
        contract = yaml.safe_load((sibling / ".fwf/agents/helpdesk-tier1-triage/governance.yaml").read_text(encoding="utf-8"))
    contract_path.write_text(yaml.safe_dump(contract), encoding="utf-8")
    if scenario == "missing_contract":
        contract_path.unlink()
    elif scenario == "missing_agent":
        shutil.rmtree(contract_path.parent)
    elif scenario == "validator_error":
        (tmp_path / "scripts/validate_governance_contract.py").write_text("raise RuntimeError('test execution failure')\n", encoding="utf-8")
    environment = {**SUBPROCESS_ENV, "CANDIDATE_ROOT": str(candidate), "GITHUB_OUTPUT": str(tmp_path / "outputs")}
    if scenario == "conftest_error":
        binary_dir = tmp_path / "bin"
        binary_dir.mkdir()
        binary = binary_dir / "conftest"
        binary.write_text("#!/bin/sh\nexit 42\n", encoding="utf-8")
        binary.chmod(0o755)
        environment["PATH"] = f"{binary_dir}{os.pathsep}{environment['PATH']}"
    step = next(step for step in WORKFLOW["jobs"]["candidate-gate"]["steps"] if step.get("id") == "candidate")

    result = subprocess.run(
        ["bash", "-c", step["run"] + '\nprintf deployed > deployment-reached\n'],
        cwd=tmp_path, env=environment, capture_output=True, text=True, check=False,
    )

    assert (result.returncode == 0) == allowed, result.stdout + result.stderr
    assert (tmp_path / "deployment-reached").exists() == allowed
    assert (tmp_path / "outputs").exists() == allowed
    if allowed:
        assert (tmp_path / "outputs").read_text(encoding="utf-8") == "baseline_status=complete\n"
        evidence = json.loads((tmp_path / "val-pre-002-gate-evidence.json").read_text(encoding="utf-8"))
        assert evidence["outcome"] == "allowed"
        assert evidence["evaluatedControls"] == ["VAL-PRE-002"]


def test_given_workflow_when_release_is_selected_then_successful_candidate_is_required() -> None:
    jobs = WORKFLOW["jobs"]

    assert jobs["release"]["needs"] == "candidate-gate"
    assert jobs["release"]["if"] == "github.event_name == 'workflow_dispatch' && inputs.route == 'combined'"
    assert "needs" not in jobs["policy-denial-experiment"]
    assert jobs["policy-denial-experiment"]["if"] == "github.event_name == 'workflow_dispatch' && inputs.route == 'policy-only'"
    assert "permissions" not in jobs["candidate-gate"]
    assert WORKFLOW["permissions"] == {"contents": "read"}
    assert "fixtures" not in WORKFLOW["env"]["CANDIDATE_ROOT"]
    for job in jobs.values():
        assert "continue-on-error" not in job
        assert all("continue-on-error" not in step for step in job["steps"])
    release_step = jobs["release"]["steps"][-1]
    assert release_step["env"]["BASELINE_STATUS"] == "${{ needs.candidate-gate.outputs.baseline_status }}"


FAKE_AZ = r'''
import json
import os
import sys
from pathlib import Path

arguments = sys.argv[1:]
state_path = Path(os.environ["AZ_TEST_STATE"])
state = json.loads(state_path.read_text())
state["calls"].append(arguments)
state_path.write_text(json.dumps(state))
scenario = os.environ["AZ_TEST_SCENARIO"]
if arguments[:2] == ["resource", "list"]:
    if scenario == "list-error":
        sys.exit(1)
    print(json.dumps(state["resources"]))
elif arguments[:3] == ["deployment", "group", "list"]:
    print(json.dumps(state["deployments"]))
elif arguments[:3] == ["deployment", "group", "create"]:
    name = arguments[arguments.index("--name") + 1]
    run_id = os.environ["DEMO_RUN_ID"]
    state["deployments"] = [{"name": name, "properties": {"parameters": {
        "demoRunId": {"value": run_id}, "demoResourceName": {"value": name}
    }}}]
    if scenario in ("deny", "other-policy", "auth-error"):
        state_path.write_text(json.dumps(state))
        message = {"deny": "RequestDisallowedByPolicy val-pre-002-kpi-baseline-gate-assignment",
                   "other-policy": "RequestDisallowedByPolicy unrelated-assignment",
                   "auth-error": "AuthorizationFailed"}[scenario]
        print(message, file=sys.stderr)
        sys.exit(1)
    state["resources"].append({"name": name, "id": "/synthetic/" + name, "tags": {
        "control-id": "VAL-PRE-002", "purpose": "governance-control-demo",
        "demo-run-id": run_id, "kpiBaselineStatus": "complete"
    }})
    state_path.write_text(json.dumps(state))
elif arguments[:2] == ["resource", "delete"]:
    if scenario == "cleanup-error":
        sys.exit(1)
    resource_id = arguments[arguments.index("--ids") + 1]
    state["resources"] = [resource for resource in state["resources"] if resource["id"] != resource_id]
    state_path.write_text(json.dumps(state))
elif arguments[:3] == ["deployment", "group", "delete"]:
    state["deployments"] = []
    state_path.write_text(json.dumps(state))
else:
    raise AssertionError(arguments)
'''


@pytest.mark.skipif(shutil.which("jq") is None, reason="jq is not installed")
@pytest.mark.parametrize(
    "mode,scenario,success",
    [
        ("release", "allow", True), ("policy-only", "deny", True),
        ("policy-only", "allow", False), ("policy-only", "auth-error", False),
        ("policy-only", "other-policy", False), ("release", "cleanup-error", False),
        ("release", "list-error", False), ("release", "collision", False),
        ("cleanup-release", "foreign-resource", False),
        ("cleanup-release", "foreign-deployment", False),
    ],
)
def test_given_azure_result_when_demo_runs_then_verifies_denial_and_scoped_cleanup(
    tmp_path: Path, mode: str, scenario: str, success: bool,
) -> None:
    binary = tmp_path / "az"
    binary.write_text(f"#!{sys.executable}\n" + FAKE_AZ, encoding="utf-8")
    binary.chmod(0o755)
    unrelated = {"name": "other-control", "id": "/synthetic/other-control", "tags": {"control-id": "VAL-PRE-001"}}
    state = {"resources": [unrelated], "deployments": [], "calls": []}
    if scenario in ("collision", "foreign-resource"):
        state["resources"].append({**unrelated, "name": "valpre002-release-123-1"})
    if scenario == "foreign-deployment":
        state["deployments"].append({"name": "valpre002-release-123-1", "properties": {"parameters": {}}})
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    environment = {
        **SUBPROCESS_ENV, "PATH": f"{tmp_path}{os.pathsep}{SUBPROCESS_ENV['PATH']}",
        "AZURE_RESOURCE_GROUP": "synthetic-test-rg", "DEMO_RUN_ID": "123-1",
        "BASELINE_STATUS": "complete", "AZ_TEST_STATE": str(state_path), "AZ_TEST_SCENARIO": scenario,
    }

    result = subprocess.run(
        ["bash", str(CONTROL_DIR / "azure-demo.sh"), mode], env=environment,
        capture_output=True, text=True, check=False,
    )

    final = json.loads(state_path.read_text(encoding="utf-8"))
    assert (result.returncode == 0) == success, result.stdout + result.stderr
    assert unrelated in final["resources"]
    if scenario in ("collision", "foreign-resource", "foreign-deployment", "list-error"):
        assert not any("delete" in call or "create" in call for call in final["calls"])
    elif scenario != "cleanup-error":
        assert final["resources"] == [unrelated]
        assert final["deployments"] == []
    if mode == "policy-only" and success:
        assert "RequestDisallowedByPolicy" in result.stdout