"""Validate, deploy, inspect, or clean up the KNW-001 Blob/Search foundation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".azure" / "foundation.json"
PENDING_STATE = ROOT / ".azure" / "foundation.pending.json"
RUNTIME_STATE = ROOT / ".azure" / "runtime.json"
RUNTIME_TYPES = {"microsoft.web/sites", "microsoft.web/serverfarms", "microsoft.cognitiveservices/accounts"}
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


def deployment_arguments(setup_principal_id: str, search_sku: str = "free", search_location: str = LOCATION) -> list[str]:
    template_sku = "standard" if search_sku == "s1" else "free"
    return [
        "--name", DEPLOYMENT, "--location", LOCATION,
        "--template-file", str(ROOT / "infra/main.bicep"),
        "--parameters", f"setupPrincipalId={setup_principal_id}", f"searchSku={template_sku}",
        f"searchLocation={search_location}",
    ]


def save_state(state: dict, path: Path = STATE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as handle:
        json.dump(state, handle, indent=2)
        temporary = Path(handle.name)
    temporary.chmod(0o600)
    temporary.replace(path)


def cleanup_targets(state: dict, subscription_id: str) -> list[str]:
    if state.get("control_id") != "KNW-001" or state.get("subscription_id") != subscription_id:
        raise ValueError("Foundation state belongs to another control or subscription.")
    phase = state.get("phase")
    if phase not in {"deployed", "storage_only", "search_only"}:
        raise ValueError("Deployment is incomplete; inspect ARM deployment operations before cleanup.")
    outputs = state["outputs"]
    prefix = f"/subscriptions/{subscription_id}/resourceGroups/{GROUP}/providers/"
    if phase == "storage_only":
        targets = [outputs["storageId"]]
        expected_types = ["Microsoft.Storage/storageAccounts"]
    elif phase == "search_only":
        targets = [outputs["searchId"]]
        expected_types = ["Microsoft.Search/searchServices"]
    else:
        targets = [outputs["searchId"], outputs["storageId"]]
        expected_types = ["Microsoft.Search/searchServices", "Microsoft.Storage/storageAccounts"]
    for target, resource_type in zip(targets, expected_types, strict=True):
        if not target.lower().startswith(f"{prefix}{resource_type}/".lower()):
            raise ValueError("Cleanup target is outside the expected control resource scope.")
        if len(target.split("/")) != 9:
            raise ValueError("Cleanup target is not a top-level control resource.")
    if len(set(targets)) != len(targets):
        raise ValueError("Cleanup targets are duplicated.")
    return targets


def runtime_present(resources: list[dict], runtime_state: dict) -> bool:
    """True while runtime.py-owned resources or an uncleaned runtime state remain."""
    if runtime_state and runtime_state.get("phase") != "cleaned":
        return True
    return any(owned(item) and str(item.get("type", "")).lower() in RUNTIME_TYPES for item in resources)


def state_from_resources(resources: list[dict], tenant_id: str, subscription_id: str) -> dict:
    output_keys = {
        "Microsoft.Search/searchServices": "searchId",
        "Microsoft.Storage/storageAccounts": "storageId",
    }
    outputs = {}
    for resource in resources:
        if not owned(resource) or str(resource.get("type", "")).lower() in RUNTIME_TYPES:
            continue
        resource_type = resource.get("type")
        key = output_keys.get(resource_type)
        if key is None:
            raise ValueError("Unexpected KNW-001-owned resource type; inspect before reconciling.")
        if key in outputs:
            raise ValueError("Multiple KNW-001 resources of the same type; inspect before reconciling.")
        outputs[key] = resource["id"]

    present = set(outputs)
    phase = (
        "deployed" if present == {"searchId", "storageId"}
        else "search_only" if present == {"searchId"}
        else "storage_only" if present == {"storageId"}
        else "empty"
    )
    return {
        "control_id": "KNW-001",
        "tenant_id": tenant_id,
        "subscription_id": subscription_id,
        "phase": phase,
        "outputs": outputs,
    }


def search_cleanup_target(state: dict, subscription_id: str) -> str:
    if state.get("control_id") != "KNW-001" or state.get("subscription_id") != subscription_id:
        raise ValueError("Foundation state belongs to another control or subscription.")
    if state.get("phase") != "deployed":
        raise ValueError("A deployed Search service is not recorded for cleanup.")
    target = state["outputs"]["searchId"]
    prefix = f"/subscriptions/{subscription_id}/resourceGroups/{GROUP}/providers/Microsoft.Search/searchServices/"
    if not target.lower().startswith(prefix.lower()) or len(target.split("/")) != 9:
        raise ValueError("Search cleanup target is outside the expected control resource scope.")
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=["validate", "deploy", "inspect", "reconcile", "cleanup-plan", "cleanup", "search-cleanup-plan", "search-cleanup"],
    )
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--subscription-id", required=True)
    parser.add_argument("--search-location", choices=["westeurope", "swedencentral"], default=LOCATION)
    parser.add_argument(
        "--search-sku",
        choices=["free", "s1"],
        default="free",
        help="Search tier (S1 is billable and requires explicit temporary use).",
    )
    parser.add_argument("--approve-delete", action="store_true", help="Separate approval to delete the two control-owned resources.")
    parser.add_argument("--approve-delete-search", action="store_true", help="Separate approval to delete only the KNW-001 Search service.")
    args = parser.parse_args()
    check_context(args.tenant_id, args.subscription_id)
    if args.action == "reconcile":
        deployment = azure("deployment", "sub", "show", "--name", DEPLOYMENT)
        if deployment["properties"].get("provisioningState") == "Running":
            raise ValueError("The ARM deployment is still running; reconcile after it reaches a terminal state.")
        resources = azure("resource", "list", "--resource-group", GROUP)
        state = state_from_resources(resources, args.tenant_id, args.subscription_id)
        save_state(state)
        PENDING_STATE.unlink(missing_ok=True)
        print(f"Foundation state reconciled from ownership tags; phase={state['phase']}.")
        return
    if args.action in {"validate", "deploy"}:
        setup = azure("ad", "signed-in-user", "show")["id"]
        parameters = deployment_arguments(setup, args.search_sku, args.search_location)
        azure("bicep", "build", "--file", str(ROOT / "infra/main.bicep"), "--stdout")
        validation = azure("deployment", "sub", "validate", *parameters)
        if validation["properties"]["provisioningState"] != "Succeeded":
            raise RuntimeError("ARM validation did not succeed; stop.")
        print(f"ARM validation: Succeeded ({args.search_sku.upper()} Search in {args.search_location}; LRS storage in {LOCATION}).")
        if args.action == "validate":
            return
        state = {
            "control_id": "KNW-001", "tenant_id": args.tenant_id,
            "subscription_id": args.subscription_id, "phase": "deploying",
        }
        save_state(state, PENDING_STATE)
        try:
            result = azure("deployment", "sub", "create", *parameters)
            if result["properties"]["provisioningState"] != "Succeeded":
                raise RuntimeError("ARM deployment did not succeed; inspect its operations.")
        except Exception as error:
            state["phase"] = "failed"
            state["failure_type"] = type(error).__name__
            save_state(state, PENDING_STATE)
            raise
        outputs = result["properties"]["outputs"]["resources"]["value"]
        state["outputs"] = {key: item["value"] for key, item in outputs.items()}
        state["phase"] = "deployed"
        save_state(state)
        PENDING_STATE.unlink(missing_ok=True)
        print(f"Foundation deployed with {args.search_sku.upper()} Search. No monitor, review endpoint, indexer, or notification sink is deployed.")
    elif args.action == "inspect":
        resources = azure("resource", "list", "--resource-group", GROUP)
        print(json.dumps([
            {"name": item["name"], "type": item["type"], "owned": owned(item)}
            for item in resources
        ], indent=2))
    elif args.action in {"search-cleanup-plan", "search-cleanup"}:
        if runtime_present(azure("resource", "list", "--resource-group", GROUP),
                           json.loads(RUNTIME_STATE.read_text()) if RUNTIME_STATE.exists() else {}):
            raise ValueError("KNW-001 runtime resources remain; run infra/runtime.py cleanup first.")
        if PENDING_STATE.exists():
            raise ValueError("An incomplete deployment attempt exists; inspect ARM operations before cleanup.")
        state = json.loads(STATE.read_text())
        if state.get("tenant_id") != args.tenant_id:
            raise ValueError("Foundation state belongs to another tenant.")
        target = search_cleanup_target(state, args.subscription_id)
        if not owned(azure("resource", "show", "--ids", target)):
            raise ValueError("Search cleanup target ownership tags do not match; stop.")
        print("Deletes only the KNW-001 Search service; the Storage account and its data are retained.")
        if args.action == "search-cleanup":
            if not args.approve_delete_search:
                raise ValueError("Search deletion requires separate --approve-delete-search authorization.")
            azure("resource", "delete", "--ids", target)
            remaining = azure("resource", "list", "--resource-group", GROUP)
            if any(item["id"].lower() == target.lower() for item in remaining):
                raise RuntimeError("The Search cleanup target remains; inspect before retrying.")
            state["outputs"].pop("searchId", None)
            state["phase"] = "storage_only"
            save_state(state)
            print("KNW-001 Search service removed; Storage retained.")
    else:
        if runtime_present(azure("resource", "list", "--resource-group", GROUP),
                           json.loads(RUNTIME_STATE.read_text()) if RUNTIME_STATE.exists() else {}):
            raise ValueError("KNW-001 runtime resources remain; run infra/runtime.py cleanup first.")
        if PENDING_STATE.exists():
            raise ValueError("An incomplete deployment attempt exists; inspect ARM operations before cleanup.")
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