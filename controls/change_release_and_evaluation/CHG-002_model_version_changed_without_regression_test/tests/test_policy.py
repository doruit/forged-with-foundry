from src.chg_002.policy import EvaluatorCounts, RegressionPolicy, decide, decide_from_rates

POLICY = RegressionPolicy("dataset/regression.jsonl", "0" * 64, ("builtin.similarity", "builtin.task_adherence"), 0.75, 5, 12)


def counts(passed: int, total: int = 12, errored: int = 0) -> EvaluatorCounts:
    return EvaluatorCounts(total=total, passed=passed, failed=total - passed - errored, errored=errored)


def run(sim: int, task: int, **kw) -> dict:
    return {"builtin.similarity": counts(sim, **kw), "builtin.task_adherence": counts(task, **kw)}


def test_equal_or_better_candidate_is_allowed() -> None:
    decision = decide(POLICY, run(11, 11), run(12, 11), 12)
    assert decision.allowed and decision.reason == "chg_002_no_regression"
    assert decision.pass_rates["builtin.similarity"] == {"baseline": 0.9167, "candidate": 1.0}


def test_drop_above_tolerance_is_blocked() -> None:
    decision = decide(POLICY, run(12, 12), run(11, 12), 12)  # 8.3 pp drop > 5 pp
    assert decision.reason == "chg_002_regression_detected" and not decision.allowed


def test_drop_within_tolerance_is_allowed() -> None:
    rates = {"builtin.similarity": {"baseline": 0.9, "candidate": 0.86}, "builtin.task_adherence": {"baseline": 0.9, "candidate": 0.9}}
    assert decide_from_rates(POLICY, rates, items_total=12, items_scored=12).allowed


def test_candidate_below_minimum_pass_rate_is_blocked_even_without_regression() -> None:
    assert decide(POLICY, run(8, 8), run(8, 8), 12).reason == "chg_002_below_min_pass_rate"


def test_errored_items_make_the_evaluation_incomplete() -> None:
    assert decide(POLICY, run(12, 12), run(11, 11, errored=1), 12).reason == "chg_002_evaluation_incomplete"


def test_missing_evaluator_is_blocked() -> None:
    candidate = {"builtin.similarity": counts(12)}
    assert decide(POLICY, run(12, 12), candidate, 12).reason == "chg_002_evaluator_missing"


def test_run_on_a_different_dataset_size_is_blocked() -> None:
    assert decide(POLICY, run(12, 12), run(10, 10, total=10), 12).reason == "chg_002_dataset_mismatch"


def test_dataset_smaller_than_minimum_is_incomplete() -> None:
    small = RegressionPolicy(*POLICY.__dict__.values())
    object.__setattr__(small, "min_scored_items", 20)
    assert decide(small, run(12, 12), run(12, 12), 12).reason == "chg_002_evaluation_incomplete"
