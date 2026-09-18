"""Regression check for Azure Policy demo coexistence (governance-contract
review, 2026-09-18): VAL-PRE-001 and VAL-PRE-002 both trigger on
tags['goLiveRequested']=='true' in the same resource group. Without an
explicit control-id selector, each policy would also evaluate -- and could
deny -- a request that was never meant for it, because it lacks the OTHER
control's required tag. Each policy definition must scope its `if` clause
to its own `tags['control-id']` value so the two demos coexist safely in
one resource group. See docs/governance-contract.md#azure-policy-coexistence.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_POLICY_FILES = {
    "VAL-PRE-001": REPOSITORY_ROOT
    / "controls/value_adoption_and_finops/VAL-PRE-001_value_hypothesis_missing/infra/policy-definition.bicep",
    "VAL-PRE-002": REPOSITORY_ROOT
    / "controls/value_adoption_and_finops/VAL-PRE-002_kpi_baseline_missing/infra/policy-definition.bicep",
}

requires_az_bicep = pytest.mark.skipif(shutil.which("az") is None, reason="Azure CLI (with the bicep extension) is not installed")


def _compile_policy_rule(bicep_path: Path) -> dict:
    result = subprocess.run(
        ["az", "bicep", "build", "--file", str(bicep_path), "--stdout"],
        capture_output=True,
        text=True,
        check=True,
    )
    template = json.loads(result.stdout)
    return template["resources"][0]["properties"]["policyRule"]


def _all_of_conditions(policy_rule: dict) -> list[dict]:
    return policy_rule["if"]["allOf"]


@requires_az_bicep
def test_each_policy_scopes_its_deny_rule_to_its_own_control_id() -> None:
    for control_id, bicep_path in _POLICY_FILES.items():
        policy_rule = _compile_policy_rule(bicep_path)
        conditions = _all_of_conditions(policy_rule)
        selector = next((c for c in conditions if c.get("field") == "tags['control-id']"), None)
        assert selector is not None, f"{control_id}'s policy is missing a control-id selector condition"
        assert selector.get("equals") == control_id, f"{control_id}'s policy selector matches the wrong control id"


@requires_az_bicep
def test_policies_trigger_on_the_same_shared_goLiveRequested_tag() -> None:
    """Confirms the scenario this regression check protects against is real:
    both policies genuinely share the same broad trigger tag, so the
    control-id selector above is the only thing preventing cross-talk."""
    for bicep_path in _POLICY_FILES.values():
        policy_rule = _compile_policy_rule(bicep_path)
        conditions = _all_of_conditions(policy_rule)
        trigger = next((c for c in conditions if c.get("field") == "tags['goLiveRequested']"), None)
        assert trigger is not None
        assert trigger.get("equals") == "true"
