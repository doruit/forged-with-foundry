"""Command line for TOOL-003.

    python -m src.tool_003 run --scenario <name> [--replay [--replay-approval approve|decline]]
    python -m src.tool_003 approve <request-id>
    python -m src.tool_003 decline <request-id>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import secrets
import sys
from pathlib import Path

from .approval import FileApprovalChannel, ScriptedApprover, approver_reference, decide
from .runner import SCENARIOS, RunAborted, replay_session, run_scenario

CONTROL_ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = CONTROL_ROOT / ".azure" / "deployment.json"
EVIDENCE_DIR = CONTROL_ROOT / "evidence"
APPROVALS_DIR = CONTROL_ROOT / "approvals"


def _reference_key() -> str:
    """Per-deployment key for approver references, kept in the git-ignored state file."""
    if not STATE_PATH.is_file():
        raise RuntimeError(f"No deployment state at {STATE_PATH}; run infra/deploy.sh first.")
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    if not state.get("approval_reference_key"):
        state["approval_reference_key"] = secrets.token_urlsafe(32)
        STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return state["approval_reference_key"]


def _decide(request_id: str, *, approve: bool) -> int:
    try:
        result = decide(APPROVALS_DIR, request_id, approve=approve, approver_ref=approver_reference(_reference_key()))
    except (FileNotFoundError, FileExistsError, ValueError, RuntimeError) as error:
        message = "A decision was already recorded for this request." if isinstance(error, FileExistsError) else str(error)
        print(message, file=sys.stderr)
        return 1
    request = result["request"]
    print(
        f"{'Approved' if approve else 'Declined'}: {request['extra_calls_requested']} extra tool calls for run "
        f"{request['run_id']} (task type {request['task_type']}, approved budget {request['approved_budget']}). "
        f"Recorded as {result['decision']['approver_ref']}."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.tool_003", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Run one scenario through ACS.")
    run.add_argument("--scenario", choices=sorted(SCENARIOS), required=True)
    run.add_argument(
        "--replay",
        action="store_true",
        help="Credential-free scripted replay (regression only; not evidence of agent behaviour).",
    )
    run.add_argument(
        "--replay-approval",
        choices=["approve", "decline"],
        help="Replay only: a scripted answer to the budget-extension request (synthetic, not a human decision).",
    )
    for name, verb in (("approve", "Approve"), ("decline", "Decline")):
        command = commands.add_parser(name, help=f"{verb} a pending budget-extension request as the AI Ops Lead.")
        command.add_argument("request_id")
    arguments = parser.parse_args(argv)

    if arguments.command in {"approve", "decline"}:
        return _decide(arguments.request_id, approve=arguments.command == "approve")

    scenario = SCENARIOS[arguments.scenario]
    if arguments.replay:
        session = replay_session(scenario)
        approver = ScriptedApprover(arguments.replay_approval == "approve") if arguments.replay_approval else None
    else:
        if arguments.replay_approval:
            parser.error("--replay-approval is only allowed with --replay")
        if not STATE_PATH.is_file():
            print(f"No deployment state at {STATE_PATH}. Run infra/deploy.sh first, or use --replay.", file=sys.stderr)
            return 2
        from .agent import FoundryAgentSession

        session = FoundryAgentSession.from_deployment(json.loads(STATE_PATH.read_text(encoding="utf-8")))
        approver = FileApprovalChannel(APPROVALS_DIR, emit=lambda line: print(line, flush=True))

    def emit(line: str) -> None:
        print(line, flush=True)

    try:
        evidence = asyncio.run(run_scenario(scenario, session, evidence_dir=EVIDENCE_DIR, emit=emit, approver=approver))
    except RunAborted as aborted:
        evidence = aborted.evidence
        print(json.dumps({key: evidence[key] for key in ("outcome", "admitted_calls", "executed_calls", "error_class")}))
        return 1
    summary = {key: evidence[key] for key in ("outcome", "admitted_calls", "executed_calls", "denied_tool")}
    summary["budget_extension"] = (evidence["budget_extension"] or {}).get("status")
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
