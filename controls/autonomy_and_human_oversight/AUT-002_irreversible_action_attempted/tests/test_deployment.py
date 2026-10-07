import importlib.util
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

INFRA = Path(__file__).resolve().parents[1] / "infra"
sys.path.insert(0, str(INFRA))
spec = importlib.util.spec_from_file_location("aut002_deploy", INFRA / "deploy.py")
deployment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deployment)


def test_context_mismatch_stops_before_mutation(monkeypatch, tmp_path):
    config = tmp_path / "config.env"
    config.write_text("\n".join(f"{name}=synthetic" for name in [
        "AZURE_TENANT_ID", "AZURE_SUBSCRIPTION_ID", "AZURE_RESOURCE_GROUP", "AZURE_LOCATION", "FOUNDRY_ACCOUNT_NAME", "AUT002_APPROVER_ID",
    ]))
    cli = Mock(return_value={"tenantId": "wrong-tenant", "id": "wrong-subscription"})
    monkeypatch.setattr(deployment, "azure", cli)
    with pytest.raises(ValueError, match="context mismatch"):
        deployment.load_configuration(config)
    cli.assert_called_once_with("account", "show")


def test_package_excludes_identity_configuration_and_evidence(tmp_path):
    import zipfile

    archive = tmp_path / "demo.zip"
    deployment.package(archive)
    with zipfile.ZipFile(archive) as package:
        assert "constraints.txt" in package.namelist()
        assert "src/aut_002/cloud_chat.py" in package.namelist()
        assert not any(".azure" in name or "evidence/" in name for name in package.namelist())


def test_approver_role_is_user_only():
    from configure_entra import app_roles

    roles = app_roles()
    assert {item["value"] for item in roles} == {"OpsManager", "DemoUser"}
    assert all(item["allowedMemberTypes"] == ["User"] for item in roles)


def test_cleanup_rejects_shared_project():
    from cleanup import validate_state

    with pytest.raises(ValueError, match="shared Foundry"):
        validate_state({"control_id": "AUT-002", "tenant_id": "synthetic", "subscription_id": "synthetic",
                        "projectId": "/projects/default-project", "modelId": "/deployments/gpt-5"},
                       {"tenantId": "synthetic", "id": "synthetic"})


def test_cleanup_rejects_wrong_tenant():
    from cleanup import validate_state

    with pytest.raises(ValueError, match="mismatch"):
        validate_state({"control_id": "AUT-002", "tenant_id": "other", "subscription_id": "synthetic"},
                       {"tenantId": "synthetic", "id": "synthetic"})


def test_cleanup_uses_supported_role_assignment_api(monkeypatch):
    import cleanup

    cli = Mock(return_value={})
    monkeypatch.setattr(cleanup, "azure", cli)
    identifier = "/subscriptions/synthetic/providers/Microsoft.Authorization/roleAssignments/synthetic"
    cleanup.existing_resource(identifier)
    cli.assert_called_once_with("resource", "show", "--ids", identifier, "--api-version", "2022-04-01")


def test_code_upload_rejects_another_environment(monkeypatch):
    cli = Mock()
    monkeypatch.setattr(deployment, "azure", cli)
    with pytest.raises(ValueError, match="context mismatch"):
        deployment.upload({"AZURE_TENANT_ID": "target", "AZURE_SUBSCRIPTION_ID": "target"},
                          {"control_id": "AUT-002", "tenant_id": "other", "subscription_id": "other"})
    cli.assert_not_called()


def test_easy_auth_hybrid_flow_does_not_enable_implicit_access_tokens():
    from configure_entra import web_settings

    settings = web_settings({"webAppUrl": "https://synthetic.azurewebsites.net"})
    assert settings["implicitGrantSettings"] == {"enableIdTokenIssuance": True, "enableAccessTokenIssuance": False}


def test_preflight_cannot_be_combined_with_upload(monkeypatch):
    cli = Mock()
    monkeypatch.setattr(deployment, "azure", cli)
    monkeypatch.setattr(sys, "argv", ["deploy.py", "--check", "--code-only"])
    with pytest.raises(SystemExit) as result:
        deployment.main()
    assert result.value.code == 2
    cli.assert_not_called()


def test_directory_cleanup_distinguishes_missing_objects_from_permissions(monkeypatch):
    import cleanup

    monkeypatch.setattr(cleanup, "request", Mock(side_effect=RuntimeError("Request_ResourceNotFound")))
    assert cleanup.existing_directory_object("https://graph.microsoft.com/v1.0/applications/synthetic") is None
    monkeypatch.setattr(cleanup, "request", Mock(side_effect=RuntimeError("Authorization_RequestDenied")))
    with pytest.raises(RuntimeError, match="Denied"):
        cleanup.existing_directory_object("https://graph.microsoft.com/v1.0/applications/synthetic")


def test_code_upload_explicitly_restarts_the_worker(monkeypatch):
    calls = []

    def cli(*arguments):
        calls.append(arguments)
        if arguments[:2] == ("webapp", "show"):
            return {"name": "synthetic-app", "tags": {"control-id": "AUT-002"}}
        return {}

    monkeypatch.setattr(deployment, "azure", cli)
    deployment.upload({"AZURE_TENANT_ID": "synthetic", "AZURE_SUBSCRIPTION_ID": "synthetic", "AZURE_RESOURCE_GROUP": "synthetic"},
                      {"control_id": "AUT-002", "tenant_id": "synthetic", "subscription_id": "synthetic", "webAppId": "synthetic-id",
                       "webAppName": "synthetic-app", "webAppUrl": "https://synthetic.azurewebsites.net"})
    assert calls[-1][-2:] == ("--restart", "true")


def test_runtime_uses_supported_role_only_at_control_project():
    source = (INFRA / "main.bicep").read_text()
    runtime = source.split("resource runtimeRole ", 1)[1].split("resource inferenceRole ", 1)[0]
    assert "scope: project" in runtime
    assert "53ca6127-db72-4b80-b1b0-d745d6d5456d" in runtime
    assert "runtime-foundry-user" in runtime