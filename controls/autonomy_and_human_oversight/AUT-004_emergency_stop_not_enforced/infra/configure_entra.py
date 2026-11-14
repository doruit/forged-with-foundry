"""Configure one control-owned Entra application and secretless App Service sign-in."""

from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5

from deploy import request

GRAPH = "https://graph.microsoft.com/v1.0"
ROLE_ID = str(uuid5(NAMESPACE_URL, "forgedwithfoundry:AUT-004:SupportOperator"))


def configure(state: dict, operator: str, save_state) -> None:
    marker = f"Forged with Foundry AUT-004; resource={state['webAppId']}"
    web = {
        "redirectUris": [f"{state['webAppUrl']}/.auth/login/aad/callback"],
        "implicitGrantSettings": {"enableIdTokenIssuance": True, "enableAccessTokenIssuance": False},
    }
    roles = [{
        "id": ROLE_ID, "allowedMemberTypes": ["User"], "isEnabled": True, "value": "SupportOperator",
        "displayName": "SupportOperator", "description": "Use the synthetic AUT-004 support agent.",
    }]
    if not state.get("application_object_id"):
        application = request("POST", f"{GRAPH}/applications", {
            "displayName": f"{state['webAppName']}-login", "signInAudience": "AzureADMyOrg",
            "notes": marker, "appRoles": roles, "web": web,
        })
        state.update(application_object_id=application["id"], application_client_id=application["appId"])
        save_state(state)
    application_url = f"{GRAPH}/applications/{state['application_object_id']}"
    application = request("GET", application_url)
    if application.get("notes") != marker or application["appId"] != state["application_client_id"]:
        raise ValueError("Entra application ownership mismatch")
    request("PATCH", application_url, {"web": web, "appRoles": roles})
    if not state.get("service_principal_id"):
        principal = request("POST", f"{GRAPH}/servicePrincipals", {
            "appId": state["application_client_id"], "appRoleAssignmentRequired": True,
            "tags": ["ForgedWithFoundry", "AUT-004"],
        })
        state["service_principal_id"] = principal["id"]
        save_state(state)
    principal_url = f"{GRAPH}/servicePrincipals/{state['service_principal_id']}"
    assigned = request("GET", f"{principal_url}/appRoleAssignedTo")["value"]
    if not any(item["principalId"] == operator and item["appRoleId"] == ROLE_ID for item in assigned):
        request("POST", f"{principal_url}/appRoleAssignedTo", {
            "principalId": operator, "resourceId": state["service_principal_id"], "appRoleId": ROLE_ID,
        })
    credentials_url = f"{application_url}/federatedIdentityCredentials"
    expected = {
        "name": "aut004-webapp-identity", "issuer": f"https://login.microsoftonline.com/{state['tenant_id']}/v2.0",
        "subject": state["identityPrincipalId"], "audiences": ["api://AzureADTokenExchange"],
    }
    existing = request("GET", credentials_url)["value"]
    if not any(item["name"] == expected["name"] for item in existing):
        request("POST", credentials_url, expected)
    request("PUT", f"https://management.azure.com{state['webAppId']}/config/authsettingsV2?api-version=2024-11-01", {"properties": {
        "platform": {"enabled": True, "runtimeVersion": "~1"},
        "globalValidation": {"requireAuthentication": True, "unauthenticatedClientAction": "RedirectToLoginPage",
                             "redirectToProvider": "azureactivedirectory"},
        "httpSettings": {"requireHttps": True},
        "login": {"tokenStore": {"enabled": True}},
        "identityProviders": {"azureActiveDirectory": {
            "enabled": True,
            "registration": {"openIdIssuer": expected["issuer"], "clientId": state["application_client_id"],
                             "clientSecretSettingName": "OVERRIDE_USE_MI_FIC_ASSERTION_CLIENTID"},
            "validation": {"allowedAudiences": [state["application_client_id"]]},
        }},
    }})
    print("Entra application, SupportOperator role and secretless App Service sign-in configured.")
