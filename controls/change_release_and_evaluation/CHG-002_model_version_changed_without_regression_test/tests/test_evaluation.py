import pytest

from src.chg_002.evaluation import build_criteria, count_results, list_items, load_dataset
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


class _Item:
    def __init__(self, n: int) -> None:
        self.n = n

    def model_dump(self) -> dict:
        return {"id": self.n}


class _Client:
    """Returns a short item list first, as Foundry did right after a run completed."""

    def __init__(self, sizes: list[int]) -> None:
        self.sizes = sizes
        self.evals = self
        self.runs = self
        self.output_items = self

    def list(self, run_id: str, eval_id: str) -> list[_Item]:
        size = self.sizes.pop(0) if len(self.sizes) > 1 else self.sizes[0]
        return [_Item(i) for i in range(size)]


def test_short_item_list_is_reread_until_complete() -> None:
    assert len(list_items(_Client([9, 12]), "e", "r", 12, wait_s=0)) == 12


def test_item_list_still_short_after_retries_stays_short_so_the_gate_fails_closed() -> None:
    assert len(list_items(_Client([9]), "e", "r", 12, attempts=3, wait_s=0)) == 9
