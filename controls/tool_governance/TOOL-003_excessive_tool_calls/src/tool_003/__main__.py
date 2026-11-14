"""Command line: python -m src.tool_003 run --scenario <name> [--replay]."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from .runner import SCENARIOS, RunAborted, replay_session, run_scenario

CONTROL_ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = CONTROL_ROOT / ".azure" / "deployment.json"
EVIDENCE_DIR = CONTROL_ROOT / "evidence"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.tool_003", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Run one scenario through ACS.")
    run.add_argument("--scenario", choices=sorted(SCENARIOS), required=True)
    run.add_argument(
        "--replay",
        action="store_true",
        help="Credential-free scripted replay (regression only; not evidence of agent behaviour).",
    )
    arguments = parser.parse_args(argv)

    scenario = SCENARIOS[arguments.scenario]
    if arguments.replay:
        session = replay_session(scenario)
    else:
        if not STATE_PATH.is_file():
            print(f"No deployment state at {STATE_PATH}. Run infra/deploy.sh first, or use --replay.", file=sys.stderr)
            return 2
        from .agent import FoundryAgentSession

        session = FoundryAgentSession.from_deployment(json.loads(STATE_PATH.read_text(encoding="utf-8")))

    try:
        evidence = asyncio.run(run_scenario(scenario, session, evidence_dir=EVIDENCE_DIR, emit=print))
    except RunAborted as aborted:
        evidence = aborted.evidence
        print(json.dumps({key: evidence[key] for key in ("outcome", "admitted_calls", "executed_calls", "error_class")}))
        return 1
    print(json.dumps({key: evidence[key] for key in ("outcome", "admitted_calls", "executed_calls", "denied_tool")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
