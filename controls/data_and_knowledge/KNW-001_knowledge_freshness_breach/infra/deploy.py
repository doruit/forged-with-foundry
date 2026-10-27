"""Validate, deploy, inspect, or clean up the KNW-001 Blob/Search foundation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".azure" / "foundation.json"
GROUP = "rg-knw001-demo"
LOCATION = "westeurope"
DEPLOYMENT = "knw001-demo"
PURPOSE = "synthetic-knowledge-freshness-demo"


def azure(*arguments: str):
    result = subprocess.run(
        ["az", *arguments, "--only-show-errors", "-o", "json"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Azure CLI command failed.")
    return json.loads(result.stdout) if result.stdout.strip() else None


def owned(resource: dict) -> bool:
    tags = resource.get("tags") or {}
    return tags.get("control-id") == "KNW-001" and tags.get("purpose") == PURPOSE


def check_context(tenant_id: str, subscription_id: str) -> dict:
    account = azure("account", "show")
    if account["tenantId"] != tenant_id or account["id"] != subscription_id:
        raise ValueError("Azure context mismatch. Select the intended tenant/subscription first.")
    if azure("group", "exists", "--name", GROUP):
        if not owned(azure("group", "show", "--name", GROUP)):
            raise ValueError("Existing resource group is not marked as KNW-001-owned.")
    return account


def deployment_arguments(setup_principal_id: str) -> list[str]:
    return [
        "--name", DEPLOYMENT, "--location", LOCATION,
        "--template-file", str(ROOT / "infra/main.bicep"),
        "--parameters", f"setupPrincipalId={setup_principal_id}",
    ]


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=STATE.parent, delete=False) as handle:
        json.dump(state, handle, indent=2)
        temporary = Path(handle.name)
    temporary.chmod(0o600)
    temporary.replace(STATE)


def cleanup_targets(state: dict, subscription_id: str) -> list[str]:
    if state.get("control_id") != "KNW-001" or state.get("subscription_id") != subscription_id:
        raise ValueError("Foundation state belongs to another control or subscription.")
    if state.get("phase") != "deployed":
        raise ValueError("Deployment is incomplete; inspect ARM deployment operations before cleanup.")
    outputs = state["outputs"]
    prefix = f"/subscriptions/{subscription_id}/resourceGroups/{GROUP}/providers/"
    targets = [outputs["searchId"], outputs["storageId"]]
    expected_types = ["Microsoft.Search/searchServices", "Microsoft.Storage/storageAccounts"]
    for target, resource_type in zip(targets, expected_types, strict=True):
        if not target.lower().startswith(f"{prefix}{resource_type}/".lower()):
            raise ValueError("Cleanup target is outside the expected control resource scope.")
        if len(target.split("/")) != 9:
            raise ValueError("Cleanup target is not a top-level control resource.")
    if len(set(targets)) != 2:
        raise ValueError("Cleanup targets are duplicated.")
    return targets


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["validate", "deploy", "inspect", "cleanup-plan", "cleanup"])
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--subscription-id", required=True)
    parser.add_argument("--approve-delete", action="store_true", help="Separate approval to delete the two control-owned resources.")
    args = parser.parse_args()
    check_context(args.tenant_id, args.subscription_id)
    if args.action in {"validate", "deploy"}:
        setup = azure("ad", "signed-in-user", "show")["id"]
        parameters = deployment_arguments(setup)
        azure("bicep", "build", "--file", str(ROOT / "infra/main.bicep"), "--stdout")
        validation = azure("deployment", "sub", "validate", *parameters)
        if validation["properties"]["provisioningState"] != "Succeeded":
            raise RuntimeError("ARM validation did not succeed; stop.")
        print("ARM validation: Succeeded (Free Search, LRS storage, West Europe).")
        if args.action == "validate":
            return
        state = {
            "control_id": "KNW-001", "tenant_id": args.tenant_id,
            "subscription_id": args.subscription_id, "phase": "deploying",
        }
        save_state(state)
        result = azure("deployment", "sub", "create", *parameters)
        if result["properties"]["provisioningState"] != "Succeeded":
            raise RuntimeError("ARM deployment did not succeed; inspect its operations.")
        outputs = result["properties"]["outputs"]["resources"]["value"]
        state["outputs"] = {key: item["value"] for key, item in outputs.items()}
        state["phase"] = "deployed"
        save_state(state)
        print("Foundation deployed. No monitor, review endpoint, indexer, or Teams sender is deployed.")
    elif args.action == "inspect":
        resources = azure("resource", "list", "--resource-group", GROUP)
        print(json.dumps([
            {"name": item["name"], "type": item["type"], "owned": owned(item)}
            for item in resources
        ], indent=2))
    else:
        state = json.loads(STATE.read_text())
        if state.get("tenant_id") != args.tenant_id:
            raise ValueError("Foundation state belongs to another tenant.")
        targets = cleanup_targets(state, args.subscription_id)
        for target in targets:
            if not owned(azure("resource", "show", "--ids", target)):
                raise ValueError("Cleanup target ownership tags do not match; stop.")
        print("Deletes only the KNW-001 Search service and Storage Account (including all their data/scoped grants).")
        print("Keeps the resource group, deployment history, and subscription policy.")
        if args.action == "cleanup":
            if not args.approve_delete:
                raise ValueError("Deletion requires separate --approve-delete authorization.")
            for target in targets:
                azure("resource", "delete", "--ids", target)
            remaining = azure("resource", "list", "--resource-group", GROUP)
            if any(item["id"].lower() in {target.lower() for target in targets} for item in remaining):
                raise RuntimeError("A cleanup target remains; inspect before retrying.")
            state["phase"] = "cleaned"
            save_state(state)
            print("Control resources removed; subscription policy left unchanged.")


if __name__ == "__main__":
    main()