"""Ownership-checked cleanup of AUT-004's Azure and Entra resources.

Only an explicit "not found" counts as absent. Any other failure stops cleanup
and keeps the state file. The shared Foundry account, model deployment and
resource group are never touched.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

CONTROL_ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = CONTROL_ROOT / ".azure" / "deployment.json"
CONTROL_ID = "AUT-004"
GRAPH = "https://graph.microsoft.com/v1.0"
_NOT_FOUND = ("ResourceNotFound", "EntityNotFound", "RoleAssignmentNotFound", "Request_ResourceNotFound", "NotFound(")
API = {
    "Microsoft.Web/sites": "2024-11-01",
    "Microsoft.Web/serverfarms": "2024-11-01",
    "Microsoft.ManagedIdentity/userAssignedIdentities": "2023-01-31",
    "Microsoft.AppConfiguration/configurationStores": "2024-06-01",
    "Microsoft.OperationalInsights/workspaces": "2023-09-01",
    "Microsoft.CognitiveServices/accounts/projects": "2025-06-01",
    "Microsoft.Authorization/roleAssignments": "2022-04-01",
}
DELETE_ORDER = ("webAppId", "planId", "identityId", "storeId", "workspaceId", "projectId")


class CleanupError(RuntimeError):
    pass


def az(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["az", *arguments, "--only-show-errors", "-o", "json"], capture_output=True, text=True)


def resource_type(resource_id: str) -> str:
    if "/providers/Microsoft.Authorization/roleAssignments/" in resource_id:
        return "Microsoft.Authorization/roleAssignments"
    parts = resource_id.rsplit("/providers/", 1)[1].split("/")
    return "/".join([parts[0], *parts[1:][0::2]])


def _missing(result: subprocess.CompletedProcess[str]) -> bool:
    return result.returncode != 0 and any(code in result.stderr for code in _NOT_FOUND)


def get(url: str) -> dict | None:
    result = az("rest", "--method", "get", "--url", url)
    if result.returncode == 0:
        return json.loads(result.stdout) if result.stdout.strip() else {}
    if _missing(result):
        return None
    raise CleanupError(f"Could not read {url.split('?')[0].rsplit('/', 1)[-1]}: {result.stderr.strip()}")


def delete(url: str) -> None:
    result = az("rest", "--method", "delete", "--url", url)
    if result.returncode != 0 and not _missing(result):
        raise CleanupError(f"Delete of {url.split('?')[0].rsplit('/', 1)[-1]} failed: {result.stderr.strip()}")


def arm_url(resource_id: str, *, force: bool = False) -> str:
    url = f"https://management.azure.com{resource_id}?api-version={API[resource_type(resource_id)]}"
    return url + "&force=true" if force else url


def owned_scopes(state: dict) -> set[str]:
    account = state["projectId"].rsplit("/projects/", 1)[0]
    return {state["storeId"].casefold(), state["projectId"].casefold(), account.casefold()}


def check_ownership(state: dict) -> dict[str, dict]:
    present: dict[str, dict] = {}
    for key in DELETE_ORDER:
        resource = get(arm_url(state[key]))
        if resource is None:
            continue
        if (resource.get("tags") or {}).get("control-id") != CONTROL_ID:
            raise CleanupError(f"{key} is not tagged control-id={CONTROL_ID}; refusing to delete anything.")
        present[key] = resource
    principals = {state.get("identityPrincipalId"), state.get("operator_principal_id")}
    for assignment in state["roleAssignmentIds"]:
        scope = assignment.split("/providers/Microsoft.Authorization/roleAssignments/")[0]
        if scope.casefold() not in owned_scopes(state):
            raise CleanupError("A recorded role assignment is outside AUT-004's scopes; refusing to delete anything.")
        resource = get(arm_url(assignment))
        if resource is not None and resource.get("properties", {}).get("principalId") not in principals:
            raise CleanupError("A recorded role assignment belongs to another principal; refusing to delete anything.")
    application = get(f"{GRAPH}/applications/{state['application_object_id']}") if state.get("application_object_id") else None
    if application is not None and application.get("notes") != f"Forged with Foundry AUT-004; resource={state['webAppId']}":
        raise CleanupError("Entra application ownership marker mismatch; refusing to delete anything.")
    principal = get(f"{GRAPH}/servicePrincipals/{state['service_principal_id']}") if state.get("service_principal_id") else None
    if principal is not None and (
        principal.get("appId") != state.get("application_client_id") or CONTROL_ID not in (principal.get("tags") or [])
    ):
        raise CleanupError("Service principal is not AUT-004's sign-in app; refusing to delete anything.")
    return present


def cleanup(state: dict, *, delete_agent, sleep=time.sleep, attempts: int = 40) -> None:
    if state.get("control_id") != CONTROL_ID:
        raise CleanupError("State file is not AUT-004 state; refusing to delete anything.")
    account = az("account", "show")
    if account.returncode != 0:
        raise CleanupError("Azure CLI is not signed in; run az login and retry.")
    if json.loads(account.stdout)["id"] != state["subscription_id"]:
        raise CleanupError("Azure CLI subscription does not match the AUT-004 deployment; run az account set.")
    present = check_ownership(state)
    if "projectId" in present and state.get("agentVersion"):
        delete_agent(state)
    for assignment in state["roleAssignmentIds"]:
        delete(arm_url(assignment))
    for key in DELETE_ORDER:
        if key in present:
            print(f"Deleting {resource_type(state[key]).rsplit('/', 1)[-1]} {state[key].rsplit('/', 1)[-1]}...")
            delete(arm_url(state[key], force=key == "workspaceId"))
    for kind in ("servicePrincipals", "applications"):
        object_id = state.get("service_principal_id" if kind == "servicePrincipals" else "application_object_id")
        if object_id:
            delete(f"{GRAPH}/{kind}/{object_id}")
    targets = [arm_url(state[key]) for key in DELETE_ORDER] + [arm_url(a) for a in state["roleAssignmentIds"]]
    targets += [f"{GRAPH}/applications/{state['application_object_id']}"] if state.get("application_object_id") else []
    targets += [f"{GRAPH}/servicePrincipals/{state['service_principal_id']}"] if state.get("service_principal_id") else []
    for url in targets:
        for _ in range(attempts):
            if get(url) is None:
                break
            sleep(15)
        else:
            raise CleanupError(f"{url.split('?')[0].rsplit('/', 1)[-1]} still present after delete.")
        print(f"Verified absent: {url.split('?')[0].rsplit('/', 1)[-1]}")


def delete_foundry_agent(state: dict) -> None:
    from azure.ai.projects import AIProjectClient
    from azure.core.exceptions import ResourceNotFoundError
    from azure.identity import AzureCliCredential

    project = AIProjectClient(endpoint=state["projectEndpoint"], credential=AzureCliCredential())
    try:
        project.agents.delete("aut-004-support-refunds")
    except ResourceNotFoundError:
        pass
    try:
        project.agents.get("aut-004-support-refunds")
    except ResourceNotFoundError:
        print("Verified absent: agent aut-004-support-refunds")
        return
    raise CleanupError("Agent still present after delete.")


def main() -> int:
    if not STATE_PATH.is_file():
        print(f"No AUT-004 state at {STATE_PATH}; nothing to clean up.")
        return 0
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    try:
        cleanup(state, delete_agent=delete_foundry_agent)
    except CleanupError as error:
        print(f"Cleanup stopped: {error} State kept at {STATE_PATH}.", file=sys.stderr)
        return 1
    STATE_PATH.unlink()
    print("AUT-004 cleanup complete. The shared Foundry account and model deployment were not touched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
