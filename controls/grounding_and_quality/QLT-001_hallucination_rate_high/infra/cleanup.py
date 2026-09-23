"""Remove only verified QLT-001 Azure resources and hosted sessions.

Platform conversations, Teams messages, the Foundry-portal-configured Eval
definition, and its continuous-evaluation rule require separate manual
cleanup in the Foundry portal. This command does not claim their deletion.
"""

import argparse
import json
from pathlib import Path
import subprocess
import sys

CONTROL = Path(__file__).resolve().parents[1]
AGENT = "it-helpdesk-kb-assistant"


def command(arguments: list[str]) -> str:
    """Run an explicit CLI operation without exposing configuration values."""
    result = subprocess.run(arguments, cwd=CONTROL, capture_output=True, text=True, check=True)
    return result.stdout


def validate_resources(subscription: str, group: str, insights: dict, workspace: dict) -> None:
    """Refuse shared, wrong-type, untagged, or cross-group deletion targets."""
    prefix = f"/subscriptions/{subscription}/resourceGroups/{group}/providers/".lower()
    for resource, resource_type, name_prefix in (
        (insights, "Microsoft.Insights/components", "appi-qlt001-"),
        (workspace, "Microsoft.OperationalInsights/workspaces", "log-qlt001-"),
    ):
        expected = prefix + resource_type.lower() + "/" + resource["name"].lower()
        if (resource["id"].lower() != expected or resource["type"].lower() != resource_type.lower()
                or not resource["name"].startswith(name_prefix)
                or resource.get("tags", {}).get("control-id") != "QLT-001"
                or resource.get("tags", {}).get("purpose") != "synthetic-groundedness-demo"):
            raise ValueError("Cleanup target is not a verified control-owned resource")
    if insights["properties"]["WorkspaceResourceId"].lower() != workspace["id"].lower():
        raise ValueError("Application Insights is linked to a different workspace")


def create_parser() -> argparse.ArgumentParser:
    """Require an explicit subscription, group, and deletion confirmation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subscription", required=True)
    parser.add_argument("--resource-group", required=True)
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--agent-principal-id",
                        help="The exact instance_identity.principal_id recorded for this deployment")
    return parser


def remaining_sessions(response: dict) -> list[dict]:
    """Exclude service-retained metadata for synchronously deleted sessions."""
    return [session for session in response["data"] if session.get("status") != "deleted"]


def main() -> int:
    """Validate all targets before deleting any session or resource."""
    args = create_parser().parse_args()
    try:
        outputs = json.loads(command([
            "az", "deployment", "group", "show", "--subscription", args.subscription,
            "--resource-group", args.resource_group, "--name", "qlt001-monitor",
            "--query", "properties.outputs", "-o", "json",
        ]))
        insights = json.loads(command(["az", "resource", "show", "--ids",
                                       outputs["applicationInsightsId"]["value"],
                                       "--api-version", "2020-02-02", "-o", "json"]))
        workspace = json.loads(command(["az", "resource", "show", "--ids",
                                        outputs["workspaceResourceId"]["value"],
                                        "--api-version", "2023-09-01", "-o", "json"]))
        validate_resources(args.subscription, args.resource_group, insights, workspace)
        environment = json.loads(command(["azd", "env", "get-values", "--output", "json"]))
        project_id = environment.get("AZURE_AI_PROJECT_ID", "")
        project_prefix = f"/subscriptions/{args.subscription}/resourceGroups/{args.resource_group}/"
        if not project_id.lower().startswith(project_prefix.lower()):
            raise ValueError("azd project does not match the explicitly selected resource group")
        agent = json.loads(command(["azd", "ai", "agent", "show", AGENT, "--output", "json"]))
        if agent["name"] != AGENT:
            raise ValueError("Unexpected agent identity")
        if args.confirm and agent.get("instance_identity", {}).get("principal_id") != args.agent_principal_id:
            raise ValueError("Agent principal does not match the recorded control deployment")
        sessions = json.loads(command(["azd", "ai", "agent", "sessions", "list",
                                       "--agent-name", AGENT, "--output", "json"]))
        if any(sessions.get(key) for key in ("next_link", "nextLink", "pagination_token", "continuation_token")):
            raise ValueError("Paginated session inventory requires explicit review")
        alerts = json.loads(command([
            "az", "resource", "list", "--subscription", args.subscription,
            "--resource-group", args.resource_group,
            "--resource-type", "microsoft.alertsmanagement/smartDetectorAlertRules", "-o", "json",
        ]))
        owned_alerts = []
        for alert in alerts:
            if alert["name"] == f"Failure Anomalies - {insights['name']}":
                detail = json.loads(command(["az", "resource", "show", "--ids", alert["id"],
                                             "--api-version", "2021-04-01", "-o", "json"]))
                if [value.lower() for value in detail["properties"]["scope"]] != [insights["id"].lower()]:
                    raise ValueError("Auto-created alert has additional or unexpected scope")
                owned_alerts.append(alert["id"])
        pending_sessions = remaining_sessions(sessions)
        print(f"Verified targets: {len(pending_sessions)} sessions, one agent, two Monitor resources, {len(owned_alerts)} linked alerts.")
        if not args.confirm:
            print("Inspection only. Add --confirm to delete these targets; shared project/group remain.")
            return 0
        for session in pending_sessions:
            command(["azd", "ai", "agent", "sessions", "delete", session["agent_session_id"],
                     "--agent-name", AGENT, "--no-prompt"])
        remaining = json.loads(command(["azd", "ai", "agent", "sessions", "list",
                                        "--agent-name", AGENT, "--output", "json"]))
        if remaining_sessions(remaining):
            raise RuntimeError("Hosted sessions remain; cleanup stopped")
        command(["azd", "ai", "agent", "delete", AGENT, "--force", "--no-prompt"])
        for resource_id in [*owned_alerts, insights["id"]]:
            command(["az", "resource", "delete", "--ids", resource_id])
        command(["az", "rest", "--method", "delete", "--url",
                 f"https://management.azure.com{workspace['id']}?api-version=2023-09-01&force=true",
                 "--output", "none"])
        print("Azure deletion requests completed. Verify resource absence separately.")
        print("Not covered: platform conversation history, Teams messages/flow, and the Foundry-portal "
              "Eval definition + continuous-evaluation rule -- delete those in the Foundry portal.")
        return 0
    except (ValueError, KeyError, RuntimeError, subprocess.SubprocessError):
        print("Cleanup stopped: ownership, access, or deletion verification failed. Shared resources were not targeted.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
