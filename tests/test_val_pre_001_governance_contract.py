"""Boundary-case tests for VAL-PRE-001's evidence schema (equivalent
coverage to the pre-migration scripts/validate_value_hypothesis.py test
suite, now expressed against the JSON Schema + shared validator instead of
hand-rolled Python). See docs/governance-contract.md.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))
import validate_governance_contract as vgc  # noqa: E402

_COMPLETE_ENTRY = {
    "id": "VAL-PRE-001",
    "version": "1.0.0",
    "evidence": {
        "owner": "it-service-desk-manager@contoso.example",
        "businessCaseId": "BIZ-CASE-HELPDESK-001",
        "expectedOutcome": "Reduce Tier-1 tickets needing human handling",
        "metric": {
            "name": "tier1_ticket_deflection_rate",
            "direction": "increase",
            "target": 35,
        },
        "baseline": {"status": "net_new"},
    },
}


def _contract_with_entry(entry: dict) -> dict:
    return {
        "apiVersion": "forgedwithfoundry.dev/v1alpha1",
        "kind": "AgentGovernanceContract",
        "metadata": {
            "agentId": "helpdesk-tier1-triage",
            "description": "Governance contract for the helpdesk triage agent",
            "source": "https://github.com/doruit/forged-with-foundry",
            "license": "MIT",
        },
        "spec": {
            "agentRef": {"definition": "./agent.yaml"},
            "controls": [entry],
        },
    }


def _assess(entry: dict) -> tuple[dict | None, list[str]]:
    return vgc.validate_control_entry("VAL-PRE-001", _contract_with_entry(entry))


def test_complete_entry_has_no_errors() -> None:
    _, errors = _assess(copy.deepcopy(_COMPLETE_ENTRY))
    assert errors == []


def test_blank_owner_is_rejected() -> None:
    entry = copy.deepcopy(_COMPLETE_ENTRY)
    entry["evidence"]["owner"] = "   "
    _, errors = _assess(entry)
    assert errors


def test_missing_owner_is_rejected() -> None:
    entry = copy.deepcopy(_COMPLETE_ENTRY)
    del entry["evidence"]["owner"]
    _, errors = _assess(entry)
    assert errors


def test_blank_business_case_id_is_rejected() -> None:
    entry = copy.deepcopy(_COMPLETE_ENTRY)
    entry["evidence"]["businessCaseId"] = ""
    _, errors = _assess(entry)
    assert errors


def test_missing_metric_name_is_rejected() -> None:
    entry = copy.deepcopy(_COMPLETE_ENTRY)
    del entry["evidence"]["metric"]["name"]
    _, errors = _assess(entry)
    assert errors


def test_missing_target_is_rejected() -> None:
    entry = copy.deepcopy(_COMPLETE_ENTRY)
    del entry["evidence"]["metric"]["target"]
    _, errors = _assess(entry)
    assert errors


def test_non_numeric_target_is_rejected() -> None:
    entry = copy.deepcopy(_COMPLETE_ENTRY)
    entry["evidence"]["metric"]["target"] = "banana"
    _, errors = _assess(entry)
    assert errors


def test_invalid_direction_is_rejected() -> None:
    entry = copy.deepcopy(_COMPLETE_ENTRY)
    entry["evidence"]["metric"]["direction"] = "sideways"
    _, errors = _assess(entry)
    assert errors


def test_invalid_baseline_status_is_rejected() -> None:
    entry = copy.deepcopy(_COMPLETE_ENTRY)
    entry["evidence"]["baseline"]["status"] = "guessed"
    _, errors = _assess(entry)
    assert errors


def test_missing_baseline_is_rejected() -> None:
    entry = copy.deepcopy(_COMPLETE_ENTRY)
    del entry["evidence"]["baseline"]
    _, errors = _assess(entry)
    assert errors


def test_missing_expected_outcome_is_rejected() -> None:
    entry = copy.deepcopy(_COMPLETE_ENTRY)
    del entry["evidence"]["expectedOutcome"]
    _, errors = _assess(entry)
    assert errors


def test_unexpected_extra_evidence_field_is_rejected() -> None:
    entry = copy.deepcopy(_COMPLETE_ENTRY)
    entry["evidence"]["unexpectedField"] = "should not be allowed"
    _, errors = _assess(entry)
    assert errors
