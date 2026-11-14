"""Deploy AUT-004: Bicep, the stop switch, Entra sign-in, the Foundry agent and the app.

Prerequisite: the shared root infra/ deployment and its infra/.env.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT.parents[2]
STATE_PATH = ROOT / ".azure" / "deployment.json"
CONTRACT = ROOT / "workload" / ".fwf" / "agents" / "aut-004-support-refunds" / "governance.yaml"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(REPOSITORY))


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


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def declaration() -> dict[str, str]:
    """The stop scope comes from the validated governance contract, nowhere else."""
    from scripts.validate_governance_contract import (
        parse_contract_bytes,
        read_contract_bytes,
        validate_contract,
        validate_control_entry,
    )

    raw = read_contract_bytes(CONTRACT)
    data = parse_contract_bytes(raw, source="AUT-004 contract")
    entry, entry_errors = validate_control_entry("AUT-004", data)
    errors = validate_contract(data, agent_dir_name="aut-004-support-refunds") + entry_errors
    if errors or entry is None:
        raise SystemExit(f"AUT-004 contract invalid: {errors}")
    [scope] = entry["evidence"]["stopScopes"]
    from src.aut_004.tools import TOOL_NAMES

    if scope["toolName"] not in TOOL_NAMES:
        raise SystemExit(f"AUT-004 contract names unknown tool {scope['toolName']!r}; expected one of {TOOL_NAMES}.")
    return {"tool": scope["toolName"], "flag": scope["flagName"], "sha256": hashlib.sha256(raw).hexdigest()}


def retry_forbidden(action, what: str, attempts: int = 20):
    """New role assignments take minutes to propagate; retry only 401/403."""
    from azure.core.exceptions import HttpResponseError

    for attempt in range(1, attempts + 1):
        try:
            return action()
        except HttpResponseError as error:
            if error.status_code not in (401, 403) or attempt == attempts:
                raise
            print(f"Waiting for role propagation before {what} ({attempt}/{attempts})...")
            time.sleep(15)


def create_switch(state: dict, flag: str) -> None:
    from azure.appconfiguration import AzureAppConfigurationClient, FeatureFlagConfigurationSetting
    from azure.core.exceptions import ResourceNotFoundError
    from azure.identity import AzureCliCredential

    client = AzureAppConfigurationClient(state["storeEndpoint"], AzureCliCredential())

    def ensure() -> None:
        try:
            client.get_configuration_setting(key=".appconfig.featureflag/" + flag)
            print(f"Stop switch {flag} already exists; its state is left unchanged.")
        except ResourceNotFoundError:
            client.add_configuration_setting(FeatureFlagConfigurationSetting(flag, enabled=True))
            print(f"Created stop switch {flag} (enabled: refunds allowed).")

    retry_forbidden(ensure, "creating the stop switch")


def register_agent(state: dict, model: str) -> str:
    from azure.ai.projects import AIProjectClient
    from azure.identity import AzureCliCredential

    from src.aut_004 import AGENT_ID
    from src.aut_004.agent import agent_definition

    project = AIProjectClient(endpoint=state["projectEndpoint"], credential=AzureCliCredential())
    version = retry_forbidden(
        lambda: project.agents.create_version(agent_name=AGENT_ID, definition=agent_definition(model)),
        "registering the agent",
    )
    print(f"Registered {AGENT_ID} version {version.version}")
    return str(version.version)


def package() -> bytes:
    with tempfile.TemporaryDirectory() as temporary:
        archive = Path(temporary) / "aut004.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as handle:
            handle.write(REPOSITORY / "constraints.txt", "constraints.txt")
            handle.writestr("requirements.txt", "-c constraints.txt\n" + (ROOT / "requirements.txt").read_text())
            for name in ("app.py", "chainlit.md", ".chainlit/config.toml", "policy/acs_manifest.yaml"):
                handle.write(ROOT / name, name)
            for source in (ROOT / "src").rglob("*.py"):
                handle.write(source, source.relative_to(ROOT))
        return archive.read_bytes()


def configure_app(state: dict, scope: dict[str, str], agent_version: str) -> None:
    url = f"https://management.azure.com{state['webAppId']}/config/appsettings?api-version=2024-11-01"
    settings = request("POST", url.replace("/appsettings?", "/appsettings/list?"))["properties"]
    settings.update({
        "AUT004_PROTECTED_TOOL": scope["tool"],
        "AUT004_FLAG_NAME": scope["flag"],
        "AUT004_CONTRACT_SHA256": scope["sha256"],
        "AUT004_AGENT_VERSION": agent_version,
        "CHAINLIT_AUTH_SECRET": settings.get("CHAINLIT_AUTH_SECRET") or secrets.token_urlsafe(48),
    })
    request("PUT", url, {"properties": settings})


def upload(state: dict, resource_group: str) -> None:
    with tempfile.TemporaryDirectory() as temporary:
        archive = Path(temporary) / "aut004.zip"
        archive.write_bytes(package())
        print("Uploading the app; the remote build takes several minutes...")
        azure("webapp", "deploy", "--resource-group", resource_group, "--name", state["webAppName"],
              "--src-path", str(archive), "--type", "zip", "--restart", "true",
              "--async", "true", "--track-status", "false")
    wait_for_build(state, resource_group)


def wait_for_build(state: dict, resource_group: str, attempts: int = 80) -> None:
    """Poll the platform's own deployment record: 4 = success, 3 = failed."""
    for _ in range(attempts):
        time.sleep(15)
        latest = (azure("webapp", "log", "deployment", "list", "--name", state["webAppName"],
                        "--resource-group", resource_group) or [{}])[0]
        if latest.get("status") == 4 and latest.get("complete"):
            print("App build and deployment succeeded.")
            return
        if latest.get("status") == 3:
            raise SystemExit("App deployment failed; see: az webapp log deployment show")
    raise SystemExit("App deployment did not finish in time; check: az webapp log deployment list")


def main() -> None:
    from configure_entra import configure

    env = {k: v for k, v in dotenv_values(REPOSITORY / "infra" / ".env").items() if v}
    for key in ("AZURE_TENANT_ID", "AZURE_SUBSCRIPTION_ID", "AZURE_RESOURCE_GROUP", "FOUNDRY_ACCOUNT_NAME", "AZURE_OPENAI_CHAT_DEPLOYMENT"):
        if key not in env:
            raise SystemExit(f"Missing {key} in infra/.env; deploy the shared infra/ first.")
    account = azure("account", "show")
    if account["id"] != env["AZURE_SUBSCRIPTION_ID"] or account["tenantId"] != env["AZURE_TENANT_ID"]:
        raise SystemExit("Azure CLI context does not match infra/.env; run az account set --subscription <id>.")

    scope = declaration()
    operator = azure("ad", "signed-in-user", "show")["id"]
    print(f"Contract valid: stop scope {scope['tool']} via switch {scope['flag']}")
    print("Deploying AUT-004 resources (several minutes)...")
    outputs = azure(
        "deployment", "group", "create", "--resource-group", env["AZURE_RESOURCE_GROUP"], "--name", "aut-004",
        "--template-file", str(ROOT / "infra" / "main.bicep"),
        "--parameters", f"foundryAccountName={env['FOUNDRY_ACCOUNT_NAME']}",
        f"modelDeploymentName={env['AZURE_OPENAI_CHAT_DEPLOYMENT']}", f"operatorPrincipalId={operator}",
        "--query", "properties.outputs",
    )
    previous = json.loads(STATE_PATH.read_text()) if STATE_PATH.is_file() else {}
    state = {
        **previous,
        "control_id": "AUT-004",
        "tenant_id": env["AZURE_TENANT_ID"],
        "subscription_id": env["AZURE_SUBSCRIPTION_ID"],
        "operator_principal_id": operator,
        **{key: value["value"] for key, value in outputs.items()},
    }
    save_state(state)
    create_switch(state, scope["flag"])
    configure(state, operator, save_state)
    state["agentVersion"] = register_agent(state, env["AZURE_OPENAI_CHAT_DEPLOYMENT"])
    save_state(state)
    configure_app(state, scope, state["agentVersion"])
    upload(state, env["AZURE_RESOURCE_GROUP"])
    print(f"AUT-004 deployed. Open {state['webAppUrl']} and sign in with Microsoft Entra.")


if __name__ == "__main__":
    main()
