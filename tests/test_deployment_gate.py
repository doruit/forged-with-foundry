"""End-to-end integration tests for the deployment enforcement boundary:
scripts/build_deployment_plan.py -> conftest test policy/governance-contract
-> scripts/deployment_gate.sh. These exercise the real `conftest` CLI (not a
mocked Rego input) and are skipped when conftest is not installed, so a
contributor without conftest can still run the rest of the suite; CI
installs the pinned conftest version so these run for real there. See
docs/governance-contract.md#policy-layer.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
GATE_SCRIPT = REPOSITORY_ROOT / "scripts" / "deployment_gate.sh"
BUILD_PLAN_SCRIPT = REPOSITORY_ROOT / "scripts" / "build_deployment_plan.py"
POLICY_DIR = REPOSITORY_ROOT / "policy" / "governance-contract"

requires_conftest = pytest.mark.skipif(shutil.which("conftest") is None, reason="conftest is not installed")

# deployment_gate.sh shells out to a bare `python3`; make sure that resolves
# to the same interpreter running this test suite (and its installed
# dependencies), not whatever unrelated python3 happens to be first on the
# outer shell's PATH.
_SUBPROCESS_ENV = {**os.environ, "PATH": f"{Path(sys.executable).parent}{os.pathsep}{os.environ.get('PATH', '')}"}

_VALID_VAL_PRE_001_ENTRY = {
    "id": "VAL-PRE-001",
    "version": "1.0.0",
    "evidence": {
        "owner": "it-service-desk-manager@contoso.example",
        "businessCaseId": "BIZ-CASE-HELPDESK-001",
        "expectedOutcome": "Reduce Tier-1 tickets that need a human agent",
        "metric": {"name": "tier1_ticket_deflection_rate", "direction": "increase", "target": 35},
        "baseline": {"status": "net_new"},
    },
}


def _write_contract(root: Path, agent_id: str, entries: list[dict]) -> None:
    agent_dir = root / ".fwf" / "agents" / agent_id
    agent_dir.mkdir(parents=True, exist_ok=True)
    contract = {
        "apiVersion": "forgedwithfoundry.dev/v1alpha1",
        "kind": "AgentGovernanceContract",
        "metadata": {
            "agentId": agent_id,
            "description": "test fixture",
            "source": "https://example.com/x",
            "license": "MIT",
        },
        "spec": {"agentRef": {"definition": "./agent.yaml"}, "controls": entries},
    }
    (agent_dir / "governance.yaml").write_text(yaml.safe_dump(contract), encoding="utf-8")


def _write_manifest(path: Path, *, expected_agents: list[str], required_controls: list[str]) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "expectedAgents": expected_agents,
                "profiles": {"test-profile": {"requiredControls": required_controls}},
            }
        ),
        encoding="utf-8",
    )


def _run_gate(manifest: Path, root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(GATE_SCRIPT), "--manifest", str(manifest), "--profile", "test-profile", "--root", str(root)],
        capture_output=True,
        text=True,
        env=_SUBPROCESS_ENV,
    )


def test_build_deployment_plan_reports_agent_folder_without_a_contract(tmp_path: Path) -> None:
    (tmp_path / ".fwf" / "agents" / "no-contract-agent").mkdir(parents=True)
    manifest = tmp_path / "manifest.yaml"
    _write_manifest(manifest, expected_agents=["no-contract-agent"], required_controls=["VAL-PRE-001"])

    result = subprocess.run(
        [sys.executable, str(BUILD_PLAN_SCRIPT), "--manifest", str(manifest), "--profile", "test-profile", "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=True,
        env=_SUBPROCESS_ENV,
    )
    plan = json.loads(result.stdout)
    assert plan["discoveredAgents"] == [{"agentId": "no-contract-agent", "contractPath": str(tmp_path / ".fwf" / "agents" / "no-contract-agent" / "governance.yaml"), "hasContract": False}]


@requires_conftest
def test_zero_contracts_denies_deployment_via_real_conftest_cli(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.yaml"
    _write_manifest(manifest, expected_agents=["ghost-agent"], required_controls=["VAL-PRE-001"])
    result = _run_gate(manifest, tmp_path)
    assert result.returncode == 1
    assert "no discovered .fwf/agents/ folder" in (result.stdout + result.stderr)


@requires_conftest
def test_two_expected_agents_with_only_one_contract_denies_via_real_conftest_cli(tmp_path: Path) -> None:
    _write_contract(tmp_path, "covered-agent", [_VALID_VAL_PRE_001_ENTRY])
    manifest = tmp_path / "manifest.yaml"
    _write_manifest(manifest, expected_agents=["covered-agent", "uncovered-agent"], required_controls=["VAL-PRE-001"])
    result = _run_gate(manifest, tmp_path)
    assert result.returncode == 1
    assert "uncovered-agent" in (result.stdout + result.stderr)


@requires_conftest
def test_deleting_the_entire_agent_folder_still_denies(tmp_path: Path) -> None:
    _write_contract(tmp_path, "temporary-agent", [_VALID_VAL_PRE_001_ENTRY])
    manifest = tmp_path / "manifest.yaml"
    _write_manifest(manifest, expected_agents=["temporary-agent"], required_controls=["VAL-PRE-001"])

    allowed = _run_gate(manifest, tmp_path)
    assert allowed.returncode == 0

    shutil.rmtree(tmp_path / ".fwf" / "agents" / "temporary-agent")
    denied = _run_gate(manifest, tmp_path)
    assert denied.returncode == 1


@requires_conftest
def test_removing_a_required_control_denies_even_if_the_remaining_contract_is_schema_valid(tmp_path: Path) -> None:
    kpi_entry = {"id": "VAL-PRE-002", "version": "1.0.0", "evidence": {"baseline": {"status": "net_new"}}}
    _write_contract(tmp_path, "two-control-agent", [_VALID_VAL_PRE_001_ENTRY, kpi_entry])
    manifest = tmp_path / "manifest.yaml"
    _write_manifest(manifest, expected_agents=["two-control-agent"], required_controls=["VAL-PRE-001", "VAL-PRE-002"])
    allowed = _run_gate(manifest, tmp_path)
    assert allowed.returncode == 0

    _write_contract(tmp_path, "two-control-agent", [_VALID_VAL_PRE_001_ENTRY])  # VAL-PRE-002 entry removed
    denied = _run_gate(manifest, tmp_path)
    assert denied.returncode == 1
    assert "VAL-PRE-002" in (denied.stdout + denied.stderr)


@requires_conftest
def test_fully_covered_agent_is_allowed_and_produces_evidence(tmp_path: Path) -> None:
    _write_contract(tmp_path, "covered-agent", [_VALID_VAL_PRE_001_ENTRY])
    manifest = tmp_path / "manifest.yaml"
    _write_manifest(manifest, expected_agents=["covered-agent"], required_controls=["VAL-PRE-001"])
    evidence_out = tmp_path / "evidence.json"

    result = subprocess.run(
        [str(GATE_SCRIPT), "--manifest", str(manifest), "--profile", "test-profile", "--root", str(tmp_path), "--evidence-out", str(evidence_out)],
        capture_output=True,
        text=True,
        env=_SUBPROCESS_ENV,
    )
    assert result.returncode == 0
    evidence = json.loads(evidence_out.read_text(encoding="utf-8"))
    assert evidence["outcome"] == "allowed"
    assert evidence["expectedAgents"] == ["covered-agent"]
    assert evidence["evaluatedControls"] == ["VAL-PRE-001"]
    assert "covered-agent" in evidence["contractHashes"]
    assert "not proof that the underlying business assertions are true" in evidence["disclaimer"]


@requires_conftest
def test_deployment_gate_conftest_policy_tests_pass() -> None:
    result = subprocess.run(
        ["conftest", "verify", "--policy", str(POLICY_DIR)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
