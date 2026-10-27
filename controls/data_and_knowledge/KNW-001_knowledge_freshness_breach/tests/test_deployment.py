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


def test_template_cannot_select_paid_search_or_another_region():
    template = (ROOT / "infra/resources.bicep").read_text()
    entry = (ROOT / "infra/main.bicep").read_text()
    assert "sku: { name: 'free' }" in template
    assert "allowSharedKeyAccess: false" in template
    assert "disableLocalAuth: true" in template
    assert "@allowed(['westeurope'])" in entry
    assert "@allowed(['rg-knw001-demo'])" in entry