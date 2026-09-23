"""Exercise the synthetic outcome boundary, without a model or Azure."""

import importlib.util
from pathlib import Path
import sqlite3

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "workload.py"
SPEC = importlib.util.spec_from_file_location("val002_workload", MODULE_PATH)
workload = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(workload)


@pytest.mark.parametrize("kind", ["account_unlock", "software_install", "hardware_repair"])
def test_given_no_tool_execution_when_verified_then_unresolved(kind):
    with workload.SyntheticTicket(kind) as ticket:
        assert ticket.outcome() == "unresolved"


@pytest.mark.parametrize("kind,action", [
    ("account_unlock", "unlock_synthetic_account"),
    ("software_install", "install_synthetic_package"),
])
def test_given_matching_action_when_executed_then_readback_proves_deflection(kind, action):
    with workload.SyntheticTicket(kind) as ticket:
        ticket.execute(action)

        assert ticket.outcome() == "deflected"


def test_given_human_handling_when_later_resolved_then_not_deflected():
    with workload.SyntheticTicket("account_unlock") as ticket:
        ticket.execute("escalate")
        ticket.execute("unlock_synthetic_account")

        assert ticket.outcome() == "escalated"


def test_given_wrong_action_when_executed_then_no_resolution():
    with workload.SyntheticTicket("hardware_repair") as ticket:
        with pytest.raises(ValueError, match="does not resolve"):
            ticket.execute("unlock_synthetic_account")

        assert ticket.outcome() == "unresolved"


def test_given_tampered_state_without_execution_when_verified_then_not_deflected():
    with workload.SyntheticTicket("account_unlock") as ticket:
        ticket.connection.execute("UPDATE ticket SET locked = 0")

        assert ticket.outcome() == "unresolved"


def test_given_finished_ticket_when_context_exits_then_state_destroyed():
    with workload.SyntheticTicket("account_unlock") as ticket:
        ticket.execute("unlock_synthetic_account")

    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        ticket.outcome()
