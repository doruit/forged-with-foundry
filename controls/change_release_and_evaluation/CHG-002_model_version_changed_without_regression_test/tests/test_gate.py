import copy
import json
import shutil
from pathlib import Path

import pytest
import yaml

from src.chg_002.gate import CONTRACT_RELATIVE, asset_id, check_candidate

CONTROL = Path(__file__).resolve().parents[1]
SHIPPED = CONTROL / "candidate"
EVIDENCE = {
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
        "passRates": {
            "builtin.similarity": {"baseline": 0.9167, "candidate": 0.9167},
            "builtin.task_adherence": {"baseline": 0.8333, "candidate": 0.9167},
        },
    },
}


@pytest.fixture
def root(tmp_path: Path) -> Path:
    target = tmp_path / "candidate"
    shutil.copytree(SHIPPED, target)
    contract = yaml.safe_load((target / CONTRACT_RELATIVE).read_text())
    contract["spec"]["controls"][0]["evidence"].update(copy.deepcopy(EVIDENCE))
    (target / CONTRACT_RELATIVE).write_text(yaml.safe_dump(contract, sort_keys=False))
    return target


def edit(root: Path, change) -> None:
    contract = yaml.safe_load((root / CONTRACT_RELATIVE).read_text())
    change(contract["spec"]["controls"][0]["evidence"])
    (root / CONTRACT_RELATIVE).write_text(yaml.safe_dump(contract, sort_keys=False))


def test_evaluated_candidate_bound_to_the_deployment_is_allowed(root: Path) -> None:
    result = check_candidate(root)
    assert result["decision"] == "release_allowed", result
    assert result["candidate"]["modelAssetId"].endswith("gpt-5-mini/versions/2025-08-07")


def test_model_change_without_a_recorded_regression_test_is_blocked(root: Path) -> None:
    edit(root, lambda e: e.pop("regressionTest"))
    assert check_candidate(root)["reason"] == "chg_002_regression_test_missing"


def test_evidence_for_another_model_version_is_blocked(root: Path) -> None:
    deployment = json.loads((root / "model-deployment.json").read_text())
    deployment["model"]["version"] = "2026-01-01"
    (root / "model-deployment.json").write_text(json.dumps(deployment))
    assert check_candidate(root)["reason"] == "chg_002_evidence_not_for_this_candidate"


def test_auto_upgrade_candidate_is_blocked(root: Path) -> None:
    deployment = json.loads((root / "model-deployment.json").read_text())
    deployment["versionUpgradeOption"] = "OnceNewDefaultVersionAvailable"
    (root / "model-deployment.json").write_text(json.dumps(deployment))
    assert check_candidate(root)["reason"] == "chg_002_auto_upgrade_not_allowed"


def test_changed_dataset_is_blocked(root: Path) -> None:
    with (root / "dataset" / "regression.jsonl").open("a") as handle:
        handle.write('{"query": "extra", "ground_truth": "extra"}\n')
    assert check_candidate(root)["reason"] == "chg_002_dataset_changed"


def test_failed_regression_test_is_blocked(root: Path) -> None:
    edit(root, lambda e: e["regressionTest"].update(status="failed"))
    assert check_candidate(root)["reason"] == "chg_002_regression_test_failed"


def test_passed_flag_with_regressing_numbers_is_blocked(root: Path) -> None:
    edit(root, lambda e: e["regressionTest"]["passRates"]["builtin.similarity"].update(candidate=0.75))
    result = check_candidate(root)
    assert result["reason"] == "chg_002_recorded_evidence_inconsistent"
    assert result["detail"] == "chg_002_regression_detected"


def test_partially_scored_run_is_blocked(root: Path) -> None:
    edit(root, lambda e: e["regressionTest"].update(itemsScored=11))
    assert check_candidate(root)["detail"] == "chg_002_evaluation_incomplete"


def test_missing_contract_and_unreadable_deployment_are_blocked(root: Path) -> None:
    (root / "model-deployment.json").write_text("{not json")
    assert check_candidate(root)["reason"] == "chg_002_deployment_candidate_unreadable"
    (root / CONTRACT_RELATIVE).unlink()
    assert check_candidate(root)["reason"] == "chg_002_contract_unreadable"


@pytest.mark.parametrize(
    "field, value",
    [("minPassRate", None), ("minPassRate", ""), ("minPassRate", 1.5), ("maxRegressionPp", -1), ("minScoredItems", 2), ("requiredEvaluators", [])],
)
def test_missing_empty_or_invalid_policy_values_fail_closed(root: Path, field: str, value) -> None:
    def change(evidence):
        if value is None:
            evidence["regressionPolicy"].pop(field)
        else:
            evidence["regressionPolicy"][field] = value
    edit(root, change)
    assert check_candidate(root)["reason"] == "chg_002_contract_invalid"


def test_asset_id_includes_registry_model_and_version() -> None:
    deployment = json.loads((SHIPPED / "model-deployment.json").read_text())
    assert asset_id(deployment) == "azureml://registries/azure-openai/models/gpt-5-mini/versions/2025-08-07"
