"""Configure one control-owned Entra application and App Service Easy Auth."""

from __future__ import annotations

from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from deploy import arm_configuration_url, request, save_state

GRAPH = "https://graph.microsoft.com/v1.0"
OPS_ROLE = str(uuid5(NAMESPACE_URL, "forgedwithfoundry:AUT-002:OpsManager"))
USER_ROLE = str(uuid5(NAMESPACE_URL, "forgedwithfoundry:AUT-002:DemoUser"))


def app_roles() -> list[dict]:
    return [{
        "id": role_id, "allowedMemberTypes": ["User"], "isEnabled": True,
        "displayName": name, "value": name, "description": description,
    } for role_id, name, description in [
        (OPS_ROLE, "OpsManager", "Approve the exact pending synthetic ACS action."),
        (USER_ROLE, "DemoUser", "Request a synthetic action but do not approve it."),
    ]]


def web_settings(state: dict) -> dict:
    return {
        "redirectUris": [f"{state['webAppUrl']}/.auth/login/aad/callback"],
        "implicitGrantSettings": {"enableIdTokenIssuance": True, "enableAccessTokenIssuance": False},
    }


def configure(configuration: dict, state: dict, state_path: Path) -> None:
    marker = f"Forged with Foundry AUT-002; resource={state['webAppId']}"
    if not state.get("application_object_id"):
        application = request("POST", f"{GRAPH}/applications", {
            "displayName": f"{state['webAppName']}-login", "signInAudience": "AzureADMyOrg",
            "notes": marker, "appRoles": app_roles(),
            "web": web_settings(state),
        })
        state.update(application_object_id=application["id"], application_client_id=application["appId"])
        save_state(state_path, state)
    application_url = f"{GRAPH}/applications/{state['application_object_id']}"
    application = request("GET", application_url)
    if application.get("notes") != marker or application["appId"] != state["application_client_id"]:
        raise ValueError("Entra application ownership mismatch")
    request("PATCH", application_url, {"web": web_settings(state), "appRoles": app_roles()})
    if not state.get("service_principal_id"):
        principal = request("POST", f"{GRAPH}/servicePrincipals", {
            "appId": state["application_client_id"], "appRoleAssignmentRequired": True,
            "tags": ["ForgedWithFoundry", "AUT-002"],
        })
        state["service_principal_id"] = principal["id"]
        save_state(state_path, state)
    principal_url = f"{GRAPH}/servicePrincipals/{state['service_principal_id']}"
    principal = request("GET", principal_url)
    if principal["appId"] != state["application_client_id"] or "AUT-002" not in principal.get("tags", []):
        raise ValueError("Entra service principal ownership mismatch")
    request("PATCH", principal_url, {"appRoleAssignmentRequired": True})
    assigned = request("GET", f"{principal_url}/appRoleAssignedTo")["value"]
    for user_id, role_id in [(configuration["AUT002_APPROVER_ID"], OPS_ROLE), (configuration.get("AUT002_TEST_USER_ID"), USER_ROLE)]:
        if user_id and not any(item["principalId"] == user_id and item["appRoleId"] == role_id for item in assigned):
            request("POST", f"{principal_url}/appRoleAssignedTo", {
                "principalId": user_id, "resourceId": state["service_principal_id"], "appRoleId": role_id,
            })
    credentials_url = f"{application_url}/federatedIdentityCredentials"
    expected = {
        "name": "aut002-webapp-identity", "issuer": f"https://login.microsoftonline.com/{state['tenant_id']}/v2.0",
        "subject": state["identityPrincipalId"], "audiences": ["api://AzureADTokenExchange"],
    }
    existing = request("GET", credentials_url)["value"]
    credential = next((item for item in existing if item["name"] == expected["name"]), None)
    if credential is None:
        request("POST", credentials_url, expected)
    elif any(credential[key] != value for key, value in expected.items()):
        raise ValueError("Federated identity ownership mismatch")
    request("PUT", arm_configuration_url(state, "authsettingsV2"), {"properties": {
        "platform": {"enabled": True, "runtimeVersion": "~1"},
        "globalValidation": {"requireAuthentication": True, "unauthenticatedClientAction": "RedirectToLoginPage", "redirectToProvider": "azureactivedirectory"},
        "httpSettings": {"requireHttps": True},
        "login": {"tokenStore": {"enabled": True}, "cookieExpiration": {"convention": "FixedTime", "timeToExpiration": "00:05:00"}},
        "identityProviders": {"azureActiveDirectory": {
            "enabled": True,
            "registration": {"openIdIssuer": expected["issuer"], "clientId": state["application_client_id"], "clientSecretSettingName": "OVERRIDE_USE_MI_FIC_ASSERTION_CLIENTID"},
            "validation": {"allowedAudiences": [state["application_client_id"]]},
        }},
    }})
    print("Entra application, user roles and secretless App Service authentication configured.")