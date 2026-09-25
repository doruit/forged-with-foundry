"""Aggregate the fleet's continuously-sampled groundedness scores for one window.

Microsoft Foundry's Continuous Evaluation is the authoritative signal (see
``docs/UPSTREAM-FEEDBACK.md``'s 2026-09-25 "Resolution pass": `kind: prompt`
agents are accepted by continuous-evaluation rules, and their live traffic's
traces do reach Application Insights once the documented instrumentation and
IAM chain in ``demo.py``'s ``instrument()`` is wired up). This module never
scores a response itself; it only aggregates each fleet agent's real,
independently-computed ``groundedness`` criterion results into one fleet-level
rollup.

Confirmed real per-criterion schema (2026-09-23, against real hosted-agent
batch eval runs, and reused unchanged by the same `builtin.groundedness`
evaluator in continuous mode): ``passed`` (bool), ``score`` (float),
``threshold`` (float), ``status`` (str), ``reason`` (str). The numeric range
is evaluator-specific (0.0-1.0 in one observed run, 1.0-4.0 in another for the
same named criterion) and must not be hardcoded -- ``passed`` is each item's
own authoritative pass/fail decision, and the critical-item override compares
each item's own ``score`` against its own ``threshold`` (``CRITICAL_RATIO``)
for the same reason.

A single fleet-wide average groundedness would hide exactly the failure mode
this control exists to catch: one team's agent regressing while the other two
stay healthy pulls the average down only a little, and could stay under a
naive threshold indefinitely. ``rollup()`` therefore reports the fleet average
alongside the best- and worst-performing agent individually, and flags a
breach whenever any single fleet member breaches on its own -- not only when
the fleet average does.
"""

from datetime import datetime, timezone
from decimal import Decimal

CONTROL_ID = "QLT-001"
VERSION = "2.1.0"

# A response scoring at or below its own evaluator's threshold times
# CRITICAL_RATIO is treated as a critical hallucination on its own, regardless
# of its agent's aggregate rate -- relative to each item's own threshold
# rather than an absolute floor, so it stays meaningful whether the
# configured evaluator's scale is 0.0-1.0 or a 1-5 Likert range.
CRITICAL_RATIO = Decimal("0.5")
THRESHOLD_PERCENT = Decimal("5")


class CannotEvaluate(ValueError):
    """A required input is missing, invalid, or ambiguous."""


def measure_agent(agent_id: str, results: list[dict]) -> dict:
    """Aggregate one fleet agent's real per-request groundedness results."""
    if not results:
        raise CannotEvaluate(f"no_scores_for_agent:{agent_id}")
    ungrounded_ids, critical_ids, scores, seen_run_ids = [], [], [], set()
    for row in results:
        run_id = row.get("run_id")
        if not isinstance(run_id, str) or not run_id or run_id in seen_run_ids:
            raise CannotEvaluate("invalid_or_duplicate_run_id")
        seen_run_ids.add(run_id)
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
        scores.append(score)
        if not passed:
            ungrounded_ids.append(run_id)
        if score <= threshold * CRITICAL_RATIO:
            critical_ids.append(run_id)
    total = len(results)
    rate = Decimal(len(ungrounded_ids)) * 100 / total
    return {
        "agent_id": agent_id,
        "total": total,
        "ungrounded": len(ungrounded_ids),
        "ungrounded_run_ids": ungrounded_ids,
        "critical_run_ids": critical_ids,
        "rate_percent": float(rate),
        "average_score": float(sum(scores) / total),
    }


def rollup(fleet_results: dict[str, list[dict]]) -> dict:
    """Combine every fleet member's measurement into one fleet-level record.

    Requires at least one result for every agent in ``fleet_results`` --
    fails closed (``CannotEvaluate``) rather than silently rolling up a
    partial fleet.
    """
    if not fleet_results:
        raise CannotEvaluate("empty_fleet")
    per_agent = {agent_id: measure_agent(agent_id, results) for agent_id, results in fleet_results.items()}
    averages = {agent_id: measurement["average_score"] for agent_id, measurement in per_agent.items()}
    best_id = max(averages, key=averages.get)
    worst_id = min(averages, key=averages.get)
    any_agent_breach = any(
        measurement["rate_percent"] > float(THRESHOLD_PERCENT) or measurement["critical_run_ids"]
        for measurement in per_agent.values()
    )
    return {
        "per_agent": per_agent,
        "fleet_average_score": sum(averages.values()) / len(averages),
        "best_agent": {"agent_id": best_id, "average_score": averages[best_id]},
        "worst_agent": {"agent_id": worst_id, "average_score": averages[worst_id]},
        "any_agent_breach": any_agent_breach,
    }


def daily_trend(scored_events: list[dict]) -> list[dict]:
    """Aggregate real per-request scores into a day-bucketed trend line.

    ``scored_events`` is a list of ``{"day": "YYYY-MM-DD", "score": float}``
    entries, one per real, already-scored request (see ``demo.py``'s
    ``fetch_agent_history``) -- deliberately not scoped to one measurement
    window, unlike ``rollup()`` above. This is the "insights over a certain
    duration of time" a single window's snapshot decision cannot show: how
    one agent's real, Microsoft-scored groundedness moved day to day.
    Returns one row per day with data, sorted chronologically, empty list
    for no data (never a fabricated zero-sample day).
    """
    by_day: dict[str, list[float]] = {}
    for event in scored_events:
        by_day.setdefault(event["day"], []).append(event["score"])
    return [
        {"day": day, "average_score": sum(scores) / len(scores), "count": len(scores)}
        for day, scores in sorted(by_day.items())
    ]


def evaluate(window: dict, fleet_results: dict[str, list[dict]], *, retrieval_complete: bool) -> dict:
    """Produce one minimized fleet decision record, including fail-closed outcomes."""
    record = {
        "control_id": CONTROL_ID,
        "control_version": VERSION,
        "policy_version": VERSION,
        "evidence_version": VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "correlation_id": window.get("window_id"),
        "window": None,
        "fleet": None,
        "decision": "cannot_evaluate",
        "reason": "invalid_input",
        "accountable_role": "AI Governance Operations",
        "threshold_percent": float(THRESHOLD_PERCENT),
        "notification": {"status": "not_requested", "delivery_verified": False},
    }
    try:
        if not retrieval_complete:
            raise CannotEvaluate("evaluation_retrieval_unavailable_or_partial")
        fleet = rollup(fleet_results)
        record["window"] = {"number": window.get("window")}
        record["fleet"] = fleet
        record.update(
            decision="quality_review_required" if fleet["any_agent_breach"] else "no_review_required",
            accountable_role="Product Owner",
            reason=(
                "an_agent_breached_rate_or_critical_item" if fleet["any_agent_breach"]
                else "every_agent_within_threshold_no_critical_item"
            ),
        )
    except CannotEvaluate as error:
        record["reason"] = str(error)
    except (ValueError, TypeError, KeyError, AttributeError):
        record["reason"] = "invalid_or_missing_input"
    return record
