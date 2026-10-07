"""Preview or remove only the resources recorded by this AUT-002 deployment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from deploy import DEFAULT_STATE, azure, request


def validate_state(state: dict, context: dict) -> list[str]:
    if state.get("control_id") != "AUT-002" or state.get("tenant_id") != context["tenantId"] or state.get("subscription_id") != context["id"]:
        raise ValueError("Cleanup control/tenant/subscription mismatch")
    project = state["projectId"]
    model = state["modelId"]
    if not project.endswith("/projects/aut-002") or not model.endswith("/deployments/aut-002-gpt-5"):
        raise ValueError("Cleanup may not target shared Foundry resources")
    expected_suffixes = {
        "projectId": "/projects/aut-002", "modelId": "/deployments/aut-002-gpt-5",
        "webAppId": f"/providers/Microsoft.Web/sites/{state['webAppName']}",
        "planId": f"/providers/Microsoft.Web/serverfarms/{state['webAppName']}-plan",
        "identityId": f"/providers/Microsoft.ManagedIdentity/userAssignedIdentities/{state['webAppName']}-identity",
    }
    prefix = f"/subscriptions/{context['id']}/resourceGroups/"
    resources = [state[key] for key in expected_suffixes]
    for key, suffix in expected_suffixes.items():
        if not state[key].startswith(prefix) or not state[key].endswith(suffix):
            raise ValueError("Invalid control resource ID")
    for assignment in state["roleAssignmentIds"]:
        scope, marker, assignment_id = assignment.rpartition("/providers/Microsoft.Authorization/roleAssignments/")
        account_scope = project.rsplit("/projects/", 1)[0]
        if not marker or scope.casefold() not in {project.casefold(), account_scope.casefold()} or not assignment_id:
            raise ValueError("Invalid role assignment scope")
    return resources


def existing_resource(resource_id: str):
    try:
        if "/providers/Microsoft.Authorization/" in resource_id:
            return azure("resource", "show", "--ids", resource_id, "--api-version", "2022-04-01")
        return azure("resource", "show", "--ids", resource_id)
    except RuntimeError as error:
        if "ResourceNotFound" in str(error) or "could not be found" in str(error):
            return None
        raise


def existing_directory_object(url: str):
    try:
        return request("GET", url)
    except RuntimeError as error:
        if "Request_ResourceNotFound" in str(error) or "ResourceNotFound" in str(error):
            return None
        raise


def cleanup(state: dict, confirm: bool) -> None:
    resources = validate_state(state, azure("account", "show"))
    for resource_id in resources:
        resource = existing_resource(resource_id)
        if resource is not None and resource_id != state["modelId"]:
            if resource.get("tags", {}).get("control-id") != "AUT-002":
                raise ValueError("Cleanup resource ownership tag missing")
    application_url = f"https://graph.microsoft.com/v1.0/applications/{state['application_object_id']}"
    application = existing_directory_object(application_url)
    if application is not None and application.get("notes") != f"Forged with Foundry AUT-002; resource={state['webAppId']}":
        raise ValueError("Cleanup Entra ownership mismatch")
    principal_url = f"https://graph.microsoft.com/v1.0/servicePrincipals/{state['service_principal_id']}"
    principal = existing_directory_object(principal_url)
    if principal is not None and (principal.get("appId") != state["application_client_id"] or "AUT-002" not in principal.get("tags", [])):
        raise ValueError("Cleanup service principal ownership mismatch")
    for assignment in state["roleAssignmentIds"]:
        resource = existing_resource(assignment)
        if resource is not None and resource.get("properties", {}).get("principalId") not in {
            state["identityPrincipalId"], state.get("setup_principal_id"),
        }:
            raise ValueError("Cleanup role assignment principal mismatch")
    for resource_id in resources:
        print(f"Target: {resource_id}")
    print("Target: control-owned Entra application, service principal and role assignments")
    if not confirm:
        print("Preview only. Repeat with --confirm to delete these targets.")
        return
    from azure.ai.projects import AIProjectClient
    from azure.identity import AzureCliCredential

    if existing_resource(state["webAppId"]):
        azure("webapp", "stop", "--ids", state["webAppId"])
    project = AIProjectClient(state["projectEndpoint"], AzureCliCredential(tenant_id=state["tenant_id"]))
    if state.get("agent_name") and existing_resource(state["projectId"]):
        from azure.core.exceptions import ResourceNotFoundError

        try:
            project.agents.delete(state["agent_name"], force=True)
        except ResourceNotFoundError:
            pass
    for assignment in state["roleAssignmentIds"]:
        if existing_resource(assignment):
            azure("role", "assignment", "delete", "--ids", assignment)
    for key in ["webAppId", "planId", "identityId", "modelId", "projectId"]:
        if existing_resource(state[key]):
            azure("resource", "delete", "--ids", state[key])
    if principal is not None:
        request("DELETE", principal_url)
    if application is not None:
        request("DELETE", application_url)
    if any(existing_resource(resource_id) is not None for resource_id in resources):
        raise RuntimeError("Cleanup incomplete: a control-owned resource still exists")
    if existing_directory_object(principal_url) is not None or existing_directory_object(application_url) is not None:
        raise RuntimeError("Cleanup incomplete: a control-owned Entra object still exists")
    print("Control-owned Azure resources are absent. Shared account, default project and model were not deleted.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--confirm", action="store_true")
    arguments = parser.parse_args()
    state = json.loads(arguments.state.read_text())
    cleanup(state, arguments.confirm)
    if arguments.confirm:
        arguments.state.rename(arguments.state.with_suffix(".cleaned.json"))


if __name__ == "__main__":
    main()