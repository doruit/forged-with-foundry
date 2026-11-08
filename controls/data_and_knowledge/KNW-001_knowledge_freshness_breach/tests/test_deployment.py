import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("knw001_deploy", ROOT / "infra/deploy.py")
deploy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(deploy)


def state():
    prefix = "/subscriptions/synthetic-subscription/resourceGroups/rg-knw001-demo/providers/"
    return {
        "control_id": "KNW-001", "subscription_id": "synthetic-subscription",
        "phase": "deployed",
        "outputs": {
            "searchId": prefix + "Microsoft.Search/searchServices/synthetic-search",
            "storageId": prefix + "Microsoft.Storage/storageAccounts/syntheticstorage",
        },
    }


def test_cleanup_targets_are_limited_to_the_two_control_resources():
    assert len(deploy.cleanup_targets(state(), "synthetic-subscription")) == 2


def test_search_only_cleanup_target_preserves_storage():
    manifest = state()

    target = deploy.search_cleanup_target(manifest, "synthetic-subscription")

    assert target == manifest["outputs"]["searchId"]
    assert target != manifest["outputs"]["storageId"]


def test_state_reconciliation_recovers_tagged_storage_only_foundation():
    resource = {
        "type": "Microsoft.Storage/storageAccounts",
        "id": "/subscriptions/synthetic-subscription/resourceGroups/rg-knw001-demo/providers/Microsoft.Storage/storageAccounts/syntheticstorage",
        "tags": {"control-id": "KNW-001", "purpose": deploy.PURPOSE},
    }

    reconciled = deploy.state_from_resources(
        [resource], "synthetic-tenant", "synthetic-subscription"
    )

    assert reconciled["phase"] == "storage_only"
    assert reconciled["outputs"] == {"storageId": resource["id"]}


def test_state_reconciliation_rejects_unexpected_control_owned_resources():
    resource = {
        "type": "Microsoft.Sql/servers",
        "id": "/subscriptions/synthetic-subscription/resourceGroups/rg-knw001-demo/providers/Microsoft.Sql/servers/knw001",
        "tags": {"control-id": "KNW-001", "purpose": deploy.PURPOSE},
    }

    with pytest.raises(ValueError, match="Unexpected KNW-001-owned"):
        deploy.state_from_resources(
            [resource], "synthetic-tenant", "synthetic-subscription"
        )


def test_storage_only_cleanup_state_targets_storage_only():
    manifest = state()
    manifest["phase"] = "storage_only"
    manifest["outputs"].pop("searchId")

    targets = deploy.cleanup_targets(manifest, "synthetic-subscription")

    assert targets == [manifest["outputs"]["storageId"]]


@pytest.mark.parametrize("field,value", [
    ("control_id", "OTHER-001"),
    ("subscription_id", "another-subscription"),
    ("phase", "deploying"),
])
def test_cleanup_rejects_wrong_control_context_or_incomplete_deployment(field, value):
    manifest = state()
    manifest[field] = value
    with pytest.raises(ValueError):
        deploy.cleanup_targets(manifest, "synthetic-subscription")


@pytest.mark.parametrize("target", [
    "/subscriptions/synthetic-subscription/resourceGroups/shared/providers/Microsoft.Search/searchServices/shared",
    "/subscriptions/synthetic-subscription/resourceGroups/rg-knw001-demo",
    "/subscriptions/synthetic-subscription/resourceGroups/rg-knw001-demo/providers/Microsoft.Search/searchServices/synthetic-search/indexes/extra",
])
def test_cleanup_rejects_shared_group_group_deletion_and_child_targets(target):
    manifest = state()
    manifest["outputs"]["searchId"] = target
    with pytest.raises(ValueError):
        deploy.cleanup_targets(manifest, "synthetic-subscription")


def test_ownership_requires_both_tags():
    assert deploy.owned({"tags": {"control-id": "KNW-001", "purpose": deploy.PURPOSE}})
    assert not deploy.owned({"tags": {"control-id": "KNW-001"}})
    assert not deploy.owned({"tags": None})


def test_pending_deployment_state_does_not_replace_successful_cleanup_state(tmp_path):
    stable = tmp_path / "foundation.json"
    pending = tmp_path / "foundation.pending.json"
    stable.write_text('{"phase":"deployed"}')

    deploy.save_state({"phase": "failed"}, pending)

    assert stable.read_text() == '{"phase":"deployed"}'
    assert '"phase": "failed"' in pending.read_text()
    assert pending.stat().st_mode & 0o777 == 0o600


def test_template_cannot_select_paid_search_or_another_region():
    template = (ROOT / "infra/resources.bicep").read_text()
    entry = (ROOT / "infra/main.bicep").read_text()
    assert "@allowed(['free', 'standard'])" in template
    assert "param searchSku string = 'free'" in template
    assert "sku: { name: searchSku }" in template
    assert "allowSharedKeyAccess: false" in template
    assert "disableLocalAuth: true" in template
    assert "@allowed(['westeurope'])" in entry
    assert "@allowed(['rg-knw001-demo'])" in entry


def test_s1_deployment_argument_is_explicit_and_opt_in():
    args = deploy.deployment_arguments("synthetic-principal", "s1")

    assert "searchSku=standard" in args


def test_sweden_search_location_preserves_storage_region():
    args = deploy.deployment_arguments("synthetic-principal", "s1", "swedencentral")
    assert "searchLocation=swedencentral" in args
    assert args[args.index("--location") + 1] == "westeurope"
    template = (ROOT / "infra/resources.bicep").read_text()
    assert "location: searchLocation" in template
    assert "location: location" in template
    assert "searchLocation: searchLocation" in (ROOT / "infra/main.bicep").read_text()