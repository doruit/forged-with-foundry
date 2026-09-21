"""Execute and verify synthetic helpdesk actions without production access."""

import sqlite3
from typing import Literal

TicketKind = Literal["account_unlock", "software_install", "hardware_repair"]
Action = Literal["unlock_synthetic_account", "install_synthetic_package", "escalate"]


class SyntheticTicket:
    """Own one disposable in-memory ticket and verify its resulting state."""

    def __init__(self, kind: TicketKind) -> None:
        if kind not in ("account_unlock", "software_install", "hardware_repair"):
            raise ValueError("Unsupported synthetic ticket kind")
        self.kind = kind
        self.connection = sqlite3.connect(":memory:")
        self.connection.execute(
            "CREATE TABLE ticket (locked INTEGER, installed INTEGER, human INTEGER, executed INTEGER)"
        )
        self.connection.execute("INSERT INTO ticket VALUES (1, 0, 0, 0)")
        self.connection.commit()

    def execute(self, action: Action) -> str:
        """Apply only the matching synthetic resolution, or hand off to a human."""
        if action == "escalate":
            statement = "UPDATE ticket SET human = 1, executed = 1"
        elif action == "unlock_synthetic_account" and self.kind == "account_unlock":
            statement = "UPDATE ticket SET locked = 0, executed = 1"
        elif action == "install_synthetic_package" and self.kind == "software_install":
            statement = "UPDATE ticket SET installed = 1, executed = 1"
        else:
            raise ValueError("Action does not resolve this synthetic ticket")
        with self.connection:
            self.connection.execute(statement)
        return "Synthetic action executed; outcome must be verified from stored state."

    def outcome(self) -> str:
        """Read back state; a model response cannot supply or override this result."""
        locked, installed, human, executed = self.connection.execute(
            "SELECT locked, installed, human, executed FROM ticket"
        ).fetchone()
        if human:
            return "escalated"
        resolved = (self.kind == "account_unlock" and locked == 0) or (
            self.kind == "software_install" and installed == 1
        )
        return "deflected" if executed and resolved else "unresolved"

    def close(self) -> None:
        """Destroy only this ticket's in-memory synthetic state."""
        self.connection.close()

    def __enter__(self) -> "SyntheticTicket":
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()