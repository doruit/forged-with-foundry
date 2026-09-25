"""Deterministic pooled-threshold, integrity, and minimization regression checks."""

from copy import deepcopy
from pathlib import Path
import sys
from uuid import uuid4

import pytest

CONTROL = Path(__file__).resolve().parents[1]
sys.modules.pop("evaluator", None)
sys.path.insert(0, str(CONTROL))
from evaluator import evaluate
sys.path.remove(str(CONTROL))
sys.modules.pop("evaluator", None)

CONTRACT = CONTROL.parent / "VAL-PRE-001_value_hypothesis_missing/fixtures/complete-workload/.fwf/agents/helpdesk-tier1-triage/governance.yaml"


def sample(deflected=(1, 1, 1, 1, 1, 1), total=6):
    run_id = str(uuid4())
    manifest = {"run_id": run_id, "completed": True,
                "started_at": "2026-09-21T00:00:00+00:00",
                "finished_at": "2026-09-21T09:00:00+00:00", "periods": []}
    rows = []
    for sequence, count in enumerate(deflected, 1):
        tickets = [{"ticket_id": f"ticket-{number:04d}", "kind": "account_unlock"}
                   for number in range(1, total + 1)]
        manifest["periods"].append({"sequence": sequence, "tickets": tickets})
        for number, ticket in enumerate(tickets):
            success = number < count
            rows.append({"item_count": 1, "properties": {
                "control_id": "VAL-002", "workload_version": "1.0.0",
                "agent_id": "helpdesk-tier1-triage", "metric_name": "tier1_ticket_deflection_rate",
                "run_id": run_id, "period": str(sequence), **ticket,
                "timestamp": f"2026-09-21T0{sequence}:00:00+00:00",
                "outcome": "deflected" if success else "escalated",
                "verified": "True", "human_handled": "False" if success else "True",
            }})
    return manifest, rows


@pytest.mark.parametrize("counts,total,decision", [
    # pooled 6/36 = 16.67% < 17.5% (50% of target 35)
    ((1, 1, 1, 1, 1, 1), 6, "reassess_required"),
    # pooled 7/36 = 19.44% >= 17.5%
    ((2, 1, 1, 1, 1, 1), 6, "no_reassessment_required"),
    # a single strong period cannot rescue a pooled shortfall: 30 deflected of 210
    # total is still 14.28% < 17.5%
    ((30, 0, 0, 0, 0, 0), 30, "reassess_required"),
    ((0, 0, 0, 0, 0, 0), 6, "reassess_required"),
    ((6, 6, 6, 6, 6, 6), 6, "no_reassessment_required"),
])
def test_given_pooled_rates_when_evaluated_then_exact_threshold_rule(counts, total, decision):
    manifest, rows = sample(counts, total)

    result = evaluate(CONTRACT, manifest, rows, query_complete=True)

    assert result["decision"] == decision
    assert (result["target_percent"], result["threshold_percent"]) == (35, 17.5)


def test_given_pooled_rate_when_computed_then_sums_events_not_averages_percentages():
    # Period 1: 100 tickets, 50 deflected (50%). Periods 2-6: 1 ticket, 0 deflected (0%).
    # Naive average of percentages would be ~8.3%; pooled sum is 50/105 = 47.6%.
    manifest = {"run_id": str(uuid4()), "completed": True,
                "started_at": "2026-09-21T00:00:00+00:00",
                "finished_at": "2026-09-21T09:00:00+00:00", "periods": []}
    rows = []
    sizes = [100, 1, 1, 1, 1, 1]
    deflected_counts = [50, 0, 0, 0, 0, 0]
    for sequence, (size, count) in enumerate(zip(sizes, deflected_counts), 1):
        tickets = [{"ticket_id": f"ticket-{number:04d}", "kind": "account_unlock"}
                   for number in range(1, size + 1)]
        manifest["periods"].append({"sequence": sequence, "tickets": tickets})
        for number, ticket in enumerate(tickets):
            success = number < count
            rows.append({"item_count": 1, "properties": {
                "control_id": "VAL-002", "workload_version": "1.0.0",
                "agent_id": "helpdesk-tier1-triage", "metric_name": "tier1_ticket_deflection_rate",
                "run_id": manifest["run_id"], "period": str(sequence), **ticket,
                "timestamp": f"2026-09-21T0{sequence}:00:00+00:00",
                "outcome": "deflected" if success else "escalated",
                "verified": "True", "human_handled": "False" if success else "True",
            }})

    result = evaluate(CONTRACT, manifest, rows, query_complete=True)

    assert result["pooled_percent"] == pytest.approx(50 / 105 * 100)
    assert result["decision"] == "no_reassessment_required"


@pytest.mark.parametrize("mutation", ["missing", "conflict", "unverified", "sampled",
                                     "bad_bool", "bad_period", "bad_metric", "bad_kind"])
def test_given_invalid_telemetry_when_evaluated_then_cannot_evaluate(mutation):
    manifest, rows = sample()
    if mutation == "missing":
        rows.pop()
    elif mutation == "conflict":
        duplicate = deepcopy(rows[0])
        duplicate["properties"].update(outcome="escalated", human_handled="True")
        rows.append(duplicate)
    elif mutation == "sampled":
        rows[0]["item_count"] = 2
    else:
        key, value = {"unverified": ("verified", "False"), "bad_bool": ("verified", "yes"),
                      "bad_period": ("period", True), "bad_metric": ("metric_name", "other"),
                      "bad_kind": ("kind", "hardware_repair")}[mutation]
        rows[0]["properties"][key] = value

    assert evaluate(CONTRACT, manifest, rows, query_complete=True)["decision"] == "cannot_evaluate"


def test_given_identical_duplicate_when_evaluated_then_counted_once():
    manifest, rows = sample()
    rows.append(deepcopy(rows[0]))

    result = evaluate(CONTRACT, manifest, rows, query_complete=True)

    assert result["decision"] == "reassess_required"
    assert result["periods"][0]["total"] == 6


@pytest.mark.parametrize("mutation", ["nonconsecutive", "unfinished", "empty", "overlap",
                                     "five_periods", "seven_periods"])
def test_given_invalid_periods_when_evaluated_then_cannot_evaluate(mutation):
    manifest, rows = sample()
    if mutation == "nonconsecutive":
        manifest["periods"][5]["sequence"] = 8
    elif mutation == "unfinished":
        manifest["completed"] = False
    elif mutation == "empty":
        manifest["periods"][0]["tickets"] = []
    elif mutation == "overlap":
        rows[0]["properties"]["timestamp"] = "2026-09-21T08:30:00+00:00"
    elif mutation == "five_periods":
        del manifest["periods"][5]
        rows = [row for row in rows if row["properties"]["period"] != "6"]
    else:
        manifest["periods"].append({"sequence": 7, "tickets": [
            {"ticket_id": "ticket-0001", "kind": "account_unlock"}]})

    assert evaluate(CONTRACT, manifest, rows, query_complete=True)["decision"] == "cannot_evaluate"


def test_given_partial_query_when_evaluated_then_no_healthy_result():
    manifest, rows = sample((6, 6, 6, 6, 6, 6))

    assert evaluate(CONTRACT, manifest, rows, query_complete=False)["decision"] == "cannot_evaluate"


def test_given_unresolved_but_claimed_verified_when_evaluated_then_cannot_evaluate():
    manifest, rows = sample()
    rows[0]["properties"].update(outcome="unresolved", verified="True", human_handled="False")

    assert evaluate(CONTRACT, manifest, rows, query_complete=True)["decision"] == "cannot_evaluate"


@pytest.mark.parametrize("replacement", ["target: -1", "target: 101", "target: .nan", "target: true"])
def test_given_invalid_target_when_evaluated_then_cannot_evaluate(tmp_path, replacement):
    contract = tmp_path / "governance.yaml"
    contract.write_text(CONTRACT.read_text().replace("target: 35", replacement))
    manifest, rows = sample()

    assert evaluate(contract, manifest, rows, query_complete=True)["decision"] == "cannot_evaluate"


def test_given_decimal_target_when_evaluated_then_precision_is_respected(tmp_path):
    contract = tmp_path / "governance.yaml"
    contract.write_text(CONTRACT.read_text().replace("target: 35", "target: 33.333333333333333333"))
    # threshold is ~16.6667% of a non-terminating target; 20% pooled clears it without
    # relying on float-exact equality (YAML/JSON floats cannot round-trip this target
    # exactly, so an equality-at-the-boundary assertion would be flaky by construction).
    manifest, rows = sample((20, 20, 20, 20, 20, 20), 100)

    result = evaluate(contract, manifest, rows, query_complete=True)

    assert result["decision"] == "no_reassessment_required"


def test_given_invalid_contract_when_evaluated_then_errors_are_minimized(tmp_path):
    contract = tmp_path / "governance.yaml"
    contract.write_text("private-person@example.com: [invalid")
    manifest, rows = sample()

    result = evaluate(contract, manifest, rows, query_complete=True)

    assert result["decision"] == "cannot_evaluate"
    assert "private-person" not in str(result)
    assert "ticket-0001" not in str(result)


def test_given_complete_contract_when_evaluated_then_business_case_is_propagated():
    manifest, rows = sample()

    result = evaluate(CONTRACT, manifest, rows, query_complete=True)

    assert result["business_case_id"]
    assert result["window_periods"] == 6
