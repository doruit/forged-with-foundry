"""Ownership-checked cleanup of TOOL-003's control-owned Azure resources.

Only an explicit "not found" from Azure counts as absent. Any other CLI
failure (expired sign-in, wrong tenant, throttling, network) stops cleanup and
keeps the local state file, so nothing is reported clean that was not verified.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

CONTROL_ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = CONTROL_ROOT / ".azure" / "deployment.json"
CONTROL_ID = "TOOL-003"
_NOT_FOUND = ("ResourceNotFound", "RoleAssignmentNotFound", "ResourceGroupNotFound")


class CleanupError(RuntimeError):
    pass


def az(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["az", *arguments, "--only-show-errors", "-o", "json"], capture_output=True, text=True)


def _arm_get(resource_id: str, api_version: str) -> dict | None:
    """Return the resource, None when Azure says it does not exist, or raise."""
    result = az("rest", "--method", "get", "--url", f"https://management.azure.com{resource_id}?api-version={api_version}")
    if result.returncode == 0:
        return json.loads(result.stdout)
    if any(code in result.stderr for code in _NOT_FOUND):
        return None
    raise CleanupError(f"Could not read {resource_id}: {result.stderr.strip()}")


def _require(result: subprocess.CompletedProcess[str], action: str) -> None:
    if result.returncode != 0 and not any(code in result.stderr for code in _NOT_FOUND):
        raise CleanupError(f"{action} failed: {result.stderr.strip()}")


def cleanup(state: dict, *, delete_agent) -> None:
    if state.get("control_id") != CONTROL_ID:
        raise CleanupError("State file is not TOOL-003 state; refusing to delete anything.")
    project_id, role_id = state["projectId"], state["roleAssignmentId"]

    account = az("account", "show")
    if account.returncode != 0:
        raise CleanupError("Azure CLI is not signed in; run az login and retry.")
    if f"/subscriptions/{json.loads(account.stdout)['id']}/" not in project_id:
        raise CleanupError("Azure CLI subscription does not match the TOOL-003 project; run az account set.")

    project = _arm_get(project_id, "2025-06-01")
    if project is not None:
        if (project.get("tags") or {}).get("control-id") != CONTROL_ID:
            raise CleanupError("Project is not tagged control-id=TOOL-003; refusing to delete it.")
        delete_agent()
    if _arm_get(role_id, "2022-04-01") is not None:
        _require(az("role", "assignment", "delete", "--ids", role_id), "Role assignment delete")
    if project is not None:
        print(f"Deleting project {project_id.rsplit('/', 1)[-1]}...")
        _require(az("resource", "delete", "--ids", project_id), "Project delete")

    if _arm_get(project_id, "2025-06-01") is not None:
        raise CleanupError("Project still present after delete.")
    print("Verified: TOOL-003 project absent.")
    if _arm_get(role_id, "2022-04-01") is not None:
        raise CleanupError("Role assignment still present after delete.")
    print("Verified: TOOL-003 role assignment absent.")


def main() -> int:
    if not STATE_PATH.is_file():
        print(f"No TOOL-003 state at {STATE_PATH}; nothing to clean up.")
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
    print("TOOL-003 cleanup complete. Local evidence remains in evidence/ (delete it with: rm -rf evidence).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
