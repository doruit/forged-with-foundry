"""Register or remove the TOOL-003 prompt agent and record control-owned state."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

CONTROL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CONTROL_ROOT))

from azure.ai.projects import AIProjectClient  # noqa: E402
from azure.core.exceptions import HttpResponseError, ResourceNotFoundError  # noqa: E402
from azure.identity import AzureCliCredential  # noqa: E402

from src.tool_003 import AGENT_ID  # noqa: E402
from src.tool_003.agent import agent_definition  # noqa: E402

STATE_PATH = CONTROL_ROOT / ".azure" / "deployment.json"


def _client(endpoint: str) -> AIProjectClient:
    return AIProjectClient(endpoint=endpoint, credential=AzureCliCredential())


def register(arguments: argparse.Namespace) -> None:
    project = _client(arguments.endpoint)
    # New role assignments can take a few minutes to propagate.
    for attempt in range(1, 13):
        try:
            version = project.agents.create_version(
                agent_name=AGENT_ID, definition=agent_definition(arguments.model)
            )
            break
        except HttpResponseError as error:
            if error.status_code not in (401, 403) or attempt == 12:
                raise
            print(f"Waiting for role assignment to propagate (attempt {attempt}/12)...")
            time.sleep(15)
    state = {
        "control_id": "TOOL-003",
        "projectEndpoint": arguments.endpoint,
        "projectId": arguments.project_id,
        "roleAssignmentId": arguments.role_assignment_id,
        "modelDeployment": arguments.model,
        "agentName": AGENT_ID,
        "agentVersion": str(version.version),
    }
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    print(f"Registered {AGENT_ID} version {version.version}; state written to {STATE_PATH}")


def delete_agent(state: dict) -> None:
    """Delete the agent and verify it is gone; raise on any other failure."""
    if state.get("control_id") != "TOOL-003" or state.get("agentName") != AGENT_ID:
        raise SystemExit("State file is not TOOL-003 state; refusing to delete anything.")
    project = _client(state["projectEndpoint"])
    try:
        project.agents.delete(AGENT_ID)
        print(f"Deleted agent {AGENT_ID}")
    except ResourceNotFoundError:
        print(f"Agent {AGENT_ID} already absent")
    try:
        project.agents.get(AGENT_ID)
    except ResourceNotFoundError:
        print(f"Verified: agent {AGENT_ID} absent")
    else:
        raise SystemExit(f"Agent {AGENT_ID} still present after delete")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("register")
    add.add_argument("--endpoint", required=True)
    add.add_argument("--model", required=True)
    add.add_argument("--project-id", required=True)
    add.add_argument("--role-assignment-id", required=True)
    arguments = parser.parse_args()
    register(arguments)


if __name__ == "__main__":
    main()
