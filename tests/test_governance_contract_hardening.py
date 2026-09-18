"""Regression tests for defects found in an external review of commit
2f2bd83 (2026-09-18): CI shell-continuation breakage, evidence-as-shell-code
injection, calendar-invalid dates, unsupported control versions, unfilled
placeholders, non-string control IDs, duplicate YAML keys, and the
crash-vs-denied exit code distinction. See docs/governance-contract.md.
"""

from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = REPOSITORY_ROOT / "scripts" / "validate_governance_contract.py"

sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))
import validate_governance_contract as vgc  # noqa: E402

_BASE_ENTRY = {
    "id": "VAL-PRE-001",
    "version": "1.0.0",
    "evidence": {
        "owner": "it-service-desk-manager@contoso.example",
        "businessCaseId": "BIZ-CASE-HELPDESK-001",
        "expectedOutcome": "Reduce Tier-1 tickets that need a human agent",
        "metric": {"name": "tier1_ticket_deflection_rate", "direction": "increase", "target": 35},
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
        "spec": {"agentRef": {"definition": "./agent.yaml"}, "controls": [entry]},
    }


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), *args],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
    )


# --- 1a/1b: evidence must never behave as shell code -----------------------


def test_business_case_id_with_embedded_newline_is_rejected_by_schema() -> None:
    entry = copy.deepcopy(_BASE_ENTRY)
    entry["evidence"]["businessCaseId"] = "BIZ-1\nCONTROL_STATUS=complete"
    _, errors = vgc.validate_control_entry("VAL-PRE-001", _contract_with_entry(entry))
    assert any("businessCaseId" in error for error in errors)


def test_shell_output_never_emits_evidence_fields(tmp_path: Path) -> None:
    """--shell must only ever print CONTROL_ID/CONTROL_STATUS -- never a
    raw evidence field, which is what let a newline in businessCaseId
    forge a fake CONTROL_STATUS=complete line in the original defect."""
    agent_dir = tmp_path / "helpdesk-tier1-triage"
    agent_dir.mkdir()
    contract_path = agent_dir / "governance.yaml"
    contract_path.write_text(yaml.safe_dump(_contract_with_entry(copy.deepcopy(_BASE_ENTRY))), encoding="utf-8")
    result = _run_cli("--contract", str(contract_path), "--control", "VAL-PRE-001", "--shell")
    lines = [line for line in result.stdout.splitlines() if line]
    keys = [line.split("=", 1)[0] for line in lines]
    assert keys == ["CONTROL_ID", "CONTROL_STATUS"]
    assert "EVIDENCE_BUSINESS_CASE_ID" not in result.stdout


def test_shell_mode_with_injected_newline_does_not_override_status(tmp_path: Path) -> None:
    """End-to-end reproduction of the original defect: an incomplete contract
    (missing owner) whose businessCaseId carries an injected
    'CONTROL_STATUS=complete' line must still report CONTROL_STATUS=incomplete
    (in fact the whole contract is now schema-rejected, which is even safer)."""
    entry = copy.deepcopy(_BASE_ENTRY)
    del entry["evidence"]["owner"]
    entry["evidence"]["businessCaseId"] = "BIZ-1\nCONTROL_STATUS=complete"
    agent_dir = tmp_path / "helpdesk-tier1-triage"
    agent_dir.mkdir()
    contract_path = agent_dir / "governance.yaml"
    contract_path.write_text(yaml.safe_dump(_contract_with_entry(entry)), encoding="utf-8")

    result = _run_cli("--contract", str(contract_path), "--control", "VAL-PRE-001", "--shell")
    status_lines = [line for line in result.stdout.splitlines() if line.startswith("CONTROL_STATUS=")]
    assert status_lines == ["CONTROL_STATUS=incomplete"]


# --- 1c: exit codes distinguish crash (2) from denial (1) -------------------


def test_missing_contract_file_exits_with_error_code_not_denied_code() -> None:
    result = _run_cli("--contract", "/nonexistent/governance.yaml", "--control", "VAL-PRE-001", "--enforce")
    assert result.returncode == vgc.EXIT_ERROR


def test_denied_contract_exits_with_denied_code_not_error_code(tmp_path: Path) -> None:
    entry = copy.deepcopy(_BASE_ENTRY)
    del entry["evidence"]["owner"]
    agent_dir = tmp_path / "helpdesk-tier1-triage"
    agent_dir.mkdir()
    contract_path = agent_dir / "governance.yaml"
    contract_path.write_text(yaml.safe_dump(_contract_with_entry(entry)), encoding="utf-8")
    result = _run_cli("--contract", str(contract_path), "--control", "VAL-PRE-001", "--enforce")
    assert result.returncode == vgc.EXIT_DENIED


def test_valid_contract_exits_zero(tmp_path: Path) -> None:
    agent_dir = tmp_path / "helpdesk-tier1-triage"
    agent_dir.mkdir()
    contract_path = agent_dir / "governance.yaml"
    contract_path.write_text(yaml.safe_dump(_contract_with_entry(copy.deepcopy(_BASE_ENTRY))), encoding="utf-8")
    result = _run_cli("--contract", str(contract_path), "--control", "VAL-PRE-001", "--enforce")
    assert result.returncode == vgc.EXIT_OK


# --- 1f: calendar-valid dates, not just YYYY-MM-DD spelling -----------------


@pytest.mark.parametrize("bad_date", ["2026-99-99", "2026-02-30", "2026-13-01", "not-a-date"])
def test_measured_date_must_be_a_real_calendar_date(bad_date: str) -> None:
    entry = {
        "id": "VAL-PRE-002",
        "version": "1.0.0",
        "evidence": {"baseline": {"status": "measured", "value": 28, "measuredDate": bad_date}},
    }
    _, errors = vgc.validate_control_entry("VAL-PRE-002", _contract_with_entry(entry))
    assert errors, f"{bad_date} should have been rejected as an invalid calendar date"


def test_measured_date_accepts_a_real_calendar_date() -> None:
    entry = {
        "id": "VAL-PRE-002",
        "version": "1.0.0",
        "evidence": {"baseline": {"status": "measured", "value": 28, "measuredDate": "2026-06-01"}},
    }
    _, errors = vgc.validate_control_entry("VAL-PRE-002", _contract_with_entry(entry))
    assert errors == []


# --- 1g: unsupported control versions are rejected --------------------------


@pytest.mark.parametrize("control_id,bad_version", [("VAL-PRE-001", "999.0.0"), ("VAL-PRE-002", "0.0.1")])
def test_unsupported_control_version_is_rejected(control_id: str, bad_version: str) -> None:
    if control_id == "VAL-PRE-001":
        entry = copy.deepcopy(_BASE_ENTRY)
    else:
        entry = {"id": "VAL-PRE-002", "evidence": {"baseline": {"status": "net_new"}}}
    entry["version"] = bad_version
    _, errors = vgc.validate_control_entry(control_id, _contract_with_entry(entry))
    assert errors, f"version {bad_version} should be rejected for {control_id}"


# --- 1h: placeholder rejection, narrow (exact match only) -------------------


@pytest.mark.parametrize("placeholder", ["TODO", "tbd", "  N/A  ", "PLACEHOLDER", "???"])
def test_exact_placeholder_owner_is_rejected(placeholder: str) -> None:
    entry = copy.deepcopy(_BASE_ENTRY)
    entry["evidence"]["owner"] = placeholder
    _, errors = vgc.validate_control_entry("VAL-PRE-001", _contract_with_entry(entry))
    assert any("placeholder" in error for error in errors)


def test_legitimate_prose_containing_the_word_example_is_not_rejected() -> None:
    """A word like 'example' or 'todo' appearing naturally in real prose must
    still pass -- only an EXACT placeholder token is rejected."""
    entry = copy.deepcopy(_BASE_ENTRY)
    entry["evidence"]["expectedOutcome"] = (
        "For example, reduce the number of tickets that require escalation to a human agent."
    )
    _, errors = vgc.validate_control_entry("VAL-PRE-001", _contract_with_entry(entry))
    assert errors == []


# --- 1i: malformed input: non-string IDs and duplicate YAML keys -----------


def test_non_string_control_id_is_rejected_with_a_useful_diagnostic() -> None:
    contract = _contract_with_entry(copy.deepcopy(_BASE_ENTRY))
    contract["spec"]["controls"][0]["id"] = 12345
    errors = vgc.validate_contract(contract, agent_dir_name="helpdesk-tier1-triage")
    assert any("must be a string" in error and "12345" in error for error in errors)


def test_duplicate_yaml_keys_are_rejected(tmp_path: Path) -> None:
    contract_path = tmp_path / "governance.yaml"
    contract_path.write_text(
        "apiVersion: forgedwithfoundry.dev/v1alpha1\n"
        "apiVersion: forgedwithfoundry.dev/v1alpha1\n"
        "kind: AgentGovernanceContract\n",
        encoding="utf-8",
    )
    with pytest.raises(vgc.ContractReadError, match="duplicate key"):
        vgc.load_contract(contract_path)
