"""Boundary-case tests for PRI-PRE-001's evidence schema. Added alongside
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
    "id": "PRI-PRE-001",
    "version": "1.0.0",
    "evidence": {
        "dpiaStatus": "approved",
        "dpiaEvidenceId": "DPIA-2026-014",
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
    return vgc.validate_control_entry("PRI-PRE-001", _contract_with_entry(entry))


def test_complete_entry_has_no_errors() -> None:
    _, errors = _assess(copy.deepcopy(_COMPLETE_ENTRY))
    assert errors == []


def test_missing_dpia_status_is_rejected() -> None:
    entry = copy.deepcopy(_COMPLETE_ENTRY)
    del entry["evidence"]["dpiaStatus"]
    _, errors = _assess(entry)
    assert errors


def test_invalid_dpia_status_is_rejected() -> None:
    entry = copy.deepcopy(_COMPLETE_ENTRY)
    entry["evidence"]["dpiaStatus"] = "rubber_stamped"
    _, errors = _assess(entry)
    assert errors


def test_pending_status_without_evidence_id_is_accepted() -> None:
    # A control that has not reached approval yet is structurally
    # complete -- it just isn't "approved". Adequacy is not this schema's
    # job; see the control's ASSESSMENT.md.
    entry = {"id": "PRI-PRE-001", "version": "1.0.0", "evidence": {"dpiaStatus": "pending"}}
    _, errors = _assess(entry)
    assert errors == []


def test_approved_status_without_evidence_id_is_rejected() -> None:
    entry = copy.deepcopy(_COMPLETE_ENTRY)
    del entry["evidence"]["dpiaEvidenceId"]
    _, errors = _assess(entry)
    assert errors


def test_blank_evidence_id_is_rejected() -> None:
    entry = copy.deepcopy(_COMPLETE_ENTRY)
    entry["evidence"]["dpiaEvidenceId"] = "   "
    _, errors = _assess(entry)
    assert errors


def test_unexpected_extra_evidence_field_is_rejected() -> None:
    entry = copy.deepcopy(_COMPLETE_ENTRY)
    entry["evidence"]["unexpectedField"] = "should not be allowed"
    _, errors = _assess(entry)
    assert errors
