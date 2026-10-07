"""Deploy the control into an explicitly selected tenant and subscription."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import tempfile
import zipfile
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT.parents[2]
DEFAULT_STATE = ROOT / ".azure" / "deployment.json"


def azure(*arguments: str) -> dict | list | str | None:
    result = subprocess.run(["az", *arguments, "--only-show-errors", "-o", "json"], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"Azure {arguments[0]} failed: {result.stderr.strip()}")
    return json.loads(result.stdout) if result.stdout.strip() else None


def request(method: str, url: str, body: dict | None = None):
    arguments = ["rest", "--method", method, "--url", url]
    if body is None:
        return azure(*arguments)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as handle:
        json.dump(body, handle)
        handle.flush()
        return azure(*arguments, "--body", f"@{handle.name}")


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as handle:
        json.dump(state, handle, indent=2)
        temporary = Path(handle.name)
    temporary.replace(path)


def load_configuration(path: Path) -> dict[str, str]:
    configuration = {key: value for key, value in dotenv_values(path).items() if value is not None}
    required = ["AZURE_TENANT_ID", "AZURE_SUBSCRIPTION_ID", "AZURE_RESOURCE_GROUP", "AZURE_LOCATION", "FOUNDRY_ACCOUNT_NAME", "AUT002_APPROVER_ID"]
    missing = [key for key in required if not configuration.get(key)]
    if missing:
        raise ValueError(f"Missing configuration: {', '.join(missing)}")
    current = azure("account", "show")
    if current["tenantId"] != configuration["AZURE_TENANT_ID"] or current["id"] != configuration["AZURE_SUBSCRIPTION_ID"]:
        raise ValueError("Azure context mismatch; select the configured tenant and subscription first")
    return configuration


def arm_configuration_url(state: dict, section: str) -> str:
    return f"https://management.azure.com{state['webAppId']}/config/{section}?api-version=2024-11-01"


def package(path: Path) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(REPOSITORY / "constraints.txt", "constraints.txt")
        archive.writestr("requirements.txt", "-c constraints.txt\n" + (ROOT / "requirements.txt").read_text())
        for name in ("app.py", "chainlit.md", ".chainlit/config.toml", "policy/acs_manifest.yaml"):
            archive.write(ROOT / name, name)
        for source in (ROOT / "src").rglob("*.py"):
            archive.write(source, source.relative_to(ROOT))


def upload(configuration: dict, state: dict) -> None:
    if state.get("control_id") != "AUT-002" or state.get("tenant_id") != configuration["AZURE_TENANT_ID"] or state.get("subscription_id") != configuration["AZURE_SUBSCRIPTION_ID"]:
        raise ValueError("Upload manifest context mismatch")
    resource = azure("webapp", "show", "--ids", state["webAppId"])
    if resource.get("tags", {}).get("control-id") != "AUT-002" or resource["name"] != state["webAppName"]:
        raise ValueError("Upload webapp ownership mismatch")
    with tempfile.TemporaryDirectory() as temporary:
        archive = Path(temporary) / "aut002.zip"
        package(archive)
        azure("webapp", "deploy", "--resource-group", configuration["AZURE_RESOURCE_GROUP"],
              "--subscription", state["subscription_id"], "--name", state["webAppName"],
              "--src-path", str(archive), "--type", "zip", "--async", "true", "--track-status", "false", "--restart", "true")
    print(f"AUT-002 upload accepted: {state['webAppUrl']}")
    print("Run with --status and continue only when deployment status is 4 (success).")


def deploy(configuration: dict, state_path: Path) -> dict:
    from configure_entra import configure

    state = json.loads(state_path.read_text()) if state_path.exists() else {
        "control_id": "AUT-002", "tenant_id": configuration["AZURE_TENANT_ID"],
        "subscription_id": configuration["AZURE_SUBSCRIPTION_ID"],
    }
    if state.get("control_id") != "AUT-002" or state.get("tenant_id") != configuration["AZURE_TENANT_ID"] or state.get("subscription_id") != configuration["AZURE_SUBSCRIPTION_ID"]:
        raise ValueError("Deployment manifest belongs to another control or environment")
    os.environ.update(configuration)
    setup_user = azure("ad", "signed-in-user", "show")["id"]
    state["setup_principal_id"] = setup_user
    save_state(state_path, state)
    os.environ["AUT002_SETUP_PRINCIPAL_ID"] = setup_user
    output = azure(
        "deployment", "group", "create", "--name", "aut002-demo",
        "--subscription", configuration["AZURE_SUBSCRIPTION_ID"],
        "--resource-group", configuration["AZURE_RESOURCE_GROUP"],
        "--template-file", str(ROOT / "infra/main.bicep"),
        "--parameters", str(ROOT / "infra/main.bicepparam"), "--query", "properties.outputs",
    )
    recorded_assignments = state.get("roleAssignmentIds", [])
    state.update({key: item["value"] for key, item in output.items()})
    state["roleAssignmentIds"] = list(dict.fromkeys(recorded_assignments + state["roleAssignmentIds"]))
    save_state(state_path, state)
    configure(configuration, state, state_path)

    from azure.ai.projects import AIProjectClient
    from azure.identity import AzureCliCredential
    import sys

    sys.path.insert(0, str(ROOT))
    from src.aut_002.foundry import AGENT_NAME, register_agent

    project = AIProjectClient(state["projectEndpoint"], AzureCliCredential(tenant_id=state["tenant_id"]))
    if not state.get("agent_version"):
        agent = register_agent(project, state["modelDeploymentName"])
        state.update(agent_name=AGENT_NAME, agent_version=agent.version)
        save_state(state_path, state)
    else:
        project.agents.get_version(state["agent_name"], state["agent_version"])

    settings_url = arm_configuration_url(state, "appsettings")
    settings = request("POST", settings_url.replace("/appsettings?", "/appsettings/list?"))["properties"]
    settings.update({
        "AUT002_AGENT_VERSION": state["agent_version"],
        "CHAINLIT_AUTH_SECRET": settings.get("CHAINLIT_AUTH_SECRET") or secrets.token_urlsafe(48),
        "CHAINLIT_NO_TELEMETRY": "true",
    })
    request("PUT", settings_url, {"properties": settings})
    upload(configuration, state)
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / ".azure/config.env")
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="Validate selected context without creating resources")
    mode.add_argument("--status", action="store_true", help="Check the uploaded application deployment without redeploying")
    mode.add_argument("--code-only", action="store_true", help="Upload updated code without changing Azure or Entra resources")
    arguments = parser.parse_args()
    configuration = load_configuration(arguments.config)
    if arguments.code_only:
        upload(configuration, json.loads(arguments.state.read_text()))
    elif arguments.status:
        state = json.loads(arguments.state.read_text())
        deployments = azure("webapp", "log", "deployment", "list", "--name", state["webAppName"],
                            "--resource-group", configuration["AZURE_RESOURCE_GROUP"],
                            "--subscription", configuration["AZURE_SUBSCRIPTION_ID"])
        latest = deployments[0] if deployments else {}
        print(f"Deployment status: {latest.get('status', 'unavailable')}; complete: {latest.get('complete', False)}")
        if latest.get("status") != 4 or not latest.get("complete") or not latest.get("active"):
            raise SystemExit(2)
        print(f"Open {state['webAppUrl']} and sign in with Microsoft Entra.")
    elif arguments.check:
        print("Configured tenant/subscription match the authenticated Azure context.")
    else:
        deploy(configuration, arguments.state)


if __name__ == "__main__":
    main()