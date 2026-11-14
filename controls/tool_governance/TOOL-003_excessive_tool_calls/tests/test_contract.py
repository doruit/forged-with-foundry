"""Runtime reading of the approved budget from the governance contract."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.tool_003.contract import DEFAULT_CONTRACT, load_budgets


def _write(tmp_path: Path, mutate) -> Path:
    data = yaml.safe_load(DEFAULT_CONTRACT.read_text(encoding="utf-8"))
    mutate(data["spec"]["controls"][0]["evidence"])
    path = tmp_path / ".fwf/agents/tool-003-support-refunds/governance.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def test_shipped_contract_declares_single_refund_budget():
    declaration = load_budgets()
    assert declaration.status == "valid"
    assert declaration.budget_for("single_refund") == 4
    assert declaration.budget_for("bulk_refund") is None
    assert declaration.sha256 is not None


@pytest.mark.parametrize(
    "mutate",
    [
        lambda e: e.pop("taskBudgets"),
        lambda e: e.update(taskBudgets=[]),
        lambda e: e["taskBudgets"][0].update(maxToolCalls=0),
        lambda e: e["taskBudgets"][0].update(maxToolCalls=-3),
        lambda e: e["taskBudgets"][0].update(maxToolCalls="4"),
        lambda e: e["taskBudgets"][0].update(maxToolCalls=4.5),
        lambda e: e["taskBudgets"][0].update(taskType=""),
        lambda e: e["taskBudgets"].append({"taskType": "single_refund", "maxToolCalls": 9}),
    ],
    ids=["missing", "empty", "zero", "negative", "string", "fraction", "empty-task-type", "duplicate-task-type"],
)
def test_invalid_declarations_are_not_valid(tmp_path, mutate):
    declaration = load_budgets(_write(tmp_path, mutate))
    assert declaration.status == "invalid"
    assert declaration.budgets == {}


def test_missing_contract_is_unreadable(tmp_path):
    declaration = load_budgets(tmp_path / "missing.yaml")
    assert declaration.status == "unreadable"
    assert declaration.budget_for("single_refund") is None
