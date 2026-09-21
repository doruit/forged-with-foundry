"""Cleanup must refuse targets outside this control's explicit ownership."""

from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("val001_cleanup", Path(__file__).resolve().parents[1] / "infra/cleanup.py")
cleanup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cleanup)


def resources():
    prefix = "/subscriptions/test/resourceGroups/demo/providers/"
    tags = {"control-id": "VAL-001", "purpose": "synthetic-kpi-demo"}
    workspace = {"id": prefix + "Microsoft.OperationalInsights/workspaces/log-val001-test",
                 "name": "log-val001-test", "type": "Microsoft.OperationalInsights/workspaces", "tags": tags.copy()}
    insights = {"id": prefix + "Microsoft.Insights/components/appi-val001-test",
                "name": "appi-val001-test", "type": "Microsoft.Insights/components", "tags": tags.copy(),
                "properties": {"WorkspaceResourceId": workspace["id"]}}
    return insights, workspace


def test_given_owned_resources_when_checked_then_accepted():
    cleanup.validate_resources("test", "demo", *resources())


def test_given_deleted_metadata_when_checked_then_only_live_state_remains():
    response = {"data": [{"status": "deleted"}, {"status": "Stopped"}, {"status": "Running"}]}

    assert cleanup.remaining_sessions(response) == [{"status": "Stopped"}, {"status": "Running"}]


@pytest.mark.parametrize("mutation", ["tag", "name", "group", "type", "link", "purpose"])
def test_given_wrong_ownership_when_checked_then_refused(mutation):
    insights, workspace = deepcopy(resources())
    if mutation == "tag":
        insights["tags"]["control-id"] = "OTHER"
    elif mutation == "purpose":
        insights["tags"]["purpose"] = "production"
    elif mutation == "name":
        insights["name"] = "shared"
    elif mutation == "group":
        insights["id"] = insights["id"].replace("/demo/", "/shared/")
    elif mutation == "type":
        workspace["type"] = "Microsoft.Resources/resourceGroups"
    else:
        insights["properties"]["WorkspaceResourceId"] = "/shared/workspace"

    with pytest.raises(ValueError):
        cleanup.validate_resources("test", "demo", insights, workspace)