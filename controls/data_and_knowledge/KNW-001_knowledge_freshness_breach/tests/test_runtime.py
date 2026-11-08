import importlib.util
from pathlib import Path
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("knw001_runtime", ROOT / "infra/runtime.py")
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)
deploy = runtime.foundation

PREFIX = "/subscriptions/synthetic-subscription/resourceGroups/rg-knw001-demo/providers/"
TAGS = {"control-id": "KNW-001", "purpose": deploy.PURPOSE}


def state(**overrides):
    return {
        "control_id": "KNW-001", "subscription_id": "synthetic-subscription", "phase": "configured",
        "tenant_id": "synthetic-tenant", "owner_object_id": "owner-oid",
        "functionPrincipalId": "monitor-oid", "application_client_id": "app-client-id",
        "functionAppId": PREFIX + "Microsoft.Web/sites/func-knw001",
        "planId": PREFIX + "Microsoft.Web/serverfarms/plan-knw001",
        "foundryId": PREFIX + "Microsoft.CognitiveServices/accounts/aif-knw001",
        **overrides,
    }


def test_runtime_cleanup_targets_only_control_runtime_resources():
    targets = runtime.cleanup_targets(state(), "synthetic-subscription")

    assert [target.split("/")[7] for target in targets] == ["sites", "serverfarms", "accounts"]


def test_redeploy_after_cleanup_does_not_reuse_deleted_entra_application():
    cleaned = state(phase="cleaned", application_object_id="deleted-app", service_principal_id="deleted-sp")
    live = state(application_object_id="live-app")

    assert runtime.carried_state(cleaned) == {}
    assert runtime.carried_state(live)["application_object_id"] == "live-app"


@pytest.mark.parametrize("override", [
    {"control_id": "KNW-002"},
    {"subscription_id": "other"},
    {"phase": "cleaned"},
    {"foundryId": "/subscriptions/synthetic-subscription/resourceGroups/rg-forged-with-foundry/providers/Microsoft.CognitiveServices/accounts/shared"},
    {"functionAppId": PREFIX + "Microsoft.Web/sites/func-knw001/slots/staging"},
])
def test_runtime_cleanup_rejects_foreign_shared_or_child_targets(override):
    with pytest.raises(ValueError):
        runtime.cleanup_targets(state(**override), "synthetic-subscription")


def test_easy_auth_admits_only_owner_and_monitor_identity_and_fails_closed():
    settings = runtime.auth_settings(state())["properties"]
    validation = settings["identityProviders"]["azureActiveDirectory"]["validation"]

    assert settings["globalValidation"]["unauthenticatedClientAction"] == "Return401"
    assert settings["globalValidation"]["excludedPaths"] == ["/admin/functions/freshness_timer"]
    assert validation["defaultAuthorizationPolicy"]["allowedPrincipals"]["identities"] == ["owner-oid", "monitor-oid"]
    assert set(validation["allowedAudiences"]) == {"app-client-id", "api://app-client-id"}


def test_function_package_contains_only_runtime_code(tmp_path):
    with zipfile.ZipFile(runtime.build_package(tmp_path)) as package:
        names = set(package.namelist())

    assert {"function_app.py", "host.json", "requirements.txt", "src/knw001/policy.py"} <= names
    assert not any("test" in name or ".azure" in name or "__pycache__" in name for name in names)


def test_foundation_reconcile_ignores_runtime_resources_and_cleanup_waits_for_them():
    resources = [
        {"type": "Microsoft.Storage/storageAccounts", "id": PREFIX + "Microsoft.Storage/storageAccounts/st", "tags": TAGS},
        {"type": "Microsoft.Web/serverFarms", "id": PREFIX + "Microsoft.Web/serverFarms/plan", "tags": TAGS},
        {"type": "Microsoft.CognitiveServices/accounts", "id": PREFIX + "Microsoft.CognitiveServices/accounts/aif", "tags": TAGS},
    ]

    reconciled = deploy.state_from_resources(resources, "synthetic-tenant", "synthetic-subscription")

    assert reconciled["phase"] == "storage_only"
    assert deploy.runtime_present(resources, {}) is True
    assert deploy.runtime_present(resources[:1], {"phase": "cleaned"}) is False
    assert deploy.runtime_present(resources[:1], {"phase": "configured"}) is True


def test_runtime_template_keeps_regions_model_and_connection_scoped():
    template = (ROOT / "infra/runtime.bicep").read_text()

    assert "@allowed(['westeurope'])" in template and "@allowed(['swedencentral'])" in template
    assert "tier: 'FlexConsumption'" in template
    assert "authType: 'AAD'" in template and "isSharedToAll: false" in template
    assert "disableLocalAuth: true" in template
    assert "'gpt-4.1-mini'" in template
    assert "subscription()" not in template


def test_environment_exports_only_non_secret_names_and_endpoints():
    base = {"storageName": "stknw001", "blobEndpoint": "https://stknw001.blob.core.windows.net/",
            "searchEndpoint": "https://srch-knw001.search.windows.net"}
    values = runtime.environment(base, state(
        sourceBlob="vpn-reset-guide.md", searchIndex="knw001-index", searchIndexer="knw001-indexer",
        projectEndpoint="https://aif-knw001.services.ai.azure.com/api/projects/knw-001",
        modelDeploymentName="knw001-gpt-4-1-mini", searchConnectionName="knw001-search",
        policyVersion="knw001-v1", functionAppUrl="https://func-knw001.azurewebsites.net",
    ))

    assert values["KNW001_REVIEW_SCOPE"] == "api://app-client-id/user_impersonation"
    assert values["KNW001_SEARCH_DATASOURCE"] == "knw001-blob"
    assert not any(word in key for key in values for word in ("KEY", "SECRET", "SAS", "TOKEN", "PASSWORD"))
