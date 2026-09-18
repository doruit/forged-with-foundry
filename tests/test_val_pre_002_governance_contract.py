"""Boundary-case tests for VAL-PRE-002's evidence schema (KPI baseline
missing): a claimed 'measured' baseline must record an actual value and
date; 'net_new' needs neither. Self-contained -- does not depend on a
VAL-PRE-001 entry existing in the same contract.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))
import validate_governance_contract as vgc  # noqa: E402

_MEASURED_COMPLETE_ENTRY = {
    "id": "VAL-PRE-002",
    "version": "1.0.0",
    "evidence": {"baseline": {"status": "measured", "value": 28, "measuredDate": "2026-06-01"}},
}
_NET_NEW_ENTRY = {
    "id": "VAL-PRE-002",
    "version": "1.0.0",
    "evidence": {"baseline": {"status": "net_new"}},
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
    return vgc.validate_control_entry("VAL-PRE-002", _contract_with_entry(entry))


def test_measured_baseline_with_value_and_date_is_complete() -> None:
    _, errors = _assess(copy.deepcopy(_MEASURED_COMPLETE_ENTRY))
    assert errors == []


def test_net_new_baseline_needs_no_value_or_date() -> None:
    _, errors = _assess(copy.deepcopy(_NET_NEW_ENTRY))
    assert errors == []


def test_measured_baseline_missing_value_is_rejected() -> None:
    entry = copy.deepcopy(_MEASURED_COMPLETE_ENTRY)
    del entry["evidence"]["baseline"]["value"]
    _, errors = _assess(entry)
    assert errors


def test_measured_baseline_missing_date_is_rejected() -> None:
    entry = copy.deepcopy(_MEASURED_COMPLETE_ENTRY)
    del entry["evidence"]["baseline"]["measuredDate"]
    _, errors = _assess(entry)
    assert errors


def test_measured_baseline_with_non_numeric_value_is_rejected() -> None:
    entry = copy.deepcopy(_MEASURED_COMPLETE_ENTRY)
    entry["evidence"]["baseline"]["value"] = "twenty-eight"
    _, errors = _assess(entry)
    assert errors


def test_measured_baseline_with_malformed_date_is_rejected() -> None:
    entry = copy.deepcopy(_MEASURED_COMPLETE_ENTRY)
    entry["evidence"]["baseline"]["measuredDate"] = "06/01/2026"
    _, errors = _assess(entry)
    assert errors


def test_invalid_baseline_status_is_rejected() -> None:
    entry = copy.deepcopy(_NET_NEW_ENTRY)
    entry["evidence"]["baseline"]["status"] = "guessed"
    _, errors = _assess(entry)
    assert errors


def test_missing_baseline_is_rejected() -> None:
    entry = {"id": "VAL-PRE-002", "version": "1.0.0", "evidence": {}}
    _, errors = _assess(entry)
    assert errors


def test_entry_is_self_contained_without_a_val_pre_001_sibling() -> None:
    """VAL-PRE-002 must validate correctly with no other control entry present."""
    contract = _contract_with_entry(copy.deepcopy(_MEASURED_COMPLETE_ENTRY))
    assert len(contract["spec"]["controls"]) == 1
    errors = vgc.validate_contract(contract, agent_dir_name="helpdesk-tier1-triage")
    assert errors == []
