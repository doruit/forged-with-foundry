"""Governance-contract evidence tests for AUT-002."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_governance_contract as vgc

from test_governance_contract_consistency import VALID_HELPDESK_CONTRACT


def _contract_with_aut_002() -> dict[str, object]:
    contract = copy.deepcopy(VALID_HELPDESK_CONTRACT)
    contract["spec"]["controls"].append(
        {
            "id": "AUT-002",
            "version": "1.0.0",
            "evidence": {
                "decision": "allow",
                "toolName": "permanently_delete_demo_record",
                "actionIdentity": "sha256:7598b31cf2c0ed5ac3669132f2835305ed329e81a21e19e07a3bb757ad49cecc",
                "executed": True,
                "verified": True,
                "timestamp": "2026-09-28T12:29:59Z",
                "correlationId": "demo-correlation-001",
                "accountableRole": "Ops Manager",
            },
        }
    )
    return contract


def test_complete_aut_002_evidence_validates() -> None:
    errors = vgc.validate_contract(_contract_with_aut_002(), agent_dir_name="helpdesk-tier1-triage")

    assert errors == []


def test_aut_002_missing_verification_fails_closed() -> None:
    contract = _contract_with_aut_002()
    del contract["spec"]["controls"][1]["evidence"]["verified"]

    errors = vgc.validate_contract(contract, agent_dir_name="helpdesk-tier1-triage")

    assert errors


def test_aut_002_escalation_cannot_claim_execution() -> None:
    contract = _contract_with_aut_002()
    evidence = contract["spec"]["controls"][1]["evidence"]
    evidence["decision"] = "escalate"
    evidence["executed"] = True

    errors = vgc.validate_contract(contract, agent_dir_name="helpdesk-tier1-triage")

    assert errors