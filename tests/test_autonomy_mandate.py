import hashlib
import json
import sys
import subprocess
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from resolve_autonomy_mandate import resolve_mandate
from validate_governance_contract import ContractReadError, validate_contract
from build_deployment_plan import build_plan


def declaration():
    return {"agentId": "synthetic-agent", "mandateVersion": "1.0.0", "purpose": "Synthetic records only",
            "defaultDecision": "deny", "actions": [{"toolName": "delete_record", "disposition": "approval_required",
            "targets": ["synthetic-record-001"], "reversibility": "irreversible", "impact": ["operational"],
            "riskReviewRef": "RISK-001", "approval": {"kind": "human_approval", "approverRole": "OpsManager",
            "ttlSeconds": 300, "evidenceRequired": ["action_identity", "decision", "executed", "verified"]}}]}


def contract(tmp_path, controls=("AUT-PRE-001", "AUT-PRE-002")):
    raw = json.dumps(declaration()).encode()
    (tmp_path / "mandate.yaml").write_bytes(raw)
    entries = [{"id": identifier, "version": "1.0.0", "evidence": {
        "mandate": {"path": "mandate.yaml", "sha256": hashlib.sha256(raw).hexdigest()},
        "accountableRole": "AI Governance" if identifier == "AUT-PRE-001" else "Business Owner",
        "reviewRef": "REVIEW-001", "reviewedOn": "2026-10-07"}} for identifier in controls]
    return {"apiVersion": "forgedwithfoundry.dev/v1alpha1", "kind": "AgentGovernanceContract",
            "metadata": {"agentId": "synthetic-agent", "description": "Synthetic mandate", "source": "https://github.com/doruit/forged-with-foundry", "license": "MIT"},
            "spec": {"agentRef": {"definition": "definition.json"}, "controls": entries}}


@pytest.mark.parametrize("controls", [("AUT-PRE-001",), ("AUT-PRE-002",), ("AUT-PRE-001", "AUT-PRE-002")])
def test_standalone_and_combined_references_validate(tmp_path, controls):
    document = contract(tmp_path, controls)
    assert validate_contract(document, agent_dir_name="synthetic-agent") == []
    assert resolve_mandate(document, tmp_path, tmp_path)["errors"] == []


def test_changed_bytes_cannot_reuse_review(tmp_path):
    document = contract(tmp_path)
    (tmp_path / "mandate.yaml").write_text("{}")
    with pytest.raises(ContractReadError, match="hash"):
        resolve_mandate(document, tmp_path, tmp_path)


@pytest.mark.parametrize("path", ["../mandate.yaml", "/tmp/mandate.yaml", "https://example.com/mandate"])
def test_unsafe_references_fail_closed(tmp_path, path):
    document = contract(tmp_path)
    document["spec"]["controls"][0]["evidence"]["mandate"]["path"] = path
    document["spec"]["controls"][1]["evidence"]["mandate"]["path"] = path
    with pytest.raises(ContractReadError, match="unsafe"):
        resolve_mandate(document, tmp_path, tmp_path)


def gate(tmp_path, mandate, controls=("AUT-PRE-001", "AUT-PRE-002")):
    agent_dir = tmp_path / ".fwf/agents/synthetic-agent"
    agent_dir.mkdir(parents=True)
    document = contract(agent_dir, controls)
    raw = json.dumps(mandate).encode()
    (agent_dir / "mandate.yaml").write_bytes(raw)
    for entry in document["spec"]["controls"]:
        entry["evidence"]["mandate"]["sha256"] = hashlib.sha256(raw).hexdigest()
    (agent_dir / "governance.yaml").write_text(json.dumps(document))
    definition = {"tools": [{"name": "delete_record", "type": "function", "parameters": {
        "type": "object", "properties": {"record_id": {"type": "string", "enum": ["synthetic-record-001"]}},
        "required": ["record_id"], "additionalProperties": False}}]}
    (tmp_path / "definition.json").write_text(json.dumps(definition))
    manifest = {"expectedAgents": ["synthetic-agent"], "candidateDefinitions": {"synthetic-agent": "definition.json"},
                "profiles": {"paired": {"requiredControls": list(controls)}}}
    (tmp_path / "profile.yaml").write_text(json.dumps(manifest))
    environment = {**os.environ, "PATH": f"{Path(sys.executable).parent}:{os.environ['PATH']}"}
    return subprocess.run([str(ROOT / "scripts/deployment_gate.sh"), "--manifest", str(tmp_path / "profile.yaml"),
                           "--profile", "paired", "--root", str(tmp_path)], env=environment, capture_output=True, text=True)


def test_complete_mandate_passes_real_shared_gate(tmp_path):
    result = gate(tmp_path, declaration())
    assert result.returncode == 0, result.stderr


def test_missing_gate_is_a_distinct_policy_denial(tmp_path):
    mandate = declaration()
    del mandate["actions"][0]["approval"]
    result = gate(tmp_path, mandate)
    assert result.returncode == 1, result.stderr
    assert "AUT-PRE-002: human_gate_incomplete" in result.stderr


def test_prohibited_action_never_accepts_approval(tmp_path):
    mandate = declaration()
    mandate["actions"][0]["disposition"] = "prohibited"
    result = gate(tmp_path, mandate)
    assert result.returncode == 1, result.stderr
    assert "AUT-PRE-001: contradictory_permission" in result.stderr