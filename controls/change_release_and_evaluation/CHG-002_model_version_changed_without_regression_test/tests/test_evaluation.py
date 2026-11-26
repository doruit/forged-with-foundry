import pytest

from src.chg_002.evaluation import build_criteria, count_results, load_dataset
from src.chg_002.gate import sha256_file
from src.chg_002.policy import EvaluatorCounts

from pathlib import Path

DATASET = Path(__file__).resolve().parents[1] / "candidate" / "dataset" / "regression.jsonl"


def test_criteria_map_only_the_inputs_each_evaluator_reads() -> None:
    similarity, task = build_criteria(("builtin.similarity", "builtin.task_adherence"), "judge")
    assert similarity["data_mapping"] == {"query": "{{item.query}}", "response": "{{sample.output_text}}", "ground_truth": "{{item.ground_truth}}"}
    assert "ground_truth" not in task["data_mapping"]
    assert similarity["initialization_parameters"] == {"deployment_name": "judge"}


def test_unknown_evaluator_fails_before_any_run() -> None:
    with pytest.raises(ValueError):
        build_criteria(("builtin.groundedness",), "judge")


def test_missing_or_null_results_count_as_errored() -> None:
    items = [
        {"results": [{"name": "similarity", "passed": True}]},
        {"results": [{"name": "similarity", "passed": False}]},
        {"results": [{"name": "similarity", "passed": None}]},
        {"results": []},
    ]
    assert count_results(items, ("builtin.similarity",)) == {
        "builtin.similarity": EvaluatorCounts(total=4, passed=1, failed=1, errored=2)
    }


def test_shipped_dataset_is_well_formed_and_matches_the_contract_hash() -> None:
    assert len(load_dataset(DATASET)) == 12
    assert sha256_file(DATASET) == "dd5edd76a7ae72cb862a7e78fdf1364ee38c2a50c8b931220b171799ba46b5ce"
