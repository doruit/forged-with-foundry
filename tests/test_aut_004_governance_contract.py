"""Governance-contract tests for the AUT-004 stop-scope declaration."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_governance_contract as vgc

from test_governance_contract_consistency import VALID_HELPDESK_CONTRACT


def _contract_with_aut_004() -> dict[str, object]:
    contract = copy.deepcopy(VALID_HELPDESK_CONTRACT)
    contract["spec"]["controls"].append(
        {
            "id": "AUT-004",
            "version": "1.0.0",
            "evidence": {
                "stopScopes": [{"toolName": "issue_refund", "flagName": "aut004-support-refunds-issue-refund"}],
                "failureMode": "stop_unless_enabled",
                "reviewRef": "SYNTHETIC-EMERGENCY-STOP-REVIEW-001",
                "reviewedOn": "2026-11-14",
                "accountableRole": "Ops Manager",
            },
        }
    )
    return contract


def _errors(contract) -> list[str]:
    return vgc.validate_contract(contract, agent_dir_name="helpdesk-tier1-triage")


def test_complete_aut_004_declaration_validates() -> None:
    assert _errors(_contract_with_aut_004()) == []


def test_aut_004_without_stop_scope_fails_closed() -> None:
    contract = _contract_with_aut_004()
    contract["spec"]["controls"][1]["evidence"]["stopScopes"] = []
    assert _errors(contract)


def test_aut_004_fail_open_mode_is_rejected() -> None:
    contract = _contract_with_aut_004()
    contract["spec"]["controls"][1]["evidence"]["failureMode"] = "allow_on_read_failure"
    assert _errors(contract)


def test_aut_004_wrong_accountable_role_fails_closed() -> None:
    contract = _contract_with_aut_004()
    contract["spec"]["controls"][1]["evidence"]["accountableRole"] = "AI Ops Lead"
    assert _errors(contract)


def test_shipped_aut_004_workload_contract_validates() -> None:
    root = Path(__file__).resolve().parents[1] / "controls/autonomy_and_human_oversight/AUT-004_emergency_stop_not_enforced/workload"
    [path] = vgc.discover_contracts(root)
    assert vgc.validate_contract(vgc.load_contract(path), agent_dir_name="aut-004-support-refunds") == []
