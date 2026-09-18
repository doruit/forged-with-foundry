#!/usr/bin/env python3
"""Builds the deployment-plan JSON that policy/governance-contract/deployment_gate.rego
evaluates. This is the small, explicit "trusted pipeline" step: it decides which agents
are expected to be deployed and which controls are mandatory for them, from a
deployment manifest supplied by the pipeline -- never from a workload's own
governance.yaml, which must not get a vote in what is mandatory for it.

A glob of existing governance.yaml files alone cannot prove every deployable agent is
covered: an agent folder with no contract, or no folder at all, is invisible to a plain
glob. This script discovers every `.fwf/agents/<agent-id>/` folder (whether or not it
has a governance.yaml) and reports on each one explicitly, so the policy layer can
distinguish "not discovered at all" from "folder exists but has no contract" from
"contract exists but is invalid" from "contract is valid but missing a required
control". See docs/governance-contract.md#policy-layer.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml
from validate_governance_contract import ContractReadError, load_contract, validate_contract, validate_control_entry


def discover_agent_folders(root: Path) -> list[Path]:
    agents_root = root / ".fwf" / "agents"
    if not agents_root.is_dir():
        return []
    return sorted(path for path in agents_root.iterdir() if path.is_dir())


def _assess_agent(agent_dir: Path) -> dict[str, Any]:
    agent_id = agent_dir.name
    contract_path = agent_dir / "governance.yaml"
    entry: dict[str, Any] = {
        "agentId": agent_id,
        "contractPath": str(contract_path),
        "hasContract": contract_path.is_file(),
    }
    if not entry["hasContract"]:
        return entry

    try:
        data = load_contract(contract_path)
    except ContractReadError as exc:
        entry["valid"] = False
        entry["errors"] = [str(exc)]
        entry["controlStatuses"] = {}
        return entry

    errors = validate_contract(data, agent_dir_name=agent_id)
    entry["valid"] = not errors
    entry["errors"] = errors

    control_statuses: dict[str, str] = {}
    spec = data.get("spec") or {}
    for control in spec.get("controls") or []:
        if isinstance(control, dict) and isinstance(control.get("id"), str):
            _, control_errors = validate_control_entry(control["id"], data)
            control_statuses[control["id"]] = "complete" if (entry["valid"] and not control_errors) else "incomplete"
    entry["controlStatuses"] = control_statuses
    return entry


def build_plan(manifest: dict[str, Any], profile: str, root: Path) -> dict[str, Any]:
    profiles = manifest.get("profiles") or {}
    if profile not in profiles:
        raise SystemExit(f"error: profile '{profile}' is not defined in the manifest (known: {sorted(profiles)})")

    discovered = [_assess_agent(agent_dir) for agent_dir in discover_agent_folders(root)]
    return {
        "policyProfile": profile,
        "requiredControls": profiles[profile].get("requiredControls", []),
        "expectedAgents": manifest.get("expectedAgents", []),
        "discoveredAgents": discovered,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", required=True, type=Path, help="Deployment manifest YAML (profiles + expectedAgents).")
    parser.add_argument("--profile", required=True, help="Which manifest profile's requiredControls to apply.")
    parser.add_argument("--root", type=Path, default=Path("."), help="Workload repository root to discover .fwf/agents/ under.")
    args = parser.parse_args()

    manifest = yaml.safe_load(args.manifest.read_text(encoding="utf-8"))
    plan = build_plan(manifest, args.profile, args.root)
    print(json.dumps(plan, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
