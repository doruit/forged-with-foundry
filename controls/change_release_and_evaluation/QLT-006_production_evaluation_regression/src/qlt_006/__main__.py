"""QLT-006 command line (runs on top of the CHG-002 deployment).

    python -m src.qlt_006 check            # evaluate the live agent and decide
    python -m src.qlt_006 degrade          # scenario: publish an instruction edit outside the model gate
    python -m src.qlt_006 restore          # republish the released definition
    python -m src.qlt_006 cleanup          # delete QLT-006 evaluations, close demo issues
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from . import AGENT_ID
from . import baseline as baseline_mod
from . import contract
from .evidence import envelope, write
from .policy import Decision, decide

CONTROL_DIR = Path(__file__).resolve().parents[2]
CHG_002_STATE = CONTROL_DIR.parent / "CHG-002_model_version_changed_without_regression_test" / ".state" / "env"
JUDGE = os.environ.get("CHG002_JUDGE_DEPLOYMENT", "chg002-judge")
DEGRADED_INSTRUCTIONS = (
    "You are Contoso's customer support assistant. Keep every answer to one short, friendly sentence. "
    "Do not quote time limits, amounts or conditions; tell customers a colleague will check their case."
)


def endpoint(name: str) -> str:
    value = os.environ.get(name)
    if not value and CHG_002_STATE.is_file():
        for line in CHG_002_STATE.read_text().splitlines():
            if line.startswith(f"{name}="):
                value = line.split("=", 1)[1]
    if not value:
        raise SystemExit(f"{name} not set and not found in the CHG-002 state; deploy CHG-002 first.")
    return value


def client(name: str):
    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    return AIProjectClient(endpoint=endpoint(name), credential=DefaultAzureCredential())


def cmd_check(args) -> int:
    from .evaluation import counts_for, load_dataset, run_live

    declaration = contract.load()
    record = {"agent": AGENT_ID, "contract": {"status": declaration.status, "sha256": declaration.sha256}}
    decision: Decision
    if declaration.status != "valid":
        decision = Decision("measurement_failed", "qlt_006_contract_invalid")
        return finish(record, decision, declaration, route=False)
    base, reason = baseline_mod.load(declaration.baseline_record)
    if base is None:
        decision = Decision("measurement_failed", reason)
        return finish(record, decision, declaration, route=not args.no_route)

    evaluators = list(base.record["evaluators"])
    eval_id, run_id = base.record["evaluationRunId"].split("/", 1)
    with client("EVAL_ENDPOINT") as eval_project:
        recomputed = {n: c.pass_rate for n, c in counts_for(eval_project.get_openai_client(), eval_id, run_id, evaluators).items()}
    record["baseline"] = {
        "record_sha256": base.sha256,
        "evaluation_run_id": base.record["evaluationRunId"],
        "pass_rates": base.rates,
        "verified_against_foundry": baseline_mod.matches_foundry(base, {n: round(r, 4) for n, r in recomputed.items()}),
    }
    if not record["baseline"]["verified_against_foundry"]:
        decision = Decision("measurement_failed", "qlt_006_baseline_not_confirmed_by_foundry")
        return finish(record, decision, declaration, route=not args.no_route)

    rows = load_dataset(base.dataset_path)
    with client("PROD_ENDPOINT") as prod:
        latest = prod.agents.get(AGENT_ID).versions.latest
        live_version, live_model = str(latest.version), latest.definition.model
        openai_client = prod.get_openai_client()
        print(f"Evaluating live {AGENT_ID} version {live_version} on {live_model} ({len(rows)} queries)...")
        live_eval, live_run, status = run_live(openai_client, agent=AGENT_ID, version=live_version, rows=rows, evaluators=evaluators, judge=JUDGE)
        live = counts_for(openai_client, live_eval, live_run, evaluators) if status == "completed" else {}
    record["live"] = {
        "agent_version": live_version,
        "model": live_model,
        "released_version": base.record["production"]["agentVersion"],
        "matches_release": live_version == base.record["production"]["agentVersion"],
        "evaluation_run_id": f"{live_eval}/{live_run}",
        "status": status,
    }
    if status != "completed":
        decision = Decision("measurement_failed", "qlt_006_evaluation_unavailable")
    else:
        decision = decide(base.rates, live, threshold_pp=declaration.threshold_pp,
                          min_scored_items=declaration.min_scored_items, dataset_items=len(rows))
    return finish(record, decision, declaration, route=not args.no_route)


def finish(record: dict, decision: Decision, declaration, *, route: bool) -> int:
    record.update(decision=decision.outcome, reason=decision.reason, deltas_pp=decision.deltas_pp,
                  live_rates=decision.live_rates, threshold_pp=declaration.threshold_pp)
    record = envelope(record)
    if decision.outcome != "within_tolerance" and route and declaration.issue_repository:
        from .route import open_issue

        try:
            record["governance_action"] = open_issue(declaration.issue_repository, record)
        except (subprocess.CalledProcessError, FileNotFoundError, ValueError) as error:
            record["governance_action"] = {"verified": False, "error_class": type(error).__name__}
    path = write(record)
    print(json.dumps({k: record.get(k) for k in ("decision", "reason", "deltas_pp", "live_rates", "governance_action")}, indent=2))
    print(f"Evidence: {path.relative_to(CONTROL_DIR) if path.is_relative_to(CONTROL_DIR) else path}")
    if record.get("governance_action", {}).get("verified") is False:
        return 2
    return 0 if decision.outcome == "within_tolerance" else 1


def _publish(instructions: str | None, version: str | None) -> int:
    from azure.ai.projects.models import PromptAgentDefinition

    with client("PROD_ENDPOINT") as prod:
        source = prod.agents.get_version(AGENT_ID, version) if version else prod.agents.get(AGENT_ID).versions.latest
        definition = PromptAgentDefinition(model=source.definition.model,
                                           instructions=instructions or source.definition.instructions)
        new = prod.agents.create_version(agent_name=AGENT_ID, definition=definition,
                                         description="QLT-006 demo scenario" if instructions else f"QLT-006 restore of version {version}")
    print(f"Published {AGENT_ID} version {new.version} on {definition.model}")
    return 0


def cmd_degrade(args) -> int:
    return _publish(DEGRADED_INSTRUCTIONS, None)


def cmd_restore(args) -> int:
    declaration = contract.load()
    base, reason = baseline_mod.load(declaration.baseline_record) if declaration.baseline_record else (None, "")
    if base is None:
        raise SystemExit(f"Cannot restore: {reason or declaration.status}")
    return _publish(None, base.record["production"]["agentVersion"])


def cmd_cleanup(args) -> int:
    from .evaluation import EVAL_PREFIX
    from .route import LABELS

    deleted = 0
    with client("PROD_ENDPOINT") as prod:
        openai_client = prod.get_openai_client()
        for item in openai_client.evals.list(limit=100):
            if (item.name or "").startswith(EVAL_PREFIX):
                openai_client.evals.delete(item.id)
                deleted += 1
    remaining = [e for e in prod_evals() if (e or "").startswith(EVAL_PREFIX)]
    declaration = contract.load()
    closed = 0
    if declaration.issue_repository:
        for label in LABELS.values():
            out = subprocess.run(["gh", "issue", "list", "-R", declaration.issue_repository, "--label", label,
                                  "--state", "open", "--json", "number"], capture_output=True, text=True)
            for issue in json.loads(out.stdout or "[]"):
                subprocess.run(["gh", "issue", "close", str(issue["number"]), "-R", declaration.issue_repository,
                                "--comment", "Closed by QLT-006 demo cleanup."], check=True, capture_output=True)
                closed += 1
    print(f"Deleted {deleted} QLT-006 evaluation(s); {len(remaining)} remain. Closed {closed} demo issue(s).")
    return 0 if not remaining else 1


def prod_evals() -> list[str]:
    with client("PROD_ENDPOINT") as prod:
        return [e.name for e in prod.get_openai_client().evals.list(limit=100)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.qlt_006", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="evaluate the live agent against the release baseline")
    check.add_argument("--no-route", action="store_true", help="decide and record evidence without opening an issue")
    check.set_defaults(func=cmd_check)
    sub.add_parser("degrade", help="scenario: publish an instruction edit outside the model gate").set_defaults(func=cmd_degrade)
    sub.add_parser("restore", help="republish the released definition").set_defaults(func=cmd_restore)
    sub.add_parser("cleanup", help="delete QLT-006 evaluations and close demo issues").set_defaults(func=cmd_cleanup)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
