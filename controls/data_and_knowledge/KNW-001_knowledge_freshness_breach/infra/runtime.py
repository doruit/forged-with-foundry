"""Deploy, operate, inspect, or clean up the KNW-001 runtime layer.

The runtime layer is a Flex Consumption Function App (scheduled monitor, owner
review route, authenticated notification inbox) and a control-owned Foundry
account/project/model/Search connection. It requires the foundation from
deploy.py and must be cleaned up before the foundation.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
from uuid import NAMESPACE_URL, uuid5
import zipfile

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("knw001_foundation", ROOT / "infra/deploy.py")
foundation = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(foundation)

RUNTIME_STATE = ROOT / ".azure" / "runtime.json"
DEPLOYMENT = "knw001-runtime"
GRAPH = "https://graph.microsoft.com/v1.0"
AZURE_CLI_APP_ID = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"
SCOPE_ID = str(uuid5(NAMESPACE_URL, "forgedwithfoundry:KNW-001:user_impersonation"))
PACKAGE_FILES = ("function_app.py", "host.json", "requirements.txt")
RUNTIME_TYPES = {
    "microsoft.web/sites": "functionAppId",
    "microsoft.web/serverfarms": "planId",
    "microsoft.cognitiveservices/accounts": "foundryId",
}
azure = foundation.azure
owned = foundation.owned


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def foundation_state(tenant_id: str, subscription_id: str) -> dict:
    state = load_json(foundation.STATE)
    if (
        state.get("control_id") != "KNW-001"
        or state.get("tenant_id") != tenant_id
        or state.get("subscription_id") != subscription_id
        or state.get("phase") != "deployed"
    ):
        raise ValueError("Deploy the KNW-001 foundation (Storage and Search) first.")
    return state


def application_marker(function_app_id: str) -> str:
    return f"Forged with Foundry KNW-001; resource={function_app_id}"


def carried_state(state: dict) -> dict:
    """Runtime state a new deployment may reuse; nothing survives a completed cleanup."""
    return {} if state.get("phase") == "cleaned" else state


def api_settings() -> dict:
    return {
        "requestedAccessTokenVersion": 2,
        "oauth2PermissionScopes": [{
            "id": SCOPE_ID, "value": "user_impersonation", "type": "User", "isEnabled": True,
            "adminConsentDisplayName": "Submit KNW-001 owner review",
            "adminConsentDescription": "Submit a KNW-001 synthetic owner review.",
            "userConsentDisplayName": "Submit KNW-001 owner review",
            "userConsentDescription": "Submit a KNW-001 synthetic owner review.",
        }],
    }


def auth_settings(state: dict) -> dict:
    client_id = state["application_client_id"]
    return {"properties": {
        "platform": {"enabled": True, "runtimeVersion": "~1"},
        "globalValidation": {
            "requireAuthentication": True,
            "unauthenticatedClientAction": "Return401",
            "excludedPaths": ["/admin/functions/freshness_timer"],
        },
        "httpSettings": {"requireHttps": True},
        "identityProviders": {"azureActiveDirectory": {
            "enabled": True,
            "registration": {
                "openIdIssuer": f"https://login.microsoftonline.com/{state['tenant_id']}/v2.0",
                "clientId": client_id,
            },
            "validation": {
                "allowedAudiences": [client_id, f"api://{client_id}"],
                "defaultAuthorizationPolicy": {"allowedPrincipals": {"identities": [
                    state["owner_object_id"], state["functionPrincipalId"],
                ]}},
            },
        }},
    }}


def cleanup_targets(state: dict, subscription_id: str) -> list[str]:
    if state.get("control_id") != "KNW-001" or state.get("subscription_id") != subscription_id:
        raise ValueError("Runtime state belongs to another control or subscription.")
    if state.get("phase") not in {"deployed", "configured"}:
        raise ValueError("No deployed KNW-001 runtime is recorded for cleanup.")
    prefix = f"/subscriptions/{subscription_id}/resourceGroups/{foundation.GROUP}/providers/".lower()
    targets = [state["functionAppId"], state["planId"], state["foundryId"]]
    for target, resource_type in zip(targets, RUNTIME_TYPES, strict=True):
        if not target.lower().startswith(f"{prefix}{resource_type}/") or len(target.split("/")) != 9:
            raise ValueError("Runtime cleanup target is outside the expected control resource scope.")
    return targets


def build_package(destination: Path) -> Path:
    archive = destination / "knw001-function.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as package:
        for name in PACKAGE_FILES:
            package.write(ROOT / name, name)
        for path in sorted((ROOT / "src/knw001").glob("*.py")):
            package.write(path, f"src/knw001/{path.name}")
    return archive


def rest(method: str, url: str, body: dict | None = None):
    arguments = ["rest", "--method", method, "--url", url]
    if body is not None:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(body, handle)
        arguments += ["--body", f"@{handle.name}", "--headers", "Content-Type=application/json"]
    try:
        return azure(*arguments)
    finally:
        if body is not None:
            Path(handle.name).unlink(missing_ok=True)


def configure_entra(state: dict) -> None:
    marker = application_marker(state["functionAppId"])
    if not state.get("application_object_id"):
        application = rest("POST", f"{GRAPH}/applications", {
            "displayName": f"{state['functionAppName']}-api",
            "signInAudience": "AzureADMyOrg", "notes": marker, "api": api_settings(),
        })
        state.update(application_object_id=application["id"], application_client_id=application["appId"])
        foundation.save_state(state, RUNTIME_STATE)
    application_url = f"{GRAPH}/applications/{state['application_object_id']}"
    application = rest("GET", application_url)
    if application.get("notes") != marker or application["appId"] != state["application_client_id"]:
        raise ValueError("Entra application ownership mismatch; stop.")
    rest("PATCH", application_url, {"identifierUris": [f"api://{state['application_client_id']}"]})
    rest("PATCH", application_url, {"api": {
        **api_settings(),
        "preAuthorizedApplications": [{"appId": AZURE_CLI_APP_ID, "delegatedPermissionIds": [SCOPE_ID]}],
    }})
    if not state.get("service_principal_id"):
        principal = rest("POST", f"{GRAPH}/servicePrincipals", {
            "appId": state["application_client_id"], "tags": ["ForgedWithFoundry", "KNW-001"],
        })
        state["service_principal_id"] = principal["id"]
        foundation.save_state(state, RUNTIME_STATE)
    rest("PUT", f"https://management.azure.com{state['functionAppId']}/config/authsettingsV2?api-version=2024-04-01", auth_settings(state))
    azure(
        "functionapp", "config", "appsettings", "set",
        "--resource-group", foundation.GROUP, "--name", state["functionAppName"], "--settings",
        "KNW001_EASY_AUTH_CONFIGURED=true",
        f"KNW001_NOTIFIER_OBJECT_ID={state['functionPrincipalId']}",
        f"KNW001_NOTIFICATION_ENDPOINT={state['functionAppUrl']}/api/notifications",
        f"KNW001_NOTIFICATION_AUDIENCE=api://{state['application_client_id']}/.default",
    )
    state["phase"] = "configured"
    foundation.save_state(state, RUNTIME_STATE)


def blob_service():
    from azure.identity import AzureCliCredential
    from azure.storage.blob import BlobServiceClient

    return BlobServiceClient(load_json(foundation.STATE)["outputs"]["blobEndpoint"], credential=AzureCliCredential())


def environment(base: dict, state: dict) -> dict[str, str]:
    """Non-secret names/endpoints consumed by setup_indexer.py, foundry_probe.py and az commands."""
    return {
        "KNW001_STORAGE_ACCOUNT": base["storageName"],
        "KNW001_BLOB_ENDPOINT": base["blobEndpoint"],
        "KNW001_SEARCH_ENDPOINT": base["searchEndpoint"],
        "KNW001_SOURCE_CONTAINER": "source",
        "KNW001_SOURCE_BLOB": state["sourceBlob"],
        "KNW001_EVIDENCE_CONTAINER": "evidence",
        "KNW001_SEARCH_INDEX": state["searchIndex"],
        "KNW001_SEARCH_INDEXER": state["searchIndexer"],
        "KNW001_SEARCH_DATASOURCE": "knw001-blob",
        "KNW001_FOUNDRY_PROJECT_ENDPOINT": state["projectEndpoint"],
        "KNW001_FOUNDRY_MODEL": state["modelDeploymentName"],
        "KNW001_FOUNDRY_SEARCH_CONNECTION": state["searchConnectionName"],
        "KNW001_POLICY_VERSION": state["policyVersion"],
        "KNW001_FUNCTION_URL": state["functionAppUrl"],
        "KNW001_REVIEW_SCOPE": f"api://{state['application_client_id']}/user_impersonation",
    }


def access_token(scope: str) -> str:
    result = subprocess.run(
        ["az", "account", "get-access-token", "--scope", scope, "--query", "accessToken", "-o", "tsv"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode:
        raise RuntimeError("Could not obtain an Entra access token for the review API.")
    return result.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=[
        "validate", "deploy", "configure", "publish", "env", "run-monitor", "review", "evidence",
        "inspect", "cleanup-plan", "cleanup",
    ])
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--subscription-id", required=True)
    parser.add_argument("--confirm-reviewed", action="store_true", help="Owner confirms the displayed revision was reviewed.")
    parser.add_argument("--correlation-id", help="Evidence run to print (default: latest run).")
    parser.add_argument("--approve-delete", action="store_true", help="Separate approval to delete the runtime layer.")
    args = parser.parse_args()
    foundation.check_context(args.tenant_id, args.subscription_id)
    base = foundation_state(args.tenant_id, args.subscription_id) if args.action in {"validate", "deploy"} else None
    state = load_json(RUNTIME_STATE)

    if args.action in {"validate", "deploy"}:
        user = azure("ad", "signed-in-user", "show")["id"]
        outputs = base["outputs"]
        parameters = [
            "--resource-group", foundation.GROUP, "--name", DEPLOYMENT,
            "--template-file", str(ROOT / "infra/runtime.bicep"), "--parameters",
            f"storageName={outputs['storageName']}", f"searchName={outputs['searchName']}",
            f"setupPrincipalId={user}", f"ownerObjectId={user}",
        ]
        validation = azure("deployment", "group", "validate", *parameters)
        if validation["properties"]["provisioningState"] != "Succeeded":
            raise RuntimeError("ARM validation did not succeed; stop.")
        print("ARM validation: Succeeded (Flex Function App, Foundry account/project/model/Search connection).")
        if args.action == "validate":
            return
        result = azure("deployment", "group", "create", *parameters)
        if result["properties"]["provisioningState"] != "Succeeded":
            raise RuntimeError("ARM deployment did not succeed; inspect its operations.")
        state = {
            **carried_state(state), "control_id": "KNW-001", "tenant_id": args.tenant_id,
            "subscription_id": args.subscription_id, "owner_object_id": user, "phase": "deployed",
            **{key: item["value"] for key, item in result["properties"]["outputs"].items()},
        }
        foundation.save_state(state, RUNTIME_STATE)
        configure_entra(state)
        print("Runtime deployed; Easy Auth, owner review API and notification inbox configured. Run 'publish' next.")
    elif args.action == "configure":
        if state.get("phase") not in {"deployed", "configured"}:
            raise ValueError("Deploy the runtime first.")
        configure_entra(state)
        print("Easy Auth, owner review API and notification inbox configured.")
    elif args.action == "publish":
        with tempfile.TemporaryDirectory() as directory:
            archive = build_package(Path(directory))
            azure(
                "functionapp", "deployment", "source", "config-zip", "--resource-group", foundation.GROUP,
                "--name", state["functionAppName"], "--src", str(archive), "--build-remote", "true",
            )
        functions = azure("functionapp", "function", "list", "--resource-group", foundation.GROUP, "--name", state["functionAppName"])
        print("Published functions:", ", ".join(sorted(item["name"].split("/")[-1] for item in functions)))
    elif args.action == "env":
        if state.get("phase") != "configured":
            raise ValueError("Deploy and configure the runtime first.")
        for key, value in environment(load_json(foundation.STATE)["outputs"], state).items():
            print(f"export {key}={shlex.quote(value)}")
    elif args.action == "run-monitor":
        import httpx

        keys = azure("functionapp", "keys", "list", "--resource-group", foundation.GROUP, "--name", state["functionAppName"])
        response = httpx.post(
            f"{state['functionAppUrl']}/admin/functions/freshness_timer",
            headers={"x-functions-key": keys["masterKey"]}, json={"input": ""}, timeout=30.0,
        )
        print(f"Monitor run requested: HTTP {response.status_code}.")
    elif args.action == "review":
        import httpx

        properties = blob_service().get_blob_client("source", state["sourceBlob"]).get_blob_properties()
        print(f"Source {state['sourceId']}: last modified {properties.last_modified.isoformat()}, "
              f"ETag SHA-256 {hashlib.sha256(properties.etag.encode()).hexdigest()[:16]}...")
        if not args.confirm_reviewed:
            print("Read the source, then rerun with --confirm-reviewed to attest this revision.")
            return
        response = httpx.post(
            f"{state['functionAppUrl']}/api/review",
            headers={"Authorization": f"Bearer {access_token(f'api://{state['application_client_id']}/user_impersonation')}"},
            json={"confirm_review": True, "source_etag": properties.etag, "policy_version": state["policyVersion"]},
            timeout=30.0,
        )
        print(f"Review API: HTTP {response.status_code} {response.text}")
    elif args.action == "evidence":
        container = blob_service().get_container_client("evidence")
        blobs = sorted(container.list_blobs(), key=lambda item: item.last_modified)
        if not blobs:
            print("No evidence records exist yet.")
            return
        run = args.correlation_id or blobs[-1].name.split("/")[1]
        for item in [blob for blob in blobs if blob.name.split("/")[1] == run]:
            print(json.dumps(json.loads(container.download_blob(item.name).readall()), indent=2, sort_keys=True))
    elif args.action == "inspect":
        resources = azure("resource", "list", "--resource-group", foundation.GROUP)
        print(json.dumps([
            {"name": item["name"], "type": item["type"], "location": item["location"], "owned": owned(item)}
            for item in resources
        ], indent=2))
    else:
        targets = cleanup_targets(state, args.subscription_id)
        for target in targets:
            if not owned(azure("resource", "show", "--ids", target)):
                raise ValueError("Runtime cleanup target ownership tags do not match; stop.")
        application = rest("GET", f"{GRAPH}/applications/{state['application_object_id']}") if state.get("application_object_id") else None
        if application and application.get("notes") != application_marker(state["functionAppId"]):
            raise ValueError("Entra application ownership mismatch; stop.")
        print("Deletes the KNW-001 Function App, its plan, Foundry account (purged), the control's Entra app, and")
        print("the runtime identities' role assignments on Storage/Search. Keeps Storage, Search and the resource group.")
        if args.action == "cleanup-plan":
            return
        if not args.approve_delete:
            raise ValueError("Deletion requires separate --approve-delete authorization.")
        principals = {state["functionPrincipalId"]}
        project = azure("resource", "show", "--ids", f"{state['foundryId']}/projects/knw-001")
        principals.add(project["identity"]["principalId"])
        base = load_json(foundation.STATE)["outputs"]
        for scope in (base["storageId"], base["searchId"]):
            for assignment in azure("role", "assignment", "list", "--scope", scope):
                if assignment["principalId"] in principals and assignment["scope"].lower() == scope.lower():
                    azure("role", "assignment", "delete", "--ids", assignment["id"])
        azure("resource", "delete", "--ids", state["functionAppId"])
        azure("resource", "delete", "--ids", state["planId"])
        azure("resource", "delete", "--ids", f"{state['foundryId']}/projects/knw-001")
        azure("resource", "delete", "--ids", state["foundryId"])
        azure("cognitiveservices", "account", "purge", "--location", state["foundryLocation"],
              "--resource-group", foundation.GROUP, "--name", state["foundryName"])
        if application:
            rest("DELETE", f"{GRAPH}/applications/{state['application_object_id']}")
            rest("DELETE", f"{GRAPH}/directory/deletedItems/{state['application_object_id']}")
        remaining = {item["id"].lower() for item in azure("resource", "list", "--resource-group", foundation.GROUP)}
        if remaining & {target.lower() for target in targets}:
            raise RuntimeError("A runtime cleanup target remains; inspect before retrying.")
        state["phase"] = "cleaned"
        for key in ("application_object_id", "application_client_id", "service_principal_id"):
            state.pop(key, None)
        foundation.save_state(state, RUNTIME_STATE)
        print("Runtime resources, Entra application and runtime role assignments removed.")


if __name__ == "__main__":
    shutil.which("az") or exit("Azure CLI is required.")
    main()
