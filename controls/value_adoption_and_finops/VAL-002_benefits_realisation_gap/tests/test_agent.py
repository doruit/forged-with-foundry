"""Verify the monitored workload's minimized event contract."""

import importlib.util
from pathlib import Path
import sys
from uuid import uuid4

import pytest

CONTROL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CONTROL))
SPEC = importlib.util.spec_from_file_location("val002_agent", CONTROL / "agent.py")
agent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(agent)


@pytest.mark.parametrize("kind,action,outcome", [
    ("account_unlock", "unlock_synthetic_account", "deflected"),
    ("software_install", "install_synthetic_package", "deflected"),
    ("hardware_repair", "escalate", "escalated"),
    ("hardware_repair", "unlock_synthetic_account", "unresolved"),
])
def test_given_action_when_processed_then_event_matches_verified_state(kind, action, outcome):
    event = agent.process_ticket(str(uuid4()), 1, "ticket-0001", kind, action)

    assert (event["outcome"], event["verified"], event["human_handled"]) == (
        outcome, outcome != "unresolved", outcome == "escalated",
    )


@pytest.mark.parametrize("field,value", [
    ("run_id", "not-a-run"), ("period", 0), ("period", True),
    ("ticket_id", "alice@example.com"), ("kind", "production_reset"),
])
def test_given_invalid_metadata_when_processed_then_rejected(field, value):
    request = dict(run_id=str(uuid4()), period=1, ticket_id="ticket-0001",
                   kind="account_unlock", action="unlock_synthetic_account")
    request[field] = value

    with pytest.raises((ValueError, TypeError)):
        agent.process_ticket(**request)


def test_given_valid_action_when_event_emitted_then_only_allowlisted_fields():
    event = agent.process_ticket(str(uuid4()), 1, "ticket-0001", "account_unlock",
                                 "unlock_synthetic_account")

    assert set(event) == {
        "control_id", "workload_version", "agent_id", "metric_name", "run_id",
        "period", "ticket_id", "kind", "outcome", "verified", "human_handled", "timestamp",
    }
    assert event["control_id"] == "VAL-002"
