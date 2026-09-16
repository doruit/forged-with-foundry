"""CR-001 local demo harness: the independent "agent runtime" stand-in.

Emits ``agent.run.started``/``agent.run.completed`` for a handful of
synthetic runs, calling the MCP gate in-process for most of them -- and
deliberately skipping the endpoint call for at least one run, so
``compliance_evaluator.py`` has a real gap to detect instead of only ever
showing a clean report. This harness exercises the MCP path only; it has no
A2A equivalent (A2A wraps a full task/agent lifecycle, not a single gated
call, so it is demonstrated instead via the live server and
``tests/test_endpoints.py``'s
``test_mcp_and_a2a_produce_equivalent_decisions_for_same_input``, which
proves both protocols reach the same PRI-001 decision). Kept outside the
PII policy logic entirely, per the constraint that this file's only job is
to produce the run inventory.

This script is **not Azure-free**: it calls the real MCP gate, which calls
the real ``text_pii.enforce_text_pii`` (Azure AI Language) unmocked, exactly
like the deployed servers do. It requires the same Azure resource,
authentication, and configuration as core PRI-001's Chainlit demo -- see the
README's "Quick local demonstration" section before running this.

Run with: ``python -m src.cr001_interop.demo_runner``
"""

from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv

# Mirrors core PRI-001's src/pri_001/chat.py: shared deployment outputs are
# the default, and a control-local .env (one level up from this extension)
# can override them. Loaded here, at the entry point, because this harness
# -- unlike chat.py's Chainlit app -- has no other startup hook that does it.
_CONTROL_ROOT = Path(__file__).resolve().parents[4]
_REPOSITORY_ROOT = Path(__file__).resolve().parents[7]
load_dotenv(_REPOSITORY_ROOT / "infra" / ".env")
load_dotenv(_CONTROL_ROOT / ".env", override=True)

from .evidence import EvidenceEvent, record_event  # noqa: E402
from .mcp_server import redact_text as mcp_redact_text  # noqa: E402

_COPILOT_AGENT_ID = "copilot-pii-demo"

# Synthetic-only inputs; never use real personal data in this demo.
_SCENARIOS = [
    {"text": "Please reschedule my appointment.", "protocol": "mcp"},
    {"text": "Contact me at jane.doe@example.com or 555-0100.", "protocol": "mcp"},
    {"text": "This run intentionally never calls the MCP/A2A gate.", "protocol": None},
]


def _check_required_configuration() -> None:
    """Fail with one clear, actionable message before the demo starts, not mid-run."""
    if not os.environ.get("AZURE_LANGUAGE_ENDPOINT"):
        raise SystemExit(
            "Missing configuration: AZURE_LANGUAGE_ENDPOINT is not set.\n"
            "This demo calls a real Azure AI Language resource -- it is not Azure-free.\n"
            "Copy controls/privacy/PRI-001_pii_exposure/.env.example to .env and fill it "
            "in (see that control's README 'Prerequisites' section for the required "
            "Azure resources), or deploy them first with "
            "controls/privacy/PRI-001_pii_exposure/infra/deploy.sh."
        )


async def _run_one(scenario: dict) -> None:
    run_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())

    record_event(
        EvidenceEvent(
            event_name="agent.run.started",
            agent_id=_COPILOT_AGENT_ID,
            platform="copilot_studio",
            run_id=run_id,
            trace_id=trace_id,
        )
    )

    if scenario["protocol"] == "mcp":
        await mcp_redact_text(
            text=scenario["text"], agent_id=_COPILOT_AGENT_ID, run_id=run_id, trace_id=trace_id
        )
    # protocol=None -> deliberately skipped, to give the evaluator a real gap.

    record_event(
        EvidenceEvent(
            event_name="agent.run.completed",
            agent_id=_COPILOT_AGENT_ID,
            platform="copilot_studio",
            run_id=run_id,
            trace_id=trace_id,
        )
    )


async def _run_all() -> None:
    for scenario in _SCENARIOS:
        await _run_one(scenario)


def main() -> None:
    _check_required_configuration()
    asyncio.run(_run_all())
    print(f"Simulated {len(_SCENARIOS)} runs; one of them deliberately skipped the MCP gate.")
    print("Now run: python -m src.cr001_interop.compliance_evaluator")


if __name__ == "__main__":
    main()

