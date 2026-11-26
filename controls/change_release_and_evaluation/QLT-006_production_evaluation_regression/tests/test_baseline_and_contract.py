import hashlib
import json
import shutil
from pathlib import Path

import pytest
import yaml

from src.qlt_006 import baseline, contract
from src.qlt_006.route import body

CONTROL = Path(__file__).resolve().parents[1]
CHG = CONTROL.parent / "CHG-002_model_version_changed_without_regression_test"
DATASET = CHG / "candidate" / "dataset" / "regression.jsonl"


def record(sha: str) -> dict:
    return {
        "controlId": "CHG-002",
        "agent": {"name": "chg-002-support-assistant", "evaluatedVersion": "2"},
        "production": {"agentVersion": "2"},
        "model": {"assetId": "azureml://registries/azure-openai/models/gpt-5-mini/versions/2025-08-07", "deploymentName": "chg002-candidate"},
        "dataset": {"path": "candidate/dataset/regression.jsonl", "sha256": sha},
        "evaluators": ["builtin.similarity", "builtin.task_adherence"],
        "passRates": {"builtin.similarity": 0.9167, "builtin.task_adherence": 0.9167},
        "evaluationRunId": "eval_1/run_2",
    }


@pytest.fixture
def chg(tmp_path: Path) -> Path:
    root = tmp_path / "CHG"
    (root / "candidate" / "dataset").mkdir(parents=True)
    (root / "release").mkdir()
    shutil.copy(DATASET, root / "candidate" / "dataset" / "regression.jsonl")
    sha = hashlib.sha256(DATASET.read_bytes()).hexdigest()
    (root / "release" / "release-baseline.json").write_text(json.dumps(record(sha)))
    return root


def test_valid_record_loads_and_must_match_foundry(chg: Path) -> None:
    base, reason = baseline.load(chg / "release" / "release-baseline.json")
    assert reason == "" and base.rates["builtin.similarity"] == 0.9167
    assert baseline.matches_foundry(base, {"builtin.similarity": 0.9167, "builtin.task_adherence": 0.9167})
    assert not baseline.matches_foundry(base, {"builtin.similarity": 0.95, "builtin.task_adherence": 0.9167})


def test_missing_invalid_or_mismatched_records_fail_closed(chg: Path) -> None:
    path = chg / "release" / "release-baseline.json"
    assert baseline.load(chg / "release" / "absent.json")[1] == "qlt_006_baseline_unavailable"
    data = json.loads(path.read_text())
    data.pop("passRates")
    path.write_text(json.dumps(data))
    assert baseline.load(path)[1] == "qlt_006_baseline_invalid"
    path.write_text(json.dumps(record("0" * 64)))
    assert baseline.load(path)[1] == "qlt_006_dataset_mismatch"


def test_shipped_contract_is_valid() -> None:
    declaration = contract.load()
    assert declaration.status == "valid"
    assert declaration.threshold_pp == 5 and declaration.min_scored_items == 12
    assert declaration.baseline_record.name == "release-baseline.json"


@pytest.mark.parametrize("field, value", [("regressionThresholdPp", None), ("regressionThresholdPp", ""), ("regressionThresholdPp", 0), ("minScoredItems", 1), ("issueRepository", "not a repo")])
def test_missing_empty_or_invalid_threshold_values_are_invalid(tmp_path: Path, field: str, value) -> None:
    data = yaml.safe_load(contract.DEFAULT_CONTRACT.read_text())
    evidence = data["spec"]["controls"][0]["evidence"]
    if value is None:
        evidence.pop(field)
    else:
        evidence[field] = value
    path = tmp_path / ".fwf" / "agents" / "chg-002-support-assistant" / "governance.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(yaml.safe_dump(data))
    assert contract.load(path).status == "invalid"


def test_issue_body_contains_numbers_and_ids_only() -> None:
    rec = {
        "decision": "change_cycle_required", "reason": "qlt_006_regression_above_threshold", "accountable_role": "QA Lead",
        "live": {"agent_version": "3", "model": "chg002-candidate"}, "threshold_pp": 5, "correlation_id": "abc",
        "baseline": {"record_sha256": "f" * 64, "evaluation_run_id": "eval_1/run_2", "pass_rates": {"builtin.similarity": 0.9167}},
        "deltas_pp": {"builtin.similarity": 25.0}, "live_rates": {"builtin.similarity": 0.6667},
    }
    text = body(rec)
    assert "25.0" in text and "abc" in text
    assert not any(row["query"] in text for row in map(json.loads, DATASET.read_text().splitlines()))
