"""Deterministic fleet threshold, rollup, and fail-closed regression checks."""

from pathlib import Path
import sys
from uuid import uuid4

import pytest

CONTROL = Path(__file__).resolve().parents[1]
sys.modules.pop("evaluator", None)
sys.path.insert(0, str(CONTROL))
from evaluator import CannotEvaluate, daily_trend, evaluate, measure_agent, rollup  # noqa: E402
sys.path.remove(str(CONTROL))
sys.modules.pop("evaluator", None)


def results(items):
    """items: iterable of (passed, score, threshold) triples, matching the real per-criterion schema.

    Confirmed live against two different evaluator scales for the same
    control: this control's own former rubric evaluator (score/threshold on
    0.0-1.0, since retired) and `builtin.groundedness` (score/threshold on a
    1-5-ish scale) -- see evaluator.py's module docstring.
    """
    return [{"run_id": str(uuid4()), "passed": passed, "score": score, "threshold": threshold}
            for passed, score, threshold in items]


def fleet(**per_agent_items):
    return {agent_id: results(items) for agent_id, items in per_agent_items.items()}


def test_given_healthy_results_when_measured_then_zero_rate_and_real_average():
    measurement = measure_agent("platform", results([(True, 0.9, 0.5), (True, 0.8, 0.5), (True, 0.9, 0.5)]))

    assert measurement["rate_percent"] == 0.0
    assert measurement["critical_run_ids"] == []
    assert measurement["average_score"] == pytest.approx((0.9 + 0.8 + 0.9) / 3)


def test_given_a_breach_when_measured_then_rate_and_critical_items_reflect_it():
    # 1/3 ungrounded ~33% > 5%, and the failing item is also critical (score <= threshold * 0.5)
    measurement = measure_agent("contractor", results([(True, 0.9, 0.5), (True, 0.9, 0.5), (False, 0.2, 0.5)]))

    assert measurement["rate_percent"] > 5.0
    assert measurement["critical_run_ids"]


def test_given_no_results_when_measured_then_cannot_evaluate():
    with pytest.raises(CannotEvaluate):
        measure_agent("platform", [])


@pytest.mark.parametrize("mutation", ["bad_score_type", "bad_threshold_type", "zero_threshold", "bad_passed_type"])
def test_given_invalid_results_when_measured_then_cannot_evaluate(mutation):
    rows = results([(True, 0.9, 0.5)])
    if mutation == "bad_score_type":
        rows[0]["score"] = "0.9"
    elif mutation == "bad_threshold_type":
        rows[0]["threshold"] = None
    elif mutation == "zero_threshold":
        rows[0]["threshold"] = 0
    else:
        rows[0]["passed"] = "true"

    with pytest.raises(CannotEvaluate):
        measure_agent("platform", rows)


def test_given_a_healthy_fleet_when_rolled_up_then_average_best_and_worst_reported():
    fleet_results = fleet(
        platform=[(True, 0.95, 0.5), (True, 0.9, 0.5)],
        regional=[(True, 0.8, 0.5), (True, 0.75, 0.5)],
        contractor=[(True, 0.6, 0.5), (True, 0.65, 0.5)],
    )

    fleet_rollup = rollup(fleet_results)

    assert fleet_rollup["best_agent"]["agent_id"] == "platform"
    assert fleet_rollup["worst_agent"]["agent_id"] == "contractor"
    assert fleet_rollup["fleet_average_score"] == pytest.approx(
        (fleet_rollup["per_agent"]["platform"]["average_score"]
         + fleet_rollup["per_agent"]["regional"]["average_score"]
         + fleet_rollup["per_agent"]["contractor"]["average_score"]) / 3
    )
    assert fleet_rollup["any_agent_breach"] is False


def test_given_one_agent_breaching_when_rolled_up_then_flagged_even_if_average_looks_healthy():
    # A single regressed agent should not be diluted away by two healthy ones.
    fleet_results = fleet(
        platform=[(True, 0.95, 0.5)] * 10,
        regional=[(True, 0.9, 0.5)] * 10,
        contractor=[(True, 0.9, 0.5)] * 8 + [(False, 0.1, 0.5), (False, 0.1, 0.5)],
    )

    fleet_rollup = rollup(fleet_results)

    assert fleet_rollup["any_agent_breach"] is True
    assert fleet_rollup["fleet_average_score"] > 0.8  # average alone would look healthy


def test_given_an_empty_fleet_when_rolled_up_then_cannot_evaluate():
    with pytest.raises(CannotEvaluate):
        rollup({})


def test_given_a_healthy_fleet_when_evaluated_then_no_review_required():
    fleet_results = fleet(
        platform=[(True, 0.95, 0.5)] * 3,
        regional=[(True, 0.9, 0.5)] * 3,
        contractor=[(True, 0.85, 0.5)] * 3,
    )
    window = {"window_id": str(uuid4()), "window": 1}

    record = evaluate(window, fleet_results, retrieval_complete=True)

    assert record["decision"] == "no_review_required"
    assert record["threshold_percent"] == 5.0


def test_given_a_breaching_fleet_when_evaluated_then_quality_review_required():
    fleet_results = fleet(
        platform=[(True, 0.95, 0.5)] * 3,
        regional=[(True, 0.9, 0.5)] * 3,
        contractor=[(True, 0.9, 0.5), (False, 0.1, 0.5), (False, 0.1, 0.5)],
    )
    window = {"window_id": str(uuid4()), "window": 4}

    record = evaluate(window, fleet_results, retrieval_complete=True)

    assert record["decision"] == "quality_review_required"
    assert record["fleet"]["worst_agent"]["agent_id"] == "contractor"


def test_given_incomplete_retrieval_when_evaluated_then_no_healthy_result():
    fleet_results = fleet(platform=[(True, 0.9, 0.5)])
    window = {"window_id": str(uuid4()), "window": 1}

    record = evaluate(window, fleet_results, retrieval_complete=False)

    assert record["decision"] == "cannot_evaluate"
    assert record["reason"] == "evaluation_retrieval_unavailable_or_partial"


def test_given_an_empty_fleet_when_evaluated_then_cannot_evaluate():
    window = {"window_id": str(uuid4()), "window": 1}

    record = evaluate(window, {}, retrieval_complete=True)

    assert record["decision"] == "cannot_evaluate"
    assert record["reason"] == "empty_fleet"


def test_given_no_scored_events_when_computing_daily_trend_then_returns_empty():
    assert daily_trend([]) == []


def test_given_multiple_days_when_computing_daily_trend_then_averages_and_sorts_chronologically():
    events = [
        {"day": "2026-09-25", "score": 5.0},
        {"day": "2026-09-24", "score": 4.0},
        {"day": "2026-09-24", "score": 2.0},
    ]

    trend = daily_trend(events)

    assert trend == [
        {"day": "2026-09-24", "average_score": 3.0, "count": 2},
        {"day": "2026-09-25", "average_score": 5.0, "count": 1},
    ]
