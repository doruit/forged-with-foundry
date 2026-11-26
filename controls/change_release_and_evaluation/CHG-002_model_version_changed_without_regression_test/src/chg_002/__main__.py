"""CHG-002 command line.

    python -m src.chg_002 gate --root candidate            # credential-free CI gate
    python -m src.chg_002 agent-version --deployment NAME   # create an agent version on a model
    python -m src.chg_002 evaluate --baseline-version N --candidate-version M [--write-contract]
    python -m src.chg_002 release --root candidate          # record the release baseline
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import yaml

from . import AGENT_ID, CONTROL_ID
from .evidence import envelope, now, write

CONTROL_DIR = Path(__file__).resolve().parents[2]
DEFAULT_ROOT = CONTROL_DIR / "candidate"
BASELINE_RECORD = CONTROL_DIR / "release" / "release-baseline.json"


def _print(record: dict) -> None:
    print(json.dumps(record, indent=2))


def cmd_gate(args) -> int:
    from .gate import check_candidate

    result = check_candidate(Path(args.root))
    path = write(envelope("candidate_gate", result))
    _print(result)
    print(f"Evidence: {path.relative_to(CONTROL_DIR)}")
    return 0 if result["decision"] == "release_allowed" else 1


def _project_client():
    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
    if not endpoint:
        raise SystemExit("Set FOUNDRY_PROJECT_ENDPOINT (printed by infra/deploy.sh).")
    return AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential())


def cmd_agent_version(args) -> int:
    from .agent import create_version

    with _project_client() as client:
        version = create_version(client, args.deployment)
    print(f"{AGENT_ID} version {version} uses deployment {args.deployment}")
    return 0


def _regression_policy(root: Path) -> tuple[dict, "object"]:
    """Validate only the regressionPolicy block, so evaluation can run before evidence exists."""

    import jsonschema

    from .gate import CONTRACT_RELATIVE
    from .policy import RegressionPolicy

    schema = json.loads(
        (CONTROL_DIR.parents[2] / "schemas/governance-contract/v1alpha1/controls/CHG-002.schema.json").read_text()
    )
    sub = schema["properties"]["evidence"]["properties"]["regressionPolicy"]
    contract = yaml.safe_load((root / CONTRACT_RELATIVE).read_text(encoding="utf-8"))
    entry = next(c for c in contract["spec"]["controls"] if c.get("id") == CONTROL_ID)
    jsonschema.validate(entry["evidence"]["regressionPolicy"], sub)
    return contract, RegressionPolicy.from_evidence(entry["evidence"])


def cmd_evaluate(args) -> int:
    from .evaluation import collect, create_eval, load_dataset, start_run, wait_for_run
    from .gate import CONTRACT_RELATIVE, DEPLOYMENT_FILE, asset_id, sha256_file
    from .policy import Decision, decide

    root = Path(args.root)
    contract, policy = _regression_policy(root)
    dataset_path = root / policy.dataset_path
    if sha256_file(dataset_path) != policy.dataset_sha256:
        decision = Decision("blocked", "chg_002_dataset_changed")
        _print({"decision": decision.outcome, "reason": decision.reason})
        return 1
    rows = load_dataset(dataset_path)

    with _project_client() as client:
        openai_client = client.get_openai_client()
        eval_id = create_eval(openai_client, f"CHG-002 regression {now()}", policy.required_evaluators, args.judge)
        runs = {}
        for label, version in (("baseline", args.baseline_version), ("candidate", args.candidate_version)):
            run_id = start_run(openai_client, eval_id, AGENT_ID, version, rows, label)
            print(f"Started {label} run {run_id} for {AGENT_ID} version {version}")
            runs[label] = run_id
        results = {}
        for label, run_id in runs.items():
            status = wait_for_run(openai_client, eval_id, run_id)
            results[label] = collect(openai_client, eval_id, run_id, status, policy.required_evaluators, expected=len(rows))
            print(f"{label} run {run_id}: {status}")

    if any(r.status != "completed" for r in results.values()):
        decision = Decision("blocked", "chg_002_evaluation_unavailable")
    else:
        decision = decide(policy, results["baseline"].counts, results["candidate"].counts, len(rows))
    deployment = json.loads((root / DEPLOYMENT_FILE).read_text(encoding="utf-8"))
    record = envelope(
        "regression_evaluation",
        {
            "decision": decision.outcome,
            "reason": decision.reason,
            "agent": AGENT_ID,
            "baseline_version": str(args.baseline_version),
            "candidate_version": str(args.candidate_version),
            "candidate_model_asset_id": asset_id(deployment),
            "eval_id": eval_id,
            "runs": {label: {"run_id": r.run_id, "status": r.status} for label, r in results.items()},
            "pass_rates": decision.pass_rates,
            "items_total": decision.items_total,
            "items_scored": decision.items_scored,
            "dataset_sha256": policy.dataset_sha256,
        },
    )
    path = write(record)
    _print({k: record[k] for k in ("decision", "reason", "pass_rates", "items_total", "items_scored")})
    print(f"Evidence: {path.relative_to(CONTROL_DIR)}")

    if args.write_contract and decision.pass_rates:
        entry = next(c for c in contract["spec"]["controls"] if c.get("id") == CONTROL_ID)
        entry["evidence"]["candidate"] = {
            "agentName": AGENT_ID,
            "agentVersion": str(args.candidate_version),
            "deploymentName": deployment["deploymentName"],
            "modelAssetId": asset_id(deployment),
            "versionUpgradeOption": deployment["versionUpgradeOption"],
        }
        entry["evidence"]["regressionTest"] = {
            "status": "passed" if decision.allowed else "failed",
            "evaluationRunId": f"{eval_id}/{results['candidate'].run_id}",
            "baselineEvaluationRunId": f"{eval_id}/{results['baseline'].run_id}",
            "baselineAgentVersion": str(args.baseline_version),
            "evaluatedAt": record["timestamp"],
            "itemsTotal": decision.items_total,
            "itemsScored": decision.items_scored,
            "passRates": decision.pass_rates,
        }
        (root / CONTRACT_RELATIVE).write_text(yaml.safe_dump(contract, sort_keys=False), encoding="utf-8")
        print(f"Updated {CONTRACT_RELATIVE} with the evaluation evidence for review.")
    return 0 if decision.allowed else 1


def cmd_release(args) -> int:
    from .gate import check_candidate, load_entry

    root = Path(args.root)
    result = check_candidate(root)
    if result["decision"] != "release_allowed":
        _print(result)
        print("Release refused: the candidate gate did not allow it.")
        return 1
    evidence, contract_sha, _ = load_entry(root)
    test, candidate = evidence["regressionTest"], evidence["candidate"]
    record = {
        "controlId": CONTROL_ID,
        "agent": {"name": candidate["agentName"], "evaluatedVersion": candidate["agentVersion"]},
        "production": {"agentVersion": str(args.production_agent_version)},
        "model": {"assetId": candidate["modelAssetId"], "deploymentName": candidate["deploymentName"]},
        "dataset": {
            "path": f"candidate/{evidence['regressionPolicy']['datasetPath']}",
            "sha256": evidence["regressionPolicy"]["datasetSha256"],
        },
        "evaluators": evidence["regressionPolicy"]["requiredEvaluators"],
        "passRates": {name: rates["candidate"] for name, rates in test["passRates"].items()},
        "itemsScored": test["itemsScored"],
        "evaluationRunId": test["evaluationRunId"],
        "releasedAt": now(),
        "contractSha256": contract_sha,
        "accountableRole": evidence["accountableRole"],
    }
    BASELINE_RECORD.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_RECORD.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    path = write(envelope("release", {"decision": "released", "baseline_record": str(BASELINE_RECORD.relative_to(CONTROL_DIR)), **result}))
    print(f"Released {candidate['agentName']} version {candidate['agentVersion']} on {candidate['modelAssetId']}")
    print(f"Release baseline record: {BASELINE_RECORD.relative_to(CONTROL_DIR)}")
    print(f"Evidence: {path.relative_to(CONTROL_DIR)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.chg_002", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    gate = sub.add_parser("gate", help="credential-free candidate gate")
    gate.add_argument("--root", default=str(DEFAULT_ROOT))
    gate.set_defaults(func=cmd_gate)
    agent = sub.add_parser("agent-version", help="create an agent version on a model deployment")
    agent.add_argument("--deployment", required=True)
    agent.set_defaults(func=cmd_agent_version)
    evaluate = sub.add_parser("evaluate", help="run the regression evaluation in Foundry")
    evaluate.add_argument("--root", default=str(DEFAULT_ROOT))
    evaluate.add_argument("--baseline-version", required=True)
    evaluate.add_argument("--candidate-version", required=True)
    evaluate.add_argument("--judge", default=os.environ.get("CHG002_JUDGE_DEPLOYMENT", "chg002-judge"))
    evaluate.add_argument("--write-contract", action="store_true")
    evaluate.set_defaults(func=cmd_evaluate)
    release = sub.add_parser("release", help="record the release baseline after the gate allows it")
    release.add_argument("--root", default=str(DEFAULT_ROOT))
    release.add_argument("--production-agent-version", required=True, help="the new production agent version that uses the released model")
    release.set_defaults(func=cmd_release)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
