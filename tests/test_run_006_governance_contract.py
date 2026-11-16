"""Governance-contract tests for the RUN-006 threshold declaration."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_governance_contract as vgc

from test_governance_contract_consistency import VALID_HELPDESK_CONTRACT


def _contract_with_run_006() -> dict[str, object]:
    contract = copy.deepcopy(VALID_HELPDESK_CONTRACT)
    contract["spec"]["controls"].append(
        {
            "id": "RUN-006",
            "version": "1.0.0",
            "evidence": {
                "repeatThreshold": 3,
                "reviewRef": "SYNTHETIC-LOOP-THRESHOLD-REVIEW-001",
                "reviewedOn": "2026-11-14",
                "accountableRole": "AI Ops Lead",
            },
        }
    )
    return contract


def _errors(contract) -> list[str]:
    return vgc.validate_contract(contract, agent_dir_name="helpdesk-tier1-triage")


def test_complete_run_006_declaration_validates() -> None:
    assert _errors(_contract_with_run_006()) == []


def test_run_006_without_threshold_fails_closed() -> None:
    contract = _contract_with_run_006()
    del contract["spec"]["controls"][1]["evidence"]["repeatThreshold"]
    assert _errors(contract)


def test_run_006_threshold_of_one_fails_closed() -> None:
    contract = _contract_with_run_006()
    contract["spec"]["controls"][1]["evidence"]["repeatThreshold"] = 1
    assert _errors(contract)


def test_run_006_wrong_accountable_role_fails_closed() -> None:
    contract = _contract_with_run_006()
    contract["spec"]["controls"][1]["evidence"]["accountableRole"] = "Ops Manager"
    assert _errors(contract)


def test_shipped_run_006_workload_contract_validates() -> None:
    root = Path(__file__).resolve().parents[1] / "controls/runtime_and_operations/RUN-006_agent_loop_or_retry_storm/workload"
    [path] = vgc.discover_contracts(root)
    assert vgc.validate_contract(vgc.load_contract(path), agent_dir_name="run-006-support-refunds") == []
