from src.qlt_006.policy import Counts, decide

BASE = {"builtin.similarity": 0.9167, "builtin.task_adherence": 0.9167}


def live(sim: int, task: int, total: int = 12, errored: int = 0) -> dict:
    return {
        "builtin.similarity": Counts(total, sim, total - sim - errored, errored),
        "builtin.task_adherence": Counts(total, task, total - task - errored, errored),
    }


def run(counts, threshold=5, minimum=12, items=12):
    return decide(BASE, counts, threshold_pp=threshold, min_scored_items=minimum, dataset_items=items)


def test_same_quality_is_within_tolerance() -> None:
    decision = run(live(11, 11))
    assert decision.outcome == "within_tolerance" and decision.deltas_pp["builtin.similarity"] == 0.0


def test_drop_above_threshold_opens_a_change_cycle() -> None:
    decision = run(live(8, 11))  # similarity 66.7% vs 91.7% = 25 pp
    assert decision.outcome == "change_cycle_required"
    assert decision.deltas_pp["builtin.similarity"] == 25.0


def test_threshold_comes_from_the_contract() -> None:
    assert run(live(10, 11), threshold=10).outcome == "within_tolerance"   # 8.33 pp
    assert run(live(10, 11), threshold=5).outcome == "change_cycle_required"


def test_improvement_is_never_a_regression() -> None:
    assert run(live(12, 12)).outcome == "within_tolerance"


def test_errored_or_missing_items_are_never_reported_healthy() -> None:
    assert run(live(11, 11, errored=1)).reason == "qlt_006_too_few_scored_items"
    assert run({"builtin.similarity": Counts(12, 11, 1, 0)}).reason == "qlt_006_evaluator_missing"
    assert run(live(10, 10, total=10)).reason == "qlt_006_dataset_mismatch"
    assert decide({}, live(11, 11), threshold_pp=5, min_scored_items=12, dataset_items=12).reason == "qlt_006_baseline_unavailable"
