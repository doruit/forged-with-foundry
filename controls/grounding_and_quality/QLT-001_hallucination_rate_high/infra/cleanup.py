"""Remove verified QLT-001 agents, evaluation configuration, and Monitor resources.

The cleanup inspects the exact three prompt agents, their exact evaluation
rules, the one shared Eval named qlt001-fleet-groundedness, and the two
tagged Monitor resources before deletion. It never deletes the shared Foundry
project or resource group.
"""

import argparse
import json
from pathlib import Path
import subprocess
import sys

import truststore
from azure.ai.projects import AIProjectClient
from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
from azure.identity import AzureCliCredential

CONTROL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CONTROL))
from workload import FLEET  # noqa: E402

AGENTS = tuple(profile.agent_id for profile in FLEET)
EVAL_NAME = "qlt001-fleet-groundedness"


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
    """Require an explicit subscription, group, project endpoint, and deletion confirmation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subscription", required=True)
    parser.add_argument("--resource-group", required=True)
    parser.add_argument("--project-endpoint", required=True,
                        help="The Foundry project endpoint the fleet agents are registered in")
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--agent-principal-ids", nargs=3, metavar=("PLATFORM", "REGIONAL", "CONTRACTOR"),
                        help="The exact instance_identity.principal_id recorded for each fleet agent, "
                             "in workload.FLEET order")
    return parser


def verified_agents(client: AIProjectClient, expected_principal_ids: list[str] | None) -> dict:
    """Fetch and verify every fleet agent's identity before any deletion is attempted."""
    agents = {}
    for index, agent_id in enumerate(AGENTS):
        try:
            detail = client.agents.get(agent_id)
        except ResourceNotFoundError:
            raise ValueError(f"Fleet agent '{agent_id}' does not exist in this project")
        if detail.name != agent_id or detail.versions["latest"]["definition"]["kind"] != "prompt":
            raise ValueError(f"'{agent_id}' is not the expected kind:prompt fleet agent")
        if expected_principal_ids is not None:
            if detail.instance_identity["principal_id"] != expected_principal_ids[index]:
                raise ValueError(f"'{agent_id}' principal does not match the recorded control deployment")
        agents[agent_id] = detail
    return agents


def verified_evaluation_configuration(client: AIProjectClient) -> tuple[str, tuple[str, ...]]:
    """Verify that the exact fleet rules share one control-owned Eval."""
    rule_ids = tuple(f"{agent_id}-rule" for agent_id in AGENTS)
    eval_ids = set()
    for agent_id, rule_id in zip(AGENTS, rule_ids):
        try:
            rule = client.evaluation_rules.get(rule_id)
        except ResourceNotFoundError:
            raise ValueError(f"Evaluation rule '{rule_id}' does not exist")
        if getattr(getattr(rule, "filter", None), "agent_name", None) != agent_id:
            raise ValueError(f"Evaluation rule '{rule_id}' targets another agent")
        eval_id = getattr(getattr(rule, "action", None), "eval_id", None)
        if not eval_id:
            raise ValueError(f"Evaluation rule '{rule_id}' has no Eval id")
        eval_ids.add(eval_id)
    if len(eval_ids) != 1:
        raise ValueError("Fleet evaluation rules do not share one Eval")
    eval_id = eval_ids.pop()
    evaluation = client.get_openai_client().evals.retrieve(eval_id)
    if getattr(evaluation, "name", None) != EVAL_NAME:
        raise ValueError("Shared Eval is not owned by QLT-001")
    return eval_id, rule_ids


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

        truststore.inject_into_ssl()
        with AzureCliCredential() as credential:
            client = AIProjectClient(args.project_endpoint, credential, allow_preview=True)
            agents = verified_agents(client, args.agent_principal_ids)
            eval_id, rule_ids = verified_evaluation_configuration(client)
            pending_sessions = {
                agent_id: [s for s in client.agents.list_sessions(agent_id)]
                for agent_id in AGENTS
            }
            total_sessions = sum(len(sessions) for sessions in pending_sessions.values())
            print(f"Verified targets: {total_sessions} sessions across {len(AGENTS)} fleet agents, "
                  f"{len(rule_ids)} evaluation rules, one Eval, and two Monitor resources.")
            if not args.confirm:
                print("Inspection only. Add --confirm to delete these targets; shared project/group remain.")
                return 0
            for rule_id in rule_ids:
                client.evaluation_rules.delete(rule_id)
            for agent_id, sessions in pending_sessions.items():
                for session in sessions:
                    client.agents.delete_session(agent_id, session.id)
                remaining = list(client.agents.list_sessions(agent_id))
                if remaining:
                    raise RuntimeError(f"Sessions remain for '{agent_id}'; cleanup stopped")
                client.agents.delete(agent_id, force=True)
            client.get_openai_client().evals.delete(eval_id)
        for resource_id in [insights["id"]]:
            command(["az", "resource", "delete", "--ids", resource_id])
        command(["az", "rest", "--method", "delete", "--url",
                 f"https://management.azure.com{workspace['id']}?api-version=2023-09-01&force=true",
                 "--output", "none"])
        print("Azure deletion requests completed. Verify resource absence separately.")
        return 0
    except (ValueError, KeyError, RuntimeError, HttpResponseError, subprocess.SubprocessError):
        print("Cleanup stopped: ownership, access, or deletion verification failed. Shared resources were not targeted.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
