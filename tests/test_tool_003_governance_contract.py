"""Governance-contract tests for the TOOL-003 budget declaration."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_governance_contract as vgc

from test_governance_contract_consistency import VALID_HELPDESK_CONTRACT


def _contract_with_tool_003() -> dict[str, object]:
    contract = copy.deepcopy(VALID_HELPDESK_CONTRACT)
    contract["spec"]["controls"].append(
        {
            "id": "TOOL-003",
            "version": "1.0.0",
            "evidence": {
                "taskBudgets": [{"taskType": "single_refund", "maxToolCalls": 4}],
                "reviewRef": "SYNTHETIC-TOOL-BUDGET-REVIEW-001",
                "reviewedOn": "2026-11-14",
                "accountableRole": "AI Ops Lead",
            },
        }
    )
    return contract


def _errors(contract) -> list[str]:
    return vgc.validate_contract(contract, agent_dir_name="helpdesk-tier1-triage")


def test_complete_tool_003_declaration_validates() -> None:
    assert _errors(_contract_with_tool_003()) == []


def test_tool_003_without_budgets_fails_closed() -> None:
    contract = _contract_with_tool_003()
    contract["spec"]["controls"][1]["evidence"]["taskBudgets"] = []
    assert _errors(contract)


def test_tool_003_zero_budget_fails_closed() -> None:
    contract = _contract_with_tool_003()
    contract["spec"]["controls"][1]["evidence"]["taskBudgets"][0]["maxToolCalls"] = 0
    assert _errors(contract)


def test_tool_003_wrong_accountable_role_fails_closed() -> None:
    contract = _contract_with_tool_003()
    contract["spec"]["controls"][1]["evidence"]["accountableRole"] = "Ops Manager"
    assert _errors(contract)


def test_shipped_tool_003_workload_contract_validates() -> None:
    root = Path(__file__).resolve().parents[1] / "controls/tool_governance/TOOL-003_excessive_tool_calls/workload"
    [path] = vgc.discover_contracts(root)
    assert vgc.validate_contract(vgc.load_contract(path), agent_dir_name="tool-003-support-refunds") == []
