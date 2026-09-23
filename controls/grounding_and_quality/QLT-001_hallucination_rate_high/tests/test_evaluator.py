"""Deterministic threshold, integrity, and fail-closed regression checks."""

from copy import deepcopy
from pathlib import Path
import sys
from uuid import uuid4

import pytest

CONTROL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CONTROL))
from evaluator import evaluate  # noqa: E402


def sample(items=((True, 0.9, 0.5), (True, 0.9, 0.5), (True, 0.9, 0.5))):
    """items: iterable of (passed, score, threshold) triples, matching the real output-item schema.

    Confirmed live against two different evaluator scales for the same
    control: this control's own generated rubric evaluator (score/threshold
    on 0.0-1.0) and `builtin.groundedness` (score/threshold on a 1-5-ish
    scale) -- see evaluator.py's module docstring.
    """
    window_id = str(uuid4())
    run_ids = [str(uuid4()) for _ in items]
    manifest = {"window_id": window_id, "window": 3, "agent_id": "it-helpdesk-kb-assistant",
                "expected_run_ids": run_ids}
    rows = [{"run_id": run_id, "passed": passed, "score": score, "threshold": threshold}
            for run_id, (passed, score, threshold) in zip(run_ids, items)]
    return manifest, rows


@pytest.mark.parametrize("items,decision", [
    (((True, 0.9, 0.5), (True, 0.8, 0.5), (True, 0.9, 0.5)), "no_review_required"),
    (((True, 0.6, 0.5), (True, 0.6, 0.5), (True, 0.6, 0.5)), "no_review_required"),
    (((True, 0.9, 0.5), (True, 0.9, 0.5), (False, 0.3, 0.5)), "quality_review_required"),  # 1/3 ungrounded ~33% > 5%
    (((True, 0.9, 0.5), (True, 0.9, 0.5), (False, 0.05, 0.5)), "quality_review_required"),  # critical item overrides
    (tuple([(True, 0.9, 0.5)] * 19 + [(False, 0.4, 0.5)]), "no_review_required"),   # 1/20 = 5%, not > 5%
    (tuple([(True, 0.9, 0.5)] * 18 + [(False, 0.4, 0.5), (False, 0.4, 0.5)]), "quality_review_required"),  # 2/20 = 10% > 5%
    # Same relative shape on a completely different evaluator scale (builtin.groundedness, observed live: ~1-4):
    (((True, 4.0, 3.0), (True, 4.0, 3.0), (False, 1.0, 3.0)), "quality_review_required"),
])
def test_given_results_when_evaluated_then_exact_threshold_and_critical_rule(items, decision):
    manifest, rows = sample(items)

    result = evaluate(manifest, rows, retrieval_complete=True)

    assert result["decision"] == decision
    assert result["threshold_percent"] == 5.0


def test_given_critical_score_when_evaluated_then_flagged_even_below_rate_threshold():
    # 1/20 = 5% rate, not > 5%, but a score at/below half its own threshold still forces review
    manifest, rows = sample(tuple([(True, 0.9, 0.5)] * 19 + [(False, 0.2, 0.5)]))

    result = evaluate(manifest, rows, retrieval_complete=True)

    assert result["decision"] == "quality_review_required"
    assert result["window"]["critical_run_ids"]


@pytest.mark.parametrize("mutation", ["missing", "extra", "conflict", "bad_score_type",
                                      "bad_threshold_type", "zero_threshold", "bad_passed_type"])
def test_given_invalid_results_when_evaluated_then_cannot_evaluate(mutation):
    manifest, rows = sample()
    if mutation == "missing":
        rows.pop()
    elif mutation == "extra":
        rows.append({"run_id": "not-an-expected-run", "passed": True, "score": 0.9, "threshold": 0.5})
    elif mutation == "conflict":
        duplicate = deepcopy(rows[0])
        duplicate["score"] = 0.1
        rows.append(duplicate)
    elif mutation == "bad_score_type":
        rows[0]["score"] = "0.9"
    elif mutation == "bad_threshold_type":
        rows[0]["threshold"] = None
    elif mutation == "zero_threshold":
        rows[0]["threshold"] = 0
    else:
        rows[0]["passed"] = "true"

    result = evaluate(manifest, rows, retrieval_complete=True)

    assert result["decision"] == "cannot_evaluate"


def test_given_identical_duplicate_when_evaluated_then_counted_once():
    manifest, rows = sample()
    rows.append(deepcopy(rows[0]))

    result = evaluate(manifest, rows, retrieval_complete=True)

    assert result["decision"] == "no_review_required"
    assert result["window"]["total"] == 3


def test_given_empty_window_when_evaluated_then_cannot_evaluate():
    manifest, rows = sample()
    manifest["expected_run_ids"] = []
    rows.clear()

    assert evaluate(manifest, rows, retrieval_complete=True)["decision"] == "cannot_evaluate"


def test_given_incomplete_retrieval_when_evaluated_then_no_healthy_result():
    manifest, rows = sample()

    result = evaluate(manifest, rows, retrieval_complete=False)

    assert result["decision"] == "cannot_evaluate"
    assert result["reason"] == "evaluation_retrieval_unavailable_or_partial"


def test_given_invalid_window_id_when_evaluated_then_errors_are_minimized():
    manifest, rows = sample()
    manifest["window_id"] = "not-a-uuid"

    result = evaluate(manifest, rows, retrieval_complete=True)

    assert result["decision"] == "cannot_evaluate"
    assert result["correlation_id"] is None
