"""Deterministic threshold, integrity, and minimization regression checks."""

from copy import deepcopy
from pathlib import Path
import sys
from uuid import uuid4

import pytest

CONTROL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CONTROL))
from evaluator import evaluate

CONTRACT = CONTROL.parent / "VAL-PRE-001_value_hypothesis_missing/fixtures/complete-workload/.fwf/agents/helpdesk-tier1-triage/governance.yaml"


def sample(deflected=(27, 27)):
    run_id = str(uuid4())
    manifest = {"run_id": run_id, "completed": True,
                "started_at": "2026-09-21T00:00:00+00:00",
                "finished_at": "2026-09-21T03:00:00+00:00", "periods": []}
    rows = []
    for sequence, count in enumerate(deflected, 1):
        tickets = [{"ticket_id": f"ticket-{number:04d}", "kind": "account_unlock"}
                   for number in range(1, 101)]
        manifest["periods"].append({"sequence": sequence, "tickets": tickets})
        for number, ticket in enumerate(tickets):
            success = number < count
            rows.append({"item_count": 1, "properties": {
                "control_id": "VAL-001", "workload_version": "1.0.0",
                "agent_id": "helpdesk-tier1-triage", "metric_name": "tier1_ticket_deflection_rate",
                "run_id": run_id, "period": str(sequence), **ticket,
                "timestamp": f"2026-09-21T0{sequence}:00:00+00:00",
                "outcome": "deflected" if success else "escalated",
                "verified": "True", "human_handled": "False" if success else "True",
            }})
    return manifest, rows


@pytest.mark.parametrize("counts,decision", [
    ((27, 27), "review_required"), ((28, 28), "no_review_required"),
    ((27, 28), "no_review_required"), ((35, 20), "no_review_required"),
    ((0, 0), "review_required"), ((100, 100), "no_review_required"),
])
def test_given_period_rates_when_evaluated_then_exact_threshold_rule(counts, decision):
    manifest, rows = sample(counts)

    result = evaluate(CONTRACT, manifest, rows, query_complete=True)

    assert result["decision"] == decision
    assert (result["target_percent"], result["threshold_percent"]) == (35, 28)


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

    assert result["decision"] == "review_required"
    assert result["periods"][0]["total"] == 100


@pytest.mark.parametrize("mutation", ["nonconsecutive", "unfinished", "empty", "overlap"])
def test_given_invalid_periods_when_evaluated_then_cannot_evaluate(mutation):
    manifest, rows = sample()
    if mutation == "nonconsecutive":
        manifest["periods"][1]["sequence"] = 3
    elif mutation == "unfinished":
        manifest["completed"] = False
    elif mutation == "empty":
        manifest["periods"][0]["tickets"] = []
    else:
        rows[0]["properties"]["timestamp"] = "2026-09-21T02:30:00+00:00"

    assert evaluate(CONTRACT, manifest, rows, query_complete=True)["decision"] == "cannot_evaluate"


def test_given_partial_query_when_evaluated_then_no_healthy_result():
    manifest, rows = sample((100, 100))

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


def test_given_invalid_contract_when_evaluated_then_errors_are_minimized(tmp_path):
    contract = tmp_path / "governance.yaml"
    contract.write_text("private-person@example.com: [invalid")
    manifest, rows = sample()

    result = evaluate(contract, manifest, rows, query_complete=True)

    assert result["decision"] == "cannot_evaluate"
    assert "private-person" not in str(result)
    assert "ticket-0001" not in str(result)