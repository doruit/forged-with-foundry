#!/usr/bin/env python3
"""Shared validator for the Forged with Foundry Agent Governance Contract.

Discovers and validates `.fwf/agents/<agent-id>/governance.yaml` contract
instances against the declarative schemas in
`schemas/governance-contract/v1alpha1/`. This script is the only place that
understands contract discovery and JSON Schema validation; individual
controls call it instead of re-implementing structural checks.

This is a Forged with Foundry community pattern; Microsoft Foundry and `azd`
tooling do not discover or enforce this file, and this script never opens a
real Microsoft/vendor `agent.yaml` -- discovery only ever matches the exact
filename `governance.yaml` under `.fwf/agents/<agent-id>/`. See
docs/governance-contract.md for the full architecture.

By default this script only reports; nothing here is a deployment-time
enforcement point on its own. Pass --enforce to make it exit non-zero on an
invalid contract or control, the mode a CI check step should use.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_ROOT = REPO_ROOT / "schemas" / "governance-contract" / "v1alpha1"
CENTRAL_SCHEMA_PATH = SCHEMA_ROOT / "fwf-governance-contract.schema.json"
CONTROLS_SCHEMA_DIR = SCHEMA_ROOT / "controls"
CONTRACT_GLOB = ".fwf/agents/*/governance.yaml"


def _load_schema(path: Path) -> dict[str, Any]:
    """Load a schema file, assigning it a file:// $id so relative $refs resolve."""
    schema = json.loads(path.read_text(encoding="utf-8"))
    schema.setdefault("$id", path.resolve().as_uri())
    return schema


def _build_registry() -> Registry:
    schema_files = [CENTRAL_SCHEMA_PATH, *sorted(CONTROLS_SCHEMA_DIR.glob("*.schema.json"))]
    resources = []
    for path in schema_files:
        schema = _load_schema(path)
        resources.append((schema["$id"], Resource.from_contents(schema, default_specification=DRAFT202012)))
    return Registry().with_resources(resources)


def _control_schema_path(control_id: str) -> Path:
    return CONTROLS_SCHEMA_DIR / f"{control_id}.schema.json"


def known_control_ids() -> list[str]:
    return sorted(path.name.removesuffix(".schema.json") for path in CONTROLS_SCHEMA_DIR.glob("*.schema.json"))


def load_contract(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: contract must be a YAML mapping, not {type(data).__name__}")
    return data


def discover_contracts(root: Path) -> list[Path]:
    """Find every .fwf/agents/<agent-id>/governance.yaml under root.

    Only this exact filename under this exact path shape is ever opened; a
    real Microsoft/vendor agent.yaml sitting anywhere nearby is ignored.
    """
    return sorted(root.glob(CONTRACT_GLOB))


def _duplicate_ids(controls: list[Any]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for entry in controls:
        control_id = entry.get("id") if isinstance(entry, dict) else None
        if control_id is None:
            continue
        if control_id in seen:
            duplicates.append(control_id)
        seen.add(control_id)
    return duplicates


def validate_contract(data: dict[str, Any], *, agent_dir_name: str | None = None) -> list[str]:
    """Validate a loaded contract against the central schema plus repo-only checks.

    JSON Schema alone cannot reliably enforce "array items have unique id
    values" across drafts, and it cannot compare a value to the file path it
    was loaded from -- both checks are done here instead.
    """
    errors: list[str] = []
    registry = _build_registry()
    central_schema = _load_schema(CENTRAL_SCHEMA_PATH)
    validator = Draft202012Validator(central_schema, registry=registry)
    for error in validator.iter_errors(data):
        location = "/".join(str(part) for part in error.path) or "<root>"
        errors.append(f"{location}: {error.message}")

    spec = data.get("spec")
    controls = spec.get("controls") if isinstance(spec, dict) else None
    if isinstance(controls, list):
        for duplicate_id in _duplicate_ids(controls):
            errors.append(f"spec/controls: duplicate control id '{duplicate_id}'")

    metadata = data.get("metadata")
    agent_id = metadata.get("agentId") if isinstance(metadata, dict) else None
    if agent_dir_name is not None and isinstance(agent_id, str) and agent_id != agent_dir_name:
        errors.append(
            f"metadata/agentId: '{agent_id}' does not match the directory it was discovered under "
            f"('{agent_dir_name}') -- the .fwf/agents/<agent-id>/ directory name must equal metadata.agentId"
        )
    return errors


def validate_control_entry(control_id: str, data: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    """Return (entry, errors) for one control id's evidence inside an already-loaded contract."""
    spec = data.get("spec")
    controls = spec.get("controls") if isinstance(spec, dict) else None
    entry = None
    if isinstance(controls, list):
        entry = next((c for c in controls if isinstance(c, dict) and c.get("id") == control_id), None)
    if entry is None:
        return None, [f"control '{control_id}' is not present in this contract"]

    schema_path = _control_schema_path(control_id)
    if not schema_path.is_file():
        return entry, [f"no schema exists for control '{control_id}' -- it has not been onboarded to the FwF contract yet"]

    registry = _build_registry()
    schema = _load_schema(schema_path)
    validator = Draft202012Validator(schema, registry=registry)
    errors = []
    for error in validator.iter_errors(entry):
        location = "/".join(str(part) for part in error.path) or "<root>"
        errors.append(f"{location}: {error.message}")
    return entry, errors


def _shell_key(name: str) -> str:
    """camelCase -> UPPER_SNAKE for shell variable names."""
    result: list[str] = []
    for char in name:
        if char.isupper() and result:
            result.append("_")
        result.append(char.upper())
    return "".join(result)


def _flatten_evidence(prefix: str, value: Any, out: dict[str, str]) -> None:
    if isinstance(value, dict):
        for key, sub_value in value.items():
            _flatten_evidence(f"{prefix}_{_shell_key(key)}", sub_value, out)
    else:
        out[prefix] = "" if value is None else str(value)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--contract", type=Path, help="Validate exactly this one governance.yaml file.")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("."),
        help="Discover .fwf/agents/*/governance.yaml under this directory (ignored if --contract is given).",
    )
    parser.add_argument("--control", dest="control_id", help="Also extract and validate one control's evidence.")
    parser.add_argument(
        "--shell",
        action="store_true",
        help="Print KEY=VALUE lines for the requested --control instead of JSON. Requires --contract and --control.",
    )
    parser.add_argument(
        "--enforce",
        action="store_true",
        help="Exit non-zero when any discovered contract, or the requested --control, is invalid.",
    )
    args = parser.parse_args()

    if args.shell and (args.contract is None or args.control_id is None):
        parser.error("--shell requires both --contract and --control")

    contracts = [args.contract] if args.contract is not None else discover_contracts(args.root)
    if not contracts:
        print(json.dumps({"error": "no governance.yaml contracts found", "root": str(args.root)}))
        return 1 if args.enforce else 0

    any_invalid = False
    single_control_result: dict[str, Any] | None = None

    for contract_path in contracts:
        if not contract_path.is_file():
            print(json.dumps({"contract": str(contract_path), "valid": False, "errors": ["file not found"]}))
            any_invalid = True
            continue
        try:
            data = load_contract(contract_path)
        except (yaml.YAMLError, ValueError) as exc:
            print(json.dumps({"contract": str(contract_path), "valid": False, "errors": [str(exc)]}))
            any_invalid = True
            continue

        envelope_errors = validate_contract(data, agent_dir_name=contract_path.parent.name)
        valid = not envelope_errors
        any_invalid = any_invalid or not valid
        result: dict[str, Any] = {"contract": str(contract_path), "valid": valid, "errors": envelope_errors}

        if args.control_id:
            entry, entry_errors = validate_control_entry(args.control_id, data)
            status = "complete" if (valid and entry is not None and not entry_errors) else "incomplete"
            result["control"] = {"id": args.control_id, "status": status, "errors": entry_errors}
            any_invalid = any_invalid or status != "complete"
            if len(contracts) == 1:
                single_control_result = {"status": status, "entry": entry}

        if not args.shell:
            print(json.dumps(result))

    if args.shell and single_control_result is not None:
        print(f"CONTROL_ID={args.control_id}")
        print(f"CONTROL_STATUS={single_control_result['status']}")
        entry = single_control_result["entry"]
        if entry is not None:
            flat: dict[str, str] = {}
            _flatten_evidence("EVIDENCE", entry.get("evidence", {}), flat)
            for key, value in flat.items():
                print(f"{key}={value}")

    return 1 if (args.enforce and any_invalid) else 0


if __name__ == "__main__":
    raise SystemExit(main())
