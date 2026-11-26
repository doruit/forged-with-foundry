"""Deterministic production-regression decision. Foundry evaluators score; this module compares."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Counts:
    total: int
    passed: int
    failed: int
    errored: int

    @property
    def scored(self) -> int:
        return self.passed + self.failed

    @property
    def pass_rate(self) -> float:
        return self.passed / self.scored if self.scored else 0.0


@dataclass(frozen=True)
class Decision:
    outcome: str  # within_tolerance | change_cycle_required | measurement_failed
    reason: str
    deltas_pp: dict[str, float] = field(default_factory=dict)
    live_rates: dict[str, float] = field(default_factory=dict)


def decide(
    baseline_rates: dict[str, float],
    live: dict[str, Counts],
    *,
    threshold_pp: float,
    min_scored_items: int,
    dataset_items: int,
) -> Decision:
    if not baseline_rates:
        return Decision("measurement_failed", "qlt_006_baseline_unavailable")
    for name in baseline_rates:
        counts = live.get(name)
        if counts is None:
            return Decision("measurement_failed", "qlt_006_evaluator_missing")
        if counts.total != dataset_items:
            return Decision("measurement_failed", "qlt_006_dataset_mismatch")
        if counts.errored or counts.scored < min_scored_items:
            return Decision("measurement_failed", "qlt_006_too_few_scored_items")
    live_rates = {name: round(live[name].pass_rate, 4) for name in baseline_rates}
    deltas = {name: round((baseline_rates[name] - live_rates[name]) * 100, 2) for name in baseline_rates}
    if any(delta > threshold_pp + 1e-9 for delta in deltas.values()):
        return Decision("change_cycle_required", "qlt_006_regression_above_threshold", deltas, live_rates)
    return Decision("within_tolerance", "qlt_006_within_tolerance", deltas, live_rates)
