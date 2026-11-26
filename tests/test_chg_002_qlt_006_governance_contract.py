"""Governance-contract tests for CHG-002 and QLT-006."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_governance_contract as vgc

from test_governance_contract_consistency import VALID_HELPDESK_CONTRACT

CATEGORY = Path(__file__).resolve().parents[1] / "controls" / "change_release_and_evaluation"
CHG_002 = {
    "id": "CHG-002",
    "version": "1.0.0",
    "evidence": {
        "regressionPolicy": {
            "datasetPath": "dataset/regression.jsonl",
            "datasetSha256": "a" * 64,
            "requiredEvaluators": ["builtin.similarity"],
            "minPassRate": 0.75,
            "maxRegressionPp": 5,
            "minScoredItems": 12,
        },
        "candidate": {
            "agentName": "chg-002-support-assistant",
            "agentVersion": "2",
            "deploymentName": "chg002-candidate",
            "modelAssetId": "azureml://registries/azure-openai/models/gpt-5-mini/versions/2025-08-07",
            "versionUpgradeOption": "NoAutoUpgrade",
        },
        "regressionTest": {
            "status": "passed",
            "evaluationRunId": "eval_1/run_2",
            "baselineAgentVersion": "1",
            "evaluatedAt": "2026-11-26T10:00:00Z",
            "itemsTotal": 12,
            "itemsScored": 12,
            "passRates": {"builtin.similarity": {"baseline": 0.9, "candidate": 0.9}},
        },
        "reviewRef": "SYNTHETIC-1",
        "reviewedOn": "2026-11-26",
        "accountableRole": "AI Engineering Lead",
    },
}
QLT_006 = {
    "id": "QLT-006",
    "version": "1.0.0",
    "evidence": {
        "baselineRecordPath": "../CHG-002/release/release-baseline.json",
        "regressionThresholdPp": 5,
        "minScoredItems": 12,
        "issueRepository": "contoso/demo",
        "reviewRef": "SYNTHETIC-2",
        "reviewedOn": "2026-11-26",
        "accountableRole": "QA Lead",
    },
}


def _errors(entry: dict) -> list[str]:
    contract = copy.deepcopy(VALID_HELPDESK_CONTRACT)
    contract["spec"]["controls"].append(copy.deepcopy(entry))
    return vgc.validate_contract(contract, agent_dir_name="helpdesk-tier1-triage")


def test_complete_declarations_validate() -> None:
    assert _errors(CHG_002) == []
    assert _errors(QLT_006) == []


def test_chg_002_auto_upgrade_or_wrong_role_fails_closed() -> None:
    entry = copy.deepcopy(CHG_002)
    entry["evidence"]["candidate"]["versionUpgradeOption"] = "OnceNewDefaultVersionAvailable"
    assert _errors(entry)
    entry = copy.deepcopy(CHG_002)
    entry["evidence"]["accountableRole"] = "QA Lead"
    assert _errors(entry)


def test_chg_002_asset_id_must_pin_a_version() -> None:
    entry = copy.deepcopy(CHG_002)
    entry["evidence"]["candidate"]["modelAssetId"] = "azureml://registries/azure-openai/models/gpt-5-mini/"
    assert _errors(entry)


def test_qlt_006_threshold_must_be_positive_and_role_fixed() -> None:
    for field, value in (("regressionThresholdPp", 0), ("minScoredItems", 2), ("accountableRole", "AI Engineering Lead")):
        entry = copy.deepcopy(QLT_006)
        entry["evidence"][field] = value
        assert _errors(entry), field


def test_shipped_workload_contracts() -> None:
    [qlt] = vgc.discover_contracts(CATEGORY / "QLT-006_production_evaluation_regression" / "workload")
    assert vgc.validate_contract(vgc.load_contract(qlt), agent_dir_name="chg-002-support-assistant") == []
    [chg] = vgc.discover_contracts(CATEGORY / "CHG-002_model_version_changed_without_regression_test" / "candidate")
    entry, _ = vgc.validate_control_entry("CHG-002", vgc.load_contract(chg))
    assert entry is not None  # declared; complete only after a recorded regression test


def test_release_job_depends_on_the_credential_free_gate_and_policy_route_is_separate() -> None:
    import yaml

    workflow = yaml.safe_load((Path(__file__).resolve().parents[1] / ".github/workflows/chg-002-model-change-gate.yml").read_text())
    jobs = workflow["jobs"]
    assert jobs["release"]["needs"] == "candidate-gate"
    assert "inputs.route == 'combined'" in jobs["release"]["if"]
    assert "needs" not in jobs["policy-denial-experiment"]
    assert "permissions" not in jobs["candidate-gate"]  # credential-free: inherits contents: read only
    gate_steps = " ".join(step.get("run", "") for step in jobs["candidate-gate"]["steps"])
    assert "deployment_gate.sh" in gate_steps and "src.chg_002 gate" in gate_steps
