"""Boundary-case tests for PRI-PRE-002's evidence schema. Added alongside
this control's pre-existing Azure Policy demo, which evaluates
deployment-request tags directly and is unaffected by this file -- see
docs/governance-contract.md and docs/pre-live-policy-gate-consolidation.md.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))
import validate_governance_contract as vgc  # noqa: E402

_COMPLETE_ENTRY = {
    "id": "PRI-PRE-002",
    "version": "1.0.0",
    "evidence": {
        "lawfulBasis": "contract",
        "purposeId": "PURPOSE-CUSTOMER-SUPPORT-001",
    },
}


def _contract_with_entry(entry: dict) -> dict:
    return {
        "apiVersion": "forgedwithfoundry.dev/v1alpha1",
        "kind": "AgentGovernanceContract",
        "metadata": {
            "agentId": "customer-support-agent",
            "description": "Governance contract for the customer support triage agent",
            "source": "https://github.com/doruit/forged-with-foundry",
            "license": "MIT",
        },
        "spec": {
            "agentRef": {"definition": "./agent.yaml"},
            "controls": [entry],
        },
    }


def _assess(entry: dict) -> tuple[dict | None, list[str]]:
    return vgc.validate_control_entry("PRI-PRE-002", _contract_with_entry(entry))


def test_complete_entry_has_no_errors() -> None:
    _, errors = _assess(copy.deepcopy(_COMPLETE_ENTRY))
    assert errors == []


def test_missing_lawful_basis_is_rejected() -> None:
    entry = copy.deepcopy(_COMPLETE_ENTRY)
    del entry["evidence"]["lawfulBasis"]
    _, errors = _assess(entry)
    assert errors


def test_unrecognized_lawful_basis_is_rejected() -> None:
    entry = copy.deepcopy(_COMPLETE_ENTRY)
    entry["evidence"]["lawfulBasis"] = "because_we_felt_like_it"
    _, errors = _assess(entry)
    assert errors


def test_missing_purpose_id_is_rejected() -> None:
    entry = copy.deepcopy(_COMPLETE_ENTRY)
    del entry["evidence"]["purposeId"]
    _, errors = _assess(entry)
    assert errors


def test_blank_purpose_id_is_rejected() -> None:
    entry = copy.deepcopy(_COMPLETE_ENTRY)
    entry["evidence"]["purposeId"] = "   "
    _, errors = _assess(entry)
    assert errors


def test_every_gdpr_article_6_1_category_is_accepted() -> None:
    for basis in ("consent", "contract", "legal_obligation", "vital_interests",
                  "public_task", "legitimate_interests"):
        entry = copy.deepcopy(_COMPLETE_ENTRY)
        entry["evidence"]["lawfulBasis"] = basis
        _, errors = _assess(entry)
        assert errors == [], f"{basis} should be accepted"


def test_unexpected_extra_evidence_field_is_rejected() -> None:
    entry = copy.deepcopy(_COMPLETE_ENTRY)
    entry["evidence"]["unexpectedField"] = "should not be allowed"
    _, errors = _assess(entry)
    assert errors
