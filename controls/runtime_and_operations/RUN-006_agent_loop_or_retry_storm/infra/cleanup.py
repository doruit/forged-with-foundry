"""Ownership-checked cleanup of RUN-006's control-owned Azure resources.

Only an explicit "not found" from Azure counts as absent. Any other CLI
failure (expired sign-in, wrong tenant, throttling, network) stops cleanup and
keeps the local state file, so nothing is reported clean that was not verified.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

CONTROL_ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = CONTROL_ROOT / ".azure" / "deployment.json"
CONTROL_ID = "RUN-006"
_NOT_FOUND = ("ResourceNotFound", "RoleAssignmentNotFound", "ResourceGroupNotFound", "WorkspaceNotFound")
_API_VERSIONS = {
    "Microsoft.Insights/scheduledQueryRules": "2023-12-01",
    "Microsoft.Insights/actionGroups": "2023-01-01",
    "Microsoft.Authorization/roleAssignments": "2022-04-01",
    "Microsoft.Insights/components": "2020-02-02",
    "Microsoft.OperationalInsights/workspaces": "2023-09-01",
    "Microsoft.CognitiveServices/accounts/projects": "2025-06-01",
}


class CleanupError(RuntimeError):
    pass


def az(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["az", *arguments, "--only-show-errors", "-o", "json"], capture_output=True, text=True)


def resource_type(resource_id: str) -> str:
    """Return the type of the last resource segment, for example Microsoft.Insights/components."""
    if "/providers/Microsoft.Authorization/roleAssignments/" in resource_id:
        return "Microsoft.Authorization/roleAssignments"
    provider_path = resource_id.rsplit("/providers/", 1)[1].split("/")
    namespace, rest = provider_path[0], provider_path[1:]
    return "/".join([namespace, *rest[0::2]])


def _url(resource_id: str, *, force: bool = False) -> str:
    url = f"https://management.azure.com{resource_id}?api-version={_API_VERSIONS[resource_type(resource_id)]}"
    return url + "&force=true" if force else url


def arm_get(resource_id: str) -> dict | None:
    """Return the resource, None when Azure says it does not exist, or raise."""
    result = az("rest", "--method", "get", "--url", _url(resource_id))
    if result.returncode == 0:
        return json.loads(result.stdout) if result.stdout.strip() else {}
    if any(code in result.stderr for code in _NOT_FOUND):
        return None
    raise CleanupError(f"Could not read {resource_id.rsplit('/', 1)[-1]}: {result.stderr.strip()}")


def arm_delete(resource_id: str) -> None:
    force = resource_type(resource_id) == "Microsoft.OperationalInsights/workspaces"
    result = az("rest", "--method", "delete", "--url", _url(resource_id, force=force))
    if result.returncode != 0 and not any(code in result.stderr for code in _NOT_FOUND):
        raise CleanupError(f"Delete of {resource_id.rsplit('/', 1)[-1]} failed: {result.stderr.strip()}")


def _owned(resource_id: str, resource: dict, owned: list[str]) -> bool:
    if resource_type(resource_id) == "Microsoft.Authorization/roleAssignments":
        scope = resource_id.split("/providers/Microsoft.Authorization/roleAssignments/")[0]
        return scope in owned
    return (resource.get("tags") or {}).get("control-id") == CONTROL_ID


def cleanup(state: dict, *, delete_agent, sleep=time.sleep, attempts: int = 40) -> None:
    if state.get("control_id") != CONTROL_ID:
        raise CleanupError(f"State file is not {CONTROL_ID} state; refusing to delete anything.")
    owned: list[str] = state["ownedResources"]

    account = az("account", "show")
    if account.returncode != 0:
        raise CleanupError("Azure CLI is not signed in; run az login and retry.")
    subscription = f"/subscriptions/{json.loads(account.stdout)['id']}/"
    if not all(resource_id.startswith(subscription) for resource_id in owned):
        raise CleanupError("Azure CLI subscription does not match the recorded resources; run az account set.")

    present = {}
    for resource_id in owned:
        resource = arm_get(resource_id)
        if resource is None:
            continue
        if not _owned(resource_id, resource, owned):
            raise CleanupError(f"{resource_id.rsplit('/', 1)[-1]} is not owned by {CONTROL_ID}; refusing to delete.")
        present[resource_id] = resource

    if state["projectId"] in present:
        delete_agent()
    for resource_id in owned:
        if resource_id in present:
            print(f"Deleting {resource_type(resource_id).rsplit('/', 1)[-1]} {resource_id.rsplit('/', 1)[-1]}...")
            arm_delete(resource_id)

    for resource_id in owned:
        for _ in range(attempts):
            if arm_get(resource_id) is None:
                break
            sleep(15)
        else:
            raise CleanupError(f"{resource_id.rsplit('/', 1)[-1]} still present after delete.")
        print(f"Verified absent: {resource_type(resource_id).rsplit('/', 1)[-1]} {resource_id.rsplit('/', 1)[-1]}")


def main() -> int:
    if not STATE_PATH.is_file():
        print(f"No {CONTROL_ID} state at {STATE_PATH}; nothing to clean up.")
        return 0
    sys.path.insert(0, str(CONTROL_ROOT / "infra"))
    from agent_registry import delete_agent

    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    try:
        cleanup(state, delete_agent=lambda: delete_agent(state))
    except CleanupError as error:
        print(f"Cleanup stopped: {error} State kept at {STATE_PATH}.", file=sys.stderr)
        return 1
    STATE_PATH.unlink()
    print(f"{CONTROL_ID} cleanup complete. Local evidence remains in evidence/ (delete it with: rm -rf evidence).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
