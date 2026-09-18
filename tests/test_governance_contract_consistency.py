"""Repo-wide consistency checks for the Forged with Foundry Agent Governance
Contract architecture: every implemented control's schema is wired into the
central schema correctly, and the shared validator fails closed on malformed,
duplicate, unknown, or forged input. See docs/governance-contract.md.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CONTROLS_ROOT = REPOSITORY_ROOT / "controls"
SCHEMA_ROOT = REPOSITORY_ROOT / "schemas" / "governance-contract" / "v1alpha1"
CENTRAL_SCHEMA_PATH = SCHEMA_ROOT / "fwf-governance-contract.schema.json"
CONTROLS_SCHEMA_DIR = SCHEMA_ROOT / "controls"

sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))
import validate_governance_contract as vgc  # noqa: E402

VALID_HELPDESK_CONTRACT = {
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
        "controls": [
            {
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
        ],
    },
}


def _control_schema_files() -> list[Path]:
    return sorted(CONTROLS_SCHEMA_DIR.glob("*.schema.json"))


def _central_schema_ref_ids() -> list[str]:
    central = json.loads(CENTRAL_SCHEMA_PATH.read_text(encoding="utf-8"))
    one_of = central["properties"]["spec"]["properties"]["controls"]["items"]["oneOf"]
    return [Path(entry["$ref"]).stem.removesuffix(".schema") for entry in one_of]


def test_every_control_schema_has_a_matching_implemented_control_folder() -> None:
    for schema_path in _control_schema_files():
        control_id = schema_path.name.removesuffix(".schema.json")
        matches = list(CONTROLS_ROOT.glob(f"*/{control_id}_*"))
        assert matches, f"no controls/*/{control_id}_*/ folder for schema {schema_path.name}"


def test_every_control_schema_enforces_its_own_id_via_const() -> None:
    for schema_path in _control_schema_files():
        control_id = schema_path.name.removesuffix(".schema.json")
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        assert schema["properties"]["id"]["const"] == control_id


def test_central_schema_references_every_control_schema() -> None:
    referenced_ids = set(_central_schema_ref_ids())
    actual_ids = {path.name.removesuffix(".schema.json") for path in _control_schema_files()}
    assert referenced_ids == actual_ids


def test_valid_example_contract_validates_with_zero_errors() -> None:
    errors = vgc.validate_contract(VALID_HELPDESK_CONTRACT, agent_dir_name="helpdesk-tier1-triage")
    assert errors == []


def test_duplicate_control_ids_are_rejected() -> None:
    contract = json.loads(json.dumps(VALID_HELPDESK_CONTRACT))  # deep copy
    contract["spec"]["controls"].append(contract["spec"]["controls"][0])
    errors = vgc.validate_contract(contract, agent_dir_name="helpdesk-tier1-triage")
    assert any("duplicate control id" in error for error in errors)


def test_unknown_control_id_fails_closed() -> None:
    contract = json.loads(json.dumps(VALID_HELPDESK_CONTRACT))
    contract["spec"]["controls"][0]["id"] = "VAL-PRE-999"
    errors = vgc.validate_contract(contract, agent_dir_name="helpdesk-tier1-triage")
    assert errors, "an unknown control id must fail schema validation, not silently pass"


def test_agent_id_must_match_discovery_directory() -> None:
    errors = vgc.validate_contract(VALID_HELPDESK_CONTRACT, agent_dir_name="some-other-agent")
    assert any("metadata/agentId" in error for error in errors)


def test_missing_required_top_level_keys_fail_closed() -> None:
    for missing_key in ("apiVersion", "kind", "metadata", "spec"):
        contract = json.loads(json.dumps(VALID_HELPDESK_CONTRACT))
        del contract[missing_key]
        errors = vgc.validate_contract(contract, agent_dir_name="helpdesk-tier1-triage")
        assert errors, f"missing {missing_key} must fail validation"


def test_wrong_api_version_and_kind_fail_closed() -> None:
    for key, bad_value in (("apiVersion", "forgedwithfoundry.dev/v2"), ("kind", "SomethingElse")):
        contract = json.loads(json.dumps(VALID_HELPDESK_CONTRACT))
        contract[key] = bad_value
        errors = vgc.validate_contract(contract, agent_dir_name="helpdesk-tier1-triage")
        assert errors, f"wrong {key} must fail validation"


def test_non_mapping_contract_is_rejected_by_load_contract(tmp_path: Path) -> None:
    contract_path = tmp_path / "governance.yaml"
    contract_path.write_text("- just\n- a\n- list\n", encoding="utf-8")
    try:
        vgc.load_contract(contract_path)
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_discovery_only_matches_governance_yaml_and_ignores_agent_yaml(tmp_path: Path) -> None:
    agent_dir = tmp_path / ".fwf" / "agents" / "helpdesk-tier1-triage"
    agent_dir.mkdir(parents=True)
    (agent_dir / "governance.yaml").write_text(
        json.dumps(VALID_HELPDESK_CONTRACT), encoding="utf-8"
    )
    # A real-shaped Microsoft/vendor manifest sitting right next to it must never be opened.
    (agent_dir / "agent.yaml").write_text(
        "kind: hosted\nname: unrelated-foundry-hosted-agent\nprotocols:\n  - protocol: responses\n",
        encoding="utf-8",
    )

    discovered = vgc.discover_contracts(tmp_path)

    assert discovered == [agent_dir / "governance.yaml"]


def test_control_entry_extraction_reports_incomplete_when_a_required_field_is_missing() -> None:
    contract = json.loads(json.dumps(VALID_HELPDESK_CONTRACT))
    del contract["spec"]["controls"][0]["evidence"]["owner"]
    entry, errors = vgc.validate_control_entry("VAL-PRE-001", contract)
    assert entry is not None
    assert errors, "removing a required evidence field must produce validation errors"
