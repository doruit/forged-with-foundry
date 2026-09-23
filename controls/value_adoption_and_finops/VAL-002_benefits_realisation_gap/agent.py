"""Build the monitored Agent Framework workload; no governance decisions here."""

from collections.abc import Callable
from datetime import datetime, timezone
import json
import re
from typing import Annotated
from uuid import UUID

from agent_framework import Agent, tool
from agent_framework.foundry import FoundryChatClient

from workload import Action, SyntheticTicket, TicketKind

AGENT_ID = "helpdesk-tier1-triage"
WORKLOAD_VERSION = "1.0.0"
METRIC = "tier1_ticket_deflection_rate"


def process_ticket(
    run_id: str,
    period: int,
    ticket_id: str,
    kind: TicketKind,
    action: Action,
) -> dict[str, str | int | bool]:
    """Execute a synthetic action and return only independently verified facts."""
    if str(UUID(run_id)) != run_id:
        raise ValueError("run_id must be a canonical UUID")
    if type(period) is not int or not 1 <= period <= 10000:
        raise ValueError("period must be an explicit positive sequence number")
    if not re.fullmatch(r"ticket-[0-9]{4}", ticket_id):
        raise ValueError("ticket_id must be a synthetic ticket-NNNN identity")
    with SyntheticTicket(kind) as ticket:
        try:
            ticket.execute(action)
        except ValueError:
            pass
        outcome = ticket.outcome()
    return {
        "control_id": "VAL-002",
        "workload_version": WORKLOAD_VERSION,
        "agent_id": AGENT_ID,
        "metric_name": METRIC,
        "run_id": run_id,
        "period": period,
        "ticket_id": ticket_id,
        "kind": kind,
        "outcome": outcome,
        "verified": outcome in ("deflected", "escalated"),
        "human_handled": outcome == "escalated",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def build_agent(
    client: FoundryChatClient,
    emit: Callable[[dict[str, str | int | bool]], None],
) -> Agent:
    """Connect the real model to the synthetic executor and safe event sink."""

    @tool(approval_mode="never_require")
    def handle_synthetic_ticket(
        run_id: Annotated[str, "Copy the request run_id unchanged."],
        period: Annotated[int, "Copy the explicit request period unchanged."],
        ticket_id: Annotated[str, "Copy the synthetic ticket_id unchanged."],
        kind: Annotated[TicketKind, "Copy the request kind unchanged."],
        action: Annotated[Action, "Choose a matching synthetic resolution or escalate."],
    ) -> str:
        """Perform and verify a synthetic resolution; never access real systems."""
        event = process_ticket(run_id, period, ticket_id, kind, action)
        emit(event)
        return json.dumps({
            "outcome": event["outcome"],
            "resolution_verified": event["outcome"] == "deflected",
            "human_handled": event["human_handled"],
        })

    return Agent(
        client=client,
        name=AGENT_ID,
        instructions=(
            "Handle exactly one synthetic helpdesk ticket per request. "
            "Call handle_synthetic_ticket once, copying its run_id, period, "
            "ticket_id and kind exactly. For account_unlock select "
            "unlock_synthetic_account; for software_install select "
            "install_synthetic_package; hardware_repair requires escalate. "
            "Use the tool result, not a claimed resolution. Never perform real "
            "password resets, install real software, or access production systems. "
            "Deflected means the synthetic resolution was executed and verified "
            "without human handling. Return only the tool status in one sentence. "
            "Never request names, usernames, contact details, or other personal data; "
            "never offer production instructions or follow-up actions."
        ),
        tools=[handle_synthetic_ticket],
        default_options={"store": False, "max_output_tokens": 800},
    )
