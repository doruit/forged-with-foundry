"""Deterministic regression decision for a candidate model.

Foundry's evaluators score each response; this module only compares the
recorded counts with the policy the AI Engineering Lead approved in the
governance contract. It never calls a model.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RegressionPolicy:
    dataset_path: str
    dataset_sha256: str
    required_evaluators: tuple[str, ...]
    min_pass_rate: float
    max_regression_pp: float
    min_scored_items: int

    @classmethod
    def from_evidence(cls, evidence: dict) -> "RegressionPolicy":
        policy = evidence["regressionPolicy"]
        return cls(
            dataset_path=policy["datasetPath"],
            dataset_sha256=policy["datasetSha256"],
            required_evaluators=tuple(policy["requiredEvaluators"]),
            min_pass_rate=float(policy["minPassRate"]),
            max_regression_pp=float(policy["maxRegressionPp"]),
            min_scored_items=int(policy["minScoredItems"]),
        )


@dataclass(frozen=True)
class EvaluatorCounts:
    """Per-evaluator outcome of one Foundry Evaluations run."""

    total: int
    passed: int
    failed: int
    errored: int

    @property
    def complete(self) -> bool:
        return self.errored == 0 and self.passed + self.failed == self.total

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0


@dataclass(frozen=True)
class Decision:
    outcome: str  # "release_allowed" or "blocked"
    reason: str
    pass_rates: dict[str, dict[str, float]] = field(default_factory=dict)
    items_total: int = 0
    items_scored: int = 0

    @property
    def allowed(self) -> bool:
        return self.outcome == "release_allowed"


def _blocked(reason: str, **kwargs) -> Decision:
    return Decision("blocked", reason, **kwargs)


def decide(
    policy: RegressionPolicy,
    baseline: dict[str, EvaluatorCounts],
    candidate: dict[str, EvaluatorCounts],
    dataset_items: int,
) -> Decision:
    """Allow a release only when the candidate is fully scored and not worse."""

    if not policy.required_evaluators:
        return _blocked("chg_002_policy_invalid")
    for name in policy.required_evaluators:
        if name not in baseline or name not in candidate:
            return _blocked("chg_002_evaluator_missing")

    counts = [run[name] for run in (baseline, candidate) for name in policy.required_evaluators]
    items_total = min(c.total for c in counts)
    items_scored = min(c.passed + c.failed for c in counts)
    if any(c.total != dataset_items for c in counts):
        return _blocked("chg_002_dataset_mismatch", items_total=items_total, items_scored=items_scored)
    if not all(c.complete for c in counts) or dataset_items < policy.min_scored_items:
        return _blocked("chg_002_evaluation_incomplete", items_total=items_total, items_scored=items_scored)

    rates = {
        name: {
            "baseline": round(baseline[name].pass_rate, 4),
            "candidate": round(candidate[name].pass_rate, 4),
        }
        for name in policy.required_evaluators
    }
    return decide_from_rates(policy, rates, items_total=dataset_items, items_scored=dataset_items)


def decide_from_rates(
    policy: RegressionPolicy,
    rates: dict[str, dict[str, float]],
    *,
    items_total: int,
    items_scored: int,
) -> Decision:
    """Apply the thresholds to recorded pass rates (also used by the credential-free gate)."""

    details = {"pass_rates": rates, "items_total": items_total, "items_scored": items_scored}
    if any(name not in rates for name in policy.required_evaluators):
        return _blocked("chg_002_evaluator_missing", **details)
    if items_scored != items_total or items_total < policy.min_scored_items:
        return _blocked("chg_002_evaluation_incomplete", **details)
    for name in policy.required_evaluators:
        if rates[name]["candidate"] < policy.min_pass_rate:
            return _blocked("chg_002_below_min_pass_rate", **details)
    for name in policy.required_evaluators:
        drop_pp = (rates[name]["baseline"] - rates[name]["candidate"]) * 100
        if drop_pp > policy.max_regression_pp + 1e-9:
            return _blocked("chg_002_regression_detected", **details)
    return Decision("release_allowed", "chg_002_no_regression", **details)
