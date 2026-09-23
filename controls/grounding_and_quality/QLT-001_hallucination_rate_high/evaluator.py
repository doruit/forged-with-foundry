"""Evaluate one measurement window's batch groundedness eval results.

Microsoft Foundry's batch/cloud evaluation (``azd ai agent eval`` /
``openai_client.evals.runs.output_items.list()``) is the authoritative
signal source (see ``ASSESSMENT.md`` revision note 3: Continuous Evaluation
does not support hosted agents, confirmed against a real deployment on two
SDK versions). This module never scores a response itself. It only
aggregates each output item's real ``passed``/``score`` result against the
deterministic rate and critical-item policy in the QLT-001 control contract.

Confirmed real schema (2026-09-23, against two real hosted-agent eval runs)
for the ``groundedness``-named entry in each item's ``results``: ``passed``
(bool), ``score`` (float), ``threshold`` (float), ``status`` (str), ``reason``
(str). The first live run only carried this control's own generated rubric
evaluator, whose ``score``/``threshold`` happened to be on a 0.0-1.0 scale; a
second live run with `builtin.groundedness` also configured showed real
scores of 1.0-4.0 for the same named criterion, on its own different scale --
confirming the numeric range is evaluator-specific and must not be
hardcoded. ``passed`` (the evaluator's own threshold decision) is the sole
authoritative signal for the rate. The critical-item override compares each
item's own ``score`` against its own ``threshold`` (``CRITICAL_RATIO``),
which stays meaningful across different evaluator scales instead of
hardcoding an absolute floor.
"""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

CONTROL_ID = "QLT-001"
VERSION = "1.0.0"

# A response scoring at or below its own evaluator's threshold times
# CRITICAL_RATIO is treated as a critical hallucination on its own,
# regardless of the window's aggregate rate -- for example, a score at or
# below half of the pass threshold. Relative to each item's own threshold
# rather than an absolute floor, so it stays meaningful whether the
# configured evaluator's scale is 0.0-1.0 or a 1-5 Likert range (both
# observed live against the same control -- see the module docstring).
CRITICAL_RATIO = Decimal("0.5")
THRESHOLD_PERCENT = Decimal("5")


class CannotEvaluate(ValueError):
    """A required input is missing, invalid, or ambiguous."""


def measure(manifest: dict, results: list[dict]) -> dict:
    """Aggregate this window's eval output items; require every sampled run exactly once."""
    expected_run_ids = set(manifest["expected_run_ids"])
    if not expected_run_ids:
        raise CannotEvaluate("empty_window")
    observed: dict[str, tuple[bool, Decimal, Decimal]] = {}
    for row in results:
        run_id = row.get("run_id")
        if run_id not in expected_run_ids:
            raise CannotEvaluate("unexpected_run")
        passed = row.get("passed")
        raw_score, raw_threshold = row.get("score"), row.get("threshold")
        if type(passed) is not bool:
            raise CannotEvaluate("invalid_score")
        for value in (raw_score, raw_threshold):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise CannotEvaluate("invalid_score")
        score, threshold = Decimal(str(raw_score)), Decimal(str(raw_threshold))
        if threshold <= 0:
            raise CannotEvaluate("invalid_score")
        if run_id in observed and observed[run_id] != (passed, score, threshold):
            raise CannotEvaluate("conflicting_duplicates")
        observed[run_id] = (passed, score, threshold)
    if observed.keys() != expected_run_ids:
        # The batch eval run had not scored every sampled run by the time the
        # window closed, or a scoring failure was reported. Never shrink the
        # denominator to only what happened to arrive; fail closed instead.
        raise CannotEvaluate("incomplete_scoring")
    total = len(observed)
    ungrounded_run_ids = [run_id for run_id, (passed, _, _) in observed.items() if not passed]
    critical_run_ids = [run_id for run_id, (_, score, threshold) in observed.items()
                        if score <= threshold * CRITICAL_RATIO]
    rate = Decimal(len(ungrounded_run_ids)) * 100 / total
    return {
        "total": total,
        "ungrounded": len(ungrounded_run_ids),
        "ungrounded_run_ids": ungrounded_run_ids,
        "critical_run_ids": critical_run_ids,
        "rate_percent": float(rate),
    }


def evaluate(manifest: dict, scores: list[dict], *, retrieval_complete: bool) -> dict:
    """Produce one minimized decision record, including fail-closed outcomes."""
    record = {
        "control_id": CONTROL_ID,
        "control_version": VERSION,
        "policy_version": VERSION,
        "evidence_version": VERSION,
        "agent_id": manifest.get("agent_id"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "correlation_id": None,
        "window": None,
        "decision": "cannot_evaluate",
        "reason": "invalid_input",
        "accountable_role": "Product Owner",
        "threshold_percent": float(THRESHOLD_PERCENT),
        "notification": {"status": "not_requested", "delivery_verified": False},
    }
    try:
        window_id = manifest["window_id"]
        if str(UUID(window_id)) != window_id:
            raise CannotEvaluate("invalid_window_id")
        record["correlation_id"] = window_id
        if not retrieval_complete:
            raise CannotEvaluate("evaluation_retrieval_unavailable_or_partial")
        measurement = measure(manifest, scores)
        record["window"] = {"number": manifest["window"], **measurement}
        breach = (
            measurement["rate_percent"] > float(THRESHOLD_PERCENT)
            or bool(measurement["critical_run_ids"])
        )
        record.update(
            decision="quality_review_required" if breach else "no_review_required",
            reason=(
                "rate_above_threshold_or_critical_item" if breach
                else "rate_within_threshold_no_critical_item"
            ),
        )
    except CannotEvaluate as error:
        record["reason"] = str(error)
    except (ValueError, TypeError, KeyError, AttributeError):
        record["reason"] = "invalid_or_missing_input"
    return record
