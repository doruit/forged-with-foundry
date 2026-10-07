"""Configure or remove an owned GitHub-environment OIDC release identity."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from uuid import NAMESPACE_URL, uuid5

CONTROL = Path(__file__).resolve().parents[1]
RUNTIME = CONTROL.parent / "AUT-002_irreversible_action_attempted"
sys.path.insert(0, str(RUNTIME / "infra"))
from deploy import DEFAULT_STATE, azure, request, save_state

OWNED_STATE = CONTROL / ".azure/oidc-state.json"
ENVIRONMENT = "autonomy-mandate-demo"


def github(*arguments: str, value: str | None = None) -> str:
    result = subprocess.run(["gh", *arguments], input=value, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError("GitHub configuration failed: " + result.stderr.strip())
    return result.stdout


def setup(repository: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("invalid repository")
    state = json.loads(DEFAULT_STATE.read_text())
    context = azure("account", "show")
    if context["tenantId"] != state["tenant_id"] or context["id"] != state["subscription_id"]:
        raise ValueError("OIDC target context mismatch")
    environment = json.loads(github("api", f"repos/{repository}/environments/{ENVIRONMENT}"))
    if not any(rule["type"] == "required_reviewers" and rule.get("reviewers") for rule in environment["protection_rules"]):
        raise ValueError("real release reviewer protection is required")
    group = state["webAppId"].split("/providers/", 1)[0]
    identity_id = group + "/providers/Microsoft.ManagedIdentity/userAssignedIdentities/autonomy-mandate-release-test"
    marker = f"AUT-PRE-001/AUT-PRE-002 temporary OIDC; repo={repository}"
    try:
        existing = request("GET", f"https://management.azure.com{identity_id}?api-version=2023-01-31")
    except RuntimeError as error:
        if "ResourceNotFound" not in str(error):
            raise
    else:
        if existing.get("tags", {}).get("purpose") != marker:
            raise ValueError("OIDC identity ownership mismatch")
    identity = request("PUT", f"https://management.azure.com{identity_id}?api-version=2023-01-31", {
        "location": "swedencentral", "tags": {"control-id": "AUT-PRE-001", "purpose": marker},
    })
    owned = {"repository": repository, "environment": ENVIRONMENT, "tenant_id": state["tenant_id"],
             "subscription_id": state["subscription_id"], "identityId": identity_id,
             "principalId": identity["properties"]["principalId"], "marker": marker, "roleAssignmentIds": []}
    save_state(OWNED_STATE, owned)
    request("PUT", f"https://management.azure.com{identity_id}/federatedIdentityCredentials/github-mandate-release?api-version=2023-01-31", {"properties": {
        "issuer": "https://token.actions.githubusercontent.com",
        "subject": f"repo:{repository}:environment:{ENVIRONMENT}",
        "audiences": ["api://AzureADTokenExchange"],
    }})
    roles = [(state["webAppId"], "b24988ac-6180-42a0-ab88-20f7382dd24c"),
             (state["projectId"], "53ca6127-db72-4b80-b1b0-d745d6d5456d")]
    for scope, role in roles:
        identifier = scope + "/providers/Microsoft.Authorization/roleAssignments/" + str(uuid5(NAMESPACE_URL, identity_id + scope + role))
        request("PUT", f"https://management.azure.com{identifier}?api-version=2022-04-01", {"properties": {
            "principalId": owned["principalId"], "principalType": "ServicePrincipal",
            "roleDefinitionId": f"/subscriptions/{state['subscription_id']}/providers/Microsoft.Authorization/roleDefinitions/{role}",
        }})
        owned["roleAssignmentIds"].append(identifier)
        save_state(OWNED_STATE, owned)
    values = {
        "AZURE_CLIENT_ID": identity["properties"]["clientId"], "AZURE_TENANT_ID": state["tenant_id"],
        "AZURE_SUBSCRIPTION_ID": state["subscription_id"],
        "AUTONOMY_TARGET_STATE": json.dumps(state),
        "AUTONOMY_TARGET_CONFIGURATION": (RUNTIME / ".azure/config.env").read_text(),
    }
    for name, value in values.items():
        github("secret", "set", name, "--repo", repository, "--env", ENVIRONMENT, value=value)
    print("Environment secrets and scoped OIDC identity configured; no credential values printed.")


def cleanup(confirm: bool) -> None:
    owned = json.loads(OWNED_STATE.read_text())
    context = azure("account", "show")
    if context["tenantId"] != owned["tenant_id"] or context["id"] != owned["subscription_id"]:
        raise ValueError("OIDC cleanup context mismatch")
    identity = request("GET", f"https://management.azure.com{owned['identityId']}?api-version=2023-01-31")
    if identity.get("tags", {}).get("purpose") != owned["marker"] or identity["properties"]["principalId"] != owned["principalId"]:
        raise ValueError("OIDC cleanup ownership mismatch")
    print("Targets: only the owned pipeline identity, federation, role assignments and environment secrets.")
    if not confirm:
        return
    for identifier in owned["roleAssignmentIds"]:
        role = request("GET", f"https://management.azure.com{identifier}?api-version=2022-04-01")
        if role["properties"]["principalId"] != owned["principalId"]:
            raise ValueError("OIDC role ownership mismatch")
        request("DELETE", f"https://management.azure.com{identifier}?api-version=2022-04-01")
    request("DELETE", f"https://management.azure.com{owned['identityId']}?api-version=2023-01-31")
    for name in ["AZURE_CLIENT_ID", "AZURE_TENANT_ID", "AZURE_SUBSCRIPTION_ID", "AUTONOMY_TARGET_STATE", "AUTONOMY_TARGET_CONFIGURATION"]:
        github("secret", "delete", name, "--repo", owned["repository"], "--env", owned["environment"])
    OWNED_STATE.rename(OWNED_STATE.with_suffix(".cleaned.json"))
    print("Owned pipeline access removed; existing workload identity and resources were not deleted.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["setup", "cleanup"])
    parser.add_argument("--repo")
    parser.add_argument("--confirm", action="store_true")
    arguments = parser.parse_args()
    if arguments.command == "setup":
        if not arguments.repo:
            parser.error("setup requires --repo")
        setup(arguments.repo)
    else:
        cleanup(arguments.confirm)


if __name__ == "__main__":
    main()