"""Credential-free candidate gate.

Runs in CI on the deployment candidate only: the governance contract, the
model deployment parameters and the evaluation dataset. It never calls
Azure. It re-applies the regression policy to the recorded evidence and
binds that evidence to the exact model asset ID that would be deployed.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from . import AGENT_ID, CONTROL_ID
from .policy import RegressionPolicy, decide_from_rates

REPOSITORY = Path(__file__).resolve().parents[5]
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))

from scripts.validate_governance_contract import (  # noqa: E402
    ContractReadError,
    parse_contract_bytes,
    read_contract_bytes,
    validate_contract,
    validate_control_entry,
)

CONTRACT_RELATIVE = Path(".fwf") / "agents" / AGENT_ID / "governance.yaml"
DEPLOYMENT_FILE = "model-deployment.json"


def asset_id(deployment: dict) -> str:
    model = deployment["model"]
    return f"azureml://registries/{deployment['registry']}/models/{model['name']}/versions/{model['version']}"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _result(decision: str, reason: str, **extra) -> dict:
    return {"control_id": CONTROL_ID, "decision": decision, "reason": reason, **extra}


def _entry_without_test(data: dict) -> bool:
    """True when CHG-002 is declared but no regression test was recorded for the candidate."""

    controls = (data.get("spec") or {}).get("controls") or []
    entries = [c for c in controls if isinstance(c, dict) and c.get("id") == CONTROL_ID]
    return len(entries) == 1 and "regressionTest" not in (entries[0].get("evidence") or {})


def load_entry(root: Path) -> tuple[dict | None, str | None, str]:
    """Return (CHG-002 evidence, contract sha256, reason) using the shared validator."""

    path = root / CONTRACT_RELATIVE
    try:
        raw = read_contract_bytes(path)
        data = parse_contract_bytes(raw, source=f"{CONTROL_ID} contract")
    except (ContractReadError, OSError, ValueError):
        return None, None, "chg_002_contract_unreadable"
    digest = hashlib.sha256(raw).hexdigest()
    if validate_contract(data, agent_dir_name=AGENT_ID):
        if _entry_without_test(data):
            return None, digest, "chg_002_regression_test_missing"
        return None, digest, "chg_002_contract_invalid"
    entry, errors = validate_control_entry(CONTROL_ID, data)
    if entry is None:
        return None, digest, "chg_002_not_declared"
    if errors:
        return None, digest, "chg_002_contract_invalid"
    return entry["evidence"], digest, ""


def check_candidate(root: Path) -> dict:
    evidence, contract_sha, reason = load_entry(root)
    if evidence is None:
        return _result("blocked", reason, contract_sha256=contract_sha)

    try:
        deployment = json.loads((root / DEPLOYMENT_FILE).read_text(encoding="utf-8"))
        candidate_asset = asset_id(deployment)
        candidate_name = deployment["deploymentName"]
        upgrade = deployment["versionUpgradeOption"]
    except (OSError, ValueError, KeyError, TypeError):
        return _result("blocked", "chg_002_deployment_candidate_unreadable", contract_sha256=contract_sha)

    declared = evidence["candidate"]
    bound = {"modelAssetId": candidate_asset, "deploymentName": candidate_name, "versionUpgradeOption": upgrade}
    common = {"contract_sha256": contract_sha, "candidate": bound}
    if upgrade != "NoAutoUpgrade":
        return _result("blocked", "chg_002_auto_upgrade_not_allowed", **common)
    if (declared["modelAssetId"], declared["deploymentName"]) != (candidate_asset, candidate_name):
        return _result("blocked", "chg_002_evidence_not_for_this_candidate", **common)

    policy = RegressionPolicy.from_evidence(evidence)
    dataset = root / policy.dataset_path
    if not dataset.is_file() or sha256_file(dataset) != policy.dataset_sha256:
        return _result("blocked", "chg_002_dataset_changed", **common)

    test = evidence["regressionTest"]
    if test["status"] != "passed":
        return _result("blocked", "chg_002_regression_test_failed", **common)
    decision = decide_from_rates(
        policy, test["passRates"], items_total=test["itemsTotal"], items_scored=test["itemsScored"]
    )
    if not decision.allowed:
        return _result("blocked", "chg_002_recorded_evidence_inconsistent", detail=decision.reason, **common)
    return _result(
        "release_allowed",
        decision.reason,
        evaluation_run_id=test["evaluationRunId"],
        pass_rates=decision.pass_rates,
        **common,
    )
