"""Governance-contract evidence tests for KNW-001."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_governance_contract as vgc

from test_governance_contract_consistency import VALID_HELPDESK_CONTRACT

AGENT = "helpdesk-tier1-triage"


def _contract_with_knw_001(**overrides: object) -> dict[str, object]:
    contract = copy.deepcopy(VALID_HELPDESK_CONTRACT)
    evidence = {
        "policyVersion": "knw001-v1",
        "sourceId": "vpn-reset-guide",
        "sourceEtagSha256": "b530f82d4c9968b4426ee308ffaf63c32b1d0ef16ee8b22d0f9bf39c62a43afa",
        "overallState": "fresh",
        "reviewState": "fresh",
        "indexState": "current",
        "reviewRecordId": "f1ac2192-4933-4ad5-9052-d9b0bc2d2845",
        "notificationRoles": [],
        "timestamp": "2026-11-08T14:34:10Z",
        "correlationId": "demo-correlation-001",
        "accountableRole": "Control Operator",
    }
    evidence.update(overrides)
    contract["spec"]["controls"].append({"id": "KNW-001", "version": "1.0.0", "evidence": evidence})
    return contract


def _errors(contract: dict[str, object]) -> list[str]:
    return vgc.validate_contract(contract, agent_dir_name=AGENT)


def test_complete_fresh_knw_001_evidence_validates() -> None:
    assert _errors(_contract_with_knw_001()) == []


def test_review_required_with_owner_notification_validates() -> None:
    contract = _contract_with_knw_001(
        overallState="review_required",
        reviewState="review_required",
        indexState="sync_pending",
        reviewRecordId=None,
        notificationRoles=["Knowledge Owner", "Control Operator"],
        accountableRole="Knowledge Owner",
    )
    assert _errors(contract) == []


def test_cannot_evaluate_with_operator_notification_validates() -> None:
    contract = _contract_with_knw_001(
        overallState="cannot_evaluate",
        reviewState="cannot_evaluate",
        indexState="cannot_evaluate",
        reviewRecordId=None,
        notificationRoles=["Control Operator"],
    )
    assert _errors(contract) == []


def test_missing_correlation_fails_closed() -> None:
    contract = _contract_with_knw_001()
    del contract["spec"]["controls"][1]["evidence"]["correlationId"]
    assert _errors(contract)


def test_fresh_cannot_hide_lagging_index() -> None:
    assert _errors(_contract_with_knw_001(indexState="sync_pending"))


def test_fresh_requires_bound_review_record() -> None:
    assert _errors(_contract_with_knw_001(reviewRecordId=None))


def test_review_required_must_notify_owner() -> None:
    contract = _contract_with_knw_001(
        overallState="review_required",
        reviewState="review_required",
        reviewRecordId=None,
        notificationRoles=["Control Operator"],
    )
    assert _errors(contract)


def test_cannot_evaluate_requires_an_unevaluable_axis() -> None:
    contract = _contract_with_knw_001(
        overallState="cannot_evaluate",
        notificationRoles=["Control Operator"],
    )
    assert _errors(contract)


def test_raw_etag_is_rejected() -> None:
    assert _errors(_contract_with_knw_001(sourceEtagSha256='"0x8DE1234567890AB"'))
