"""Boundary-case tests for PRI-PRE-003's evidence schema. Added alongside
this control's pre-existing Azure Policy demo, which evaluates
deployment-request tags directly and is unaffected by this file -- see
docs/governance-contract.md and docs/pre-live-policy-gate-consolidation.md.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))
import validate_governance_contract as vgc  # noqa: E402

_COMPLETE_ENTRY = {
    "id": "PRI-PRE-003",
    "version": "1.0.0",
    "evidence": {
        "governedDataPresent": True,
        "retentionDataCategory": "conversation_transcripts",
        "retentionStorageSystem": "log-analytics-workspace",
        "retentionPeriodDays": 90,
        "retentionDisposition": "delete",
        "retentionOwner": "privacy-officer@contoso.example",
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
    return vgc.validate_control_entry("PRI-PRE-003", _contract_with_entry(entry))


def test_complete_entry_has_no_errors() -> None:
    _, errors = _assess(copy.deepcopy(_COMPLETE_ENTRY))
    assert errors == []


def test_no_governed_data_needs_no_retention_fields() -> None:
    entry = {"id": "PRI-PRE-003", "version": "1.0.0", "evidence": {"governedDataPresent": False}}
    _, errors = _assess(entry)
    assert errors == []


def test_governed_data_present_without_any_retention_field_is_rejected() -> None:
    entry = {"id": "PRI-PRE-003", "version": "1.0.0", "evidence": {"governedDataPresent": True}}
    _, errors = _assess(entry)
    assert errors


@pytest.mark.parametrize("missing_field", [
    "retentionDataCategory", "retentionStorageSystem", "retentionPeriodDays",
    "retentionDisposition", "retentionOwner",
])
def test_governed_data_present_missing_one_retention_field_is_rejected(missing_field) -> None:
    entry = copy.deepcopy(_COMPLETE_ENTRY)
    del entry["evidence"][missing_field]
    _, errors = _assess(entry)
    assert errors


@pytest.mark.parametrize("period_days", [0, -5, 100000, "ninety"])
def test_invalid_retention_period_is_rejected(period_days) -> None:
    entry = copy.deepcopy(_COMPLETE_ENTRY)
    entry["evidence"]["retentionPeriodDays"] = period_days
    _, errors = _assess(entry)
    assert errors


def test_unrecognized_disposition_is_rejected() -> None:
    entry = copy.deepcopy(_COMPLETE_ENTRY)
    entry["evidence"]["retentionDisposition"] = "keep_forever"
    _, errors = _assess(entry)
    assert errors


def test_archive_disposition_is_accepted() -> None:
    entry = copy.deepcopy(_COMPLETE_ENTRY)
    entry["evidence"]["retentionDisposition"] = "archive"
    _, errors = _assess(entry)
    assert errors == []


def test_blank_retention_owner_is_rejected() -> None:
    entry = copy.deepcopy(_COMPLETE_ENTRY)
    entry["evidence"]["retentionOwner"] = "   "
    _, errors = _assess(entry)
    assert errors


def test_unexpected_extra_evidence_field_is_rejected() -> None:
    entry = copy.deepcopy(_COMPLETE_ENTRY)
    entry["evidence"]["unexpectedField"] = "should not be allowed"
    _, errors = _assess(entry)
    assert errors
