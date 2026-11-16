"""Synthetic Contoso support tools with an ambiguous payment gateway.

The refund ledger and the ticket's reply log are the system of record.
Progress means an attempt produced a new, verified change there: a refund
newly on the ledger, or a reply not already on the ticket. A read never
counts as progress, and repeating an action that already succeeded does not
either. No real customer data or payment system is used.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ORDERS: dict[str, dict[str, Any]] = {
    "ORD-1001": {"amount_eur": 49.0, "damaged": True},
    "ORD-1003": {"amount_eur": 75.0, "damaged": True},
}
# The gateway times out for this order: it reports `unknown` and never commits.
AMBIGUOUS_GATEWAY_ORDERS = frozenset({"ORD-1003"})
TICKETS = ("TCK-2001", "TCK-2003")
TOOL_NAMES = ("lookup_order", "issue_refund", "reply_to_ticket")


@dataclass
class SyntheticSupportSystem:
    ledger: dict[str, str] = field(default_factory=dict)
    replies: set[tuple[str, str]] = field(default_factory=set)
    executed_calls: int = 0
    refund_attempts: int = 0
    last_progress: bool = False

    def execute(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        self.executed_calls += 1
        self.last_progress = False
        if tool_name == "lookup_order":
            order_id = args["order_id"]
            return {
                "order_id": order_id,
                "amount_eur": ORDERS[order_id]["amount_eur"],
                "refund_on_ledger": order_id in self.ledger,
                "eligible_for_refund": ORDERS[order_id]["damaged"] and order_id not in self.ledger,
            }
        if tool_name == "issue_refund":
            self.refund_attempts += 1
            order_id = args["order_id"]
            if order_id in AMBIGUOUS_GATEWAY_ORDERS:
                return {"order_id": order_id, "status": "unknown", "detail": "payment gateway timeout"}
            already_on_ledger = order_id in self.ledger
            refund_id = self.ledger.setdefault(order_id, f"RF-{order_id[-4:]}")
            self.last_progress = not already_on_ledger and order_id in self.ledger
            return {"order_id": order_id, "status": "refunded", "refund_id": refund_id}
        if tool_name == "reply_to_ticket":
            reply = (args["ticket_id"], args["summary"])
            self.last_progress = reply not in self.replies
            self.replies.add(reply)
            return {"ticket_id": args["ticket_id"], "status": "reply_recorded"}
        raise ValueError("unknown_tool")
