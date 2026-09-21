"""Evaluate one complete synthetic run against the validated VAL-PRE-001 entry."""

from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
import re
import sys
from uuid import UUID

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.validate_governance_contract import (
    ContractReadError,
    parse_contract_bytes,
    read_contract_bytes,
    validate_contract,
    validate_control_entry,
)

AGENT_ID = "helpdesk-tier1-triage"
METRIC = "tier1_ticket_deflection_rate"
VERSION = "1.0.0"


class CannotEvaluate(ValueError):
    """A required input is missing, invalid, or ambiguous."""


def instant(value: object) -> datetime:
    """Require a timezone-aware timestamp."""
    if not isinstance(value, str):
        raise CannotEvaluate("invalid_timestamp")
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise CannotEvaluate("invalid_timestamp")
    return result


def contract_target(path: Path) -> dict:
    """Read and hash exactly the bytes validated by the shared validator."""
    raw = read_contract_bytes(path)
    data = parse_contract_bytes(raw, source="VAL-PRE-001 contract")
    errors = validate_contract(data, agent_dir_name=AGENT_ID)
    entry, entry_errors = validate_control_entry("VAL-PRE-001", data)
    if errors or entry_errors or entry is None:
        raise CannotEvaluate("invalid_contract")
    evidence = entry["evidence"]
    metric = evidence["metric"]
    if metric["name"] != METRIC or metric["direction"] != "increase":
        raise CannotEvaluate("unsupported_metric")
    target = Decimal(str(metric["target"]))
    if not target.is_finite() or not 0 < target <= 100:
        raise CannotEvaluate("invalid_absolute_percent_target")
    return {
        "reference": ".fwf/agents/helpdesk-tier1-triage/governance.yaml",
        "sha256": sha256(raw).hexdigest(),
        "api_version": data["apiVersion"],
        "control_id": entry["id"],
        "control_version": entry["version"],
        "owner": evidence["owner"],
        "target": target,
        "threshold": target * Decimal("0.8"),
    }


def normalized_bool(value: object) -> bool:
    """Accept only booleans or their exact Azure custom-dimension encodings."""
    if type(value) is bool:
        return value
    if value in ("True", "true"):
        return True
    if value in ("False", "false"):
        return False
    raise CannotEvaluate("invalid_outcome_verification")


def measure(manifest: dict, rows: list[dict]) -> list[dict]:
    """Deduplicate verified events and require every expected ticket exactly once."""
    run_id = manifest["run_id"]
    if str(UUID(run_id)) != run_id or manifest.get("completed") is not True:
        raise CannotEvaluate("incomplete_run")
    started, finished = instant(manifest["started_at"]), instant(manifest["finished_at"])
    if finished < started:
        raise CannotEvaluate("invalid_run_window")
    periods = manifest["periods"]
    if len(periods) != 2:
        raise CannotEvaluate("require_two_periods")
    sequence = [period["sequence"] for period in periods]
    if any(type(value) is not int or value < 1 for value in sequence):
        raise CannotEvaluate("invalid_period")
    if sequence[1] != sequence[0] + 1:
        raise CannotEvaluate("nonconsecutive_periods")
    expected = {}
    for period in periods:
        if not period["tickets"]:
            raise CannotEvaluate("empty_period")
        for ticket in period["tickets"]:
            identity = (period["sequence"], ticket["ticket_id"])
            if identity in expected or not re.fullmatch(r"ticket-[0-9]{4}", ticket["ticket_id"]):
                raise CannotEvaluate("invalid_expected_ticket")
            if ticket["kind"] not in ("account_unlock", "software_install", "hardware_repair"):
                raise CannotEvaluate("invalid_expected_ticket")
            expected[identity] = ticket["kind"]
    observed = {}
    event_times = {number: [] for number in sequence}
    for row in rows:
        if row.get("item_count") != 1 or type(row.get("item_count")) is bool:
            raise CannotEvaluate("sampled_or_invalid_telemetry")
        event = row["properties"]
        if (event.get("run_id") != run_id or event.get("agent_id") != AGENT_ID
                or event.get("control_id") != "VAL-001" or event.get("metric_name") != METRIC
                or event.get("workload_version") != VERSION):
            raise CannotEvaluate("unexpected_telemetry")
        period = event["period"]
        if isinstance(period, str) and re.fullmatch(r"[1-9][0-9]*", period):
            period = int(period)
        if type(period) is not int:
            raise CannotEvaluate("invalid_period")
        identity = (period, event["ticket_id"])
        if identity not in expected or expected[identity] != event["kind"]:
            raise CannotEvaluate("unexpected_ticket")
        timestamp = instant(event["timestamp"])
        if not started <= timestamp <= finished:
            raise CannotEvaluate("outcome_outside_run")
        outcome = event["outcome"]
        verified = normalized_bool(event["verified"])
        human = normalized_bool(event["human_handled"])
        if outcome not in ("deflected", "escalated", "unresolved"):
            raise CannotEvaluate("invalid_outcome")
        if outcome == "unresolved" or not verified or human != (outcome == "escalated"):
            raise CannotEvaluate("unverified_outcome")
        facts = (outcome, verified, human)
        if identity in observed and observed[identity] != facts:
            raise CannotEvaluate("conflicting_duplicates")
        observed[identity] = facts
        event_times[period].append(timestamp)
    if observed.keys() != expected.keys():
        raise CannotEvaluate("incomplete_telemetry")
    if max(event_times[sequence[0]]) > min(event_times[sequence[1]]):
        raise CannotEvaluate("overlapping_periods")
    measurements = []
    for number in sequence:
        outcomes = [facts[0] for identity, facts in observed.items() if identity[0] == number]
        deflected = outcomes.count("deflected")
        measurements.append({
            "sequence": number, "total": len(outcomes), "deflected": deflected,
            "percent": float(Decimal(deflected) * 100 / len(outcomes)),
        })
    return measurements


def evaluate(path: Path, manifest: dict, rows: list[dict], *, query_complete: bool) -> dict:
    """Produce one minimized decision record, including fail-closed outcomes."""
    record = {
        "control_id": "VAL-001", "control_version": VERSION, "policy_version": VERSION,
        "evidence_version": VERSION, "agent_id": AGENT_ID, "metric_name": METRIC,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "correlation_id": None, "contract": None, "periods": [],
        "decision": "cannot_evaluate", "reason": "invalid_input",
        "accountable_role": "Business Owner", "owner": None,
        "target_percent": None, "threshold_percent": None,
        "notification": {"status": "not_requested", "delivery_verified": False},
    }
    try:
        run_id = manifest["run_id"]
        if str(UUID(run_id)) != run_id:
            raise CannotEvaluate("invalid_run_id")
        record["correlation_id"] = run_id
        target = contract_target(path)
        target_value = target.pop("target")
        threshold_value = target.pop("threshold")
        record.update(owner=target.pop("owner"), target_percent=float(target_value),
                  threshold_percent=float(threshold_value), contract=target)
        if not query_complete:
            raise CannotEvaluate("telemetry_query_unavailable_or_partial")
        measurements = measure(manifest, rows)
        threshold = threshold_value
        underperforming = all(
            Decimal(period["deflected"]) * 100 < threshold * period["total"]
            for period in measurements
        )
        record.update(periods=measurements,
                      decision="review_required" if underperforming else "no_review_required",
                      reason="two_periods_strictly_below_threshold" if underperforming
                      else "sustained_underperformance_not_observed")
    except CannotEvaluate as error:
        record["reason"] = str(error)
    except (ContractReadError, OSError, ValueError, TypeError, KeyError, AttributeError):
        record["reason"] = "invalid_or_missing_input"
    return record