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

Run with: ``python -m src.cr001_interop.demo_runner``
"""

from __future__ import annotations

import asyncio
import uuid

from .evidence import EvidenceEvent, record_event
from .mcp_server import redact_text as mcp_redact_text

_COPILOT_AGENT_ID = "copilot-pii-demo"

# Synthetic-only inputs; never use real personal data in this demo.
_SCENARIOS = [
    {"text": "Please reschedule my appointment.", "protocol": "mcp"},
    {"text": "Contact me at jane.doe@example.com or 555-0100.", "protocol": "mcp"},
    {"text": "This run intentionally never calls the MCP/A2A gate.", "protocol": None},
]


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
    asyncio.run(_run_all())
    print(f"Simulated {len(_SCENARIOS)} runs; one of them deliberately skipped the MCP gate.")
    print("Now run: python -m src.cr001_interop.compliance_evaluator")


if __name__ == "__main__":
    main()
