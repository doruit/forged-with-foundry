"""Configure the optional authenticated Teams workflow on an existing AUT-002 app."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from deploy import DEFAULT_STATE, ROOT, arm_configuration_url, azure, load_configuration, request, save_state, upload, workflow_settings
from cleanup import existing_resource, validate_state

sys.path.insert(0, str(ROOT))
from src.aut_002.teams import validate_workflow_url

SCOPE_ID = str(uuid5(NAMESPACE_URL, "forgedwithfoundry:AUT-002:Workflow.Review"))


def api_scope() -> dict:
    return {
        "id": SCOPE_ID, "value": "Workflow.Review", "type": "Admin", "isEnabled": True,
        "adminConsentDisplayName": "Review the pending AUT-002 synthetic action",
        "adminConsentDescription": "Call the AUT-002 review endpoint on behalf of an authenticated operator. OpsManager authorization is still required.",
    }


def validate_scope(scope: dict | None) -> None:
    if scope is not None and any(scope.get(key) != value for key, value in api_scope().items()):
        raise ValueError("Workflow API scope differs from the expected definition")


def configure(configuration: dict, state: dict, state_path: Path, *, confirm: bool) -> None:
    validate_state(state, azure("account", "show"))
    webapp = existing_resource(state["webAppId"])
    if webapp is None or webapp.get("tags", {}).get("control-id") != "AUT-002":
        raise ValueError("Deploy AUT-002 before configuring its workflow")
    url = configuration.get("AUT002_WORKFLOW_URL")
    if url:
        url = validate_workflow_url(url)
    application_url = f"https://graph.microsoft.com/v1.0/applications/{state['application_object_id']}"
    application = request("GET", application_url)
    if application.get("notes") != f"Forged with Foundry AUT-002; resource={state['webAppId']}" or application.get("appId") != state["application_client_id"]:
        raise ValueError("Existing application ownership mismatch")
    api = application.get("api") or {}
    scopes = api.get("oauth2PermissionScopes", [])
    scope = next((entry for entry in scopes if entry.get("id") == SCOPE_ID or entry.get("value") == "Workflow.Review"), None)
    validate_scope(scope)
    if not confirm:
        print("Preview: expose one delegated review scope on the existing app; keep authentication required; configure workflow transport.")
        print("Repeat with --confirm. No connector consent is granted by this command.")
        return
    if scope is None:
        scopes.append(api_scope())
    resource_uri = f"api://{state['application_client_id']}"
    api.update({"oauth2PermissionScopes": scopes, "requestedAccessTokenVersion": 2})
    request("PATCH", application_url, {"api": api, "identifierUris": list(dict.fromkeys(application.get("identifierUris", []) + [resource_uri]))})
    auth_url = arm_configuration_url(state, "authsettingsV2")
    auth = request("GET", auth_url)["properties"]
    if not auth["globalValidation"].get("requireAuthentication") or auth["globalValidation"].get("excludedPaths"):
        raise ValueError("Workflow callback requires app-wide Entra authentication with no excluded paths")
    auth["identityProviders"]["azureActiveDirectory"]["validation"]["allowedAudiences"] = [state["application_client_id"], resource_uri]
    request("PUT", auth_url, {"properties": auth})
    state["workflowEnabled"] = True
    if url:
        state["workflowUrl"] = url
    save_state(state_path, state)
    settings_url = arm_configuration_url(state, "appsettings")
    settings = request("POST", settings_url.replace("/appsettings?", "/appsettings/list?"))["properties"]
    settings.update(workflow_settings(state))
    request("PUT", settings_url, {"properties": settings})
    save_state(ROOT / ".azure/workflow-connection.json", {
        "baseResourceUrl": state["webAppUrl"], "resourceUri": resource_uri,
        "scope": "Workflow.Review", "callbackPath": "/api/teams/review",
        "triggerAllowedPrincipalId": state["identityPrincipalId"],
    })
    upload(configuration, state, state_path=state_path)
    print("Workflow connection values written to private .azure/workflow-connection.json.")
    print("Configure and test the flow before claiming Teams delivery or approval success.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / ".azure/config.env")
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    configure(load_configuration(args.config), json.loads(args.state.read_text()), args.state, confirm=args.confirm)


if __name__ == "__main__":
    main()