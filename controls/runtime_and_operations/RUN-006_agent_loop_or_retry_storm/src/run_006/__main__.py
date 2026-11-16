"""Command line: python -m src.run_006 run --scenario <name> [--replay]."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import warnings
from pathlib import Path

from .policy import get_control
from .runner import SCENARIOS, RunAborted, run_scenario
from .telemetry import telemetry_export

CONTROL_ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = CONTROL_ROOT / ".azure" / "deployment.json"
EVIDENCE_DIR = CONTROL_ROOT / "evidence"
SUMMARY = ("outcome", "stopped_at", "admitted_tool_calls", "refund_attempts_executed", "notification", "error_class")


def main(argv: list[str] | None = None) -> int:
    # ACS 0.3.1b1's own OpenAI adapter calls the deprecated Decision.applies_effects;
    # silence only that upstream warning so the transcript stays readable.
    warnings.filterwarnings("ignore", message="Decision.applies_effects is deprecated", category=DeprecationWarning)
    parser = argparse.ArgumentParser(prog="python -m src.run_006", description=__doc__)
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
        from .agent import ScriptedSession

        telemetry = telemetry_export(None)
        control = get_control()
        session = ScriptedSession(control, scenario.replay)
    else:
        if not STATE_PATH.is_file():
            print(f"No deployment state at {STATE_PATH}. Run infra/deploy.sh first, or use --replay.", file=sys.stderr)
            return 2
        from .agent import FoundryAgentSession

        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        telemetry = telemetry_export(state.get("appInsightsConnectionString"))
        control = get_control(telemetry.sink)
        session = FoundryAgentSession.from_deployment(control, state)

    try:
        evidence = asyncio.run(
            run_scenario(scenario, session, control, telemetry=telemetry, evidence_dir=EVIDENCE_DIR, emit=print)
        )
    except RunAborted as aborted:
        print(json.dumps({key: aborted.evidence[key] for key in SUMMARY}))
        return 1
    print(json.dumps({key: evidence[key] for key in SUMMARY}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
