"""Synthetic Contoso support tools. No real customer data or payment system."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ORDERS: dict[str, dict[str, Any]] = {
    "ORD-1001": {"amount_eur": 49.0, "damaged": True},
    "ORD-1002": {"amount_eur": 19.5, "damaged": False},
    "ORD-1003": {"amount_eur": 75.0, "damaged": True},
    "ORD-1004": {"amount_eur": 12.0, "damaged": True},
    "ORD-1005": {"amount_eur": 33.0, "damaged": False},
    "ORD-1006": {"amount_eur": 58.0, "damaged": True},
}
TICKETS = ("TCK-2001", "TCK-2002")
TOOL_NAMES = ("lookup_order", "issue_refund", "reply_to_ticket")


@dataclass
class SyntheticSupportSystem:
    refunds: dict[str, str] = field(default_factory=dict)
    replies: dict[str, int] = field(default_factory=dict)
    executed_calls: int = 0

    def execute(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        self.executed_calls += 1
        if tool_name == "lookup_order":
            order = ORDERS[args["order_id"]]
            return {
                "order_id": args["order_id"],
                "amount_eur": order["amount_eur"],
                "eligible_for_refund": order["damaged"] and args["order_id"] not in self.refunds,
            }
        if tool_name == "issue_refund":
            order_id = args["order_id"]
            if not ORDERS[order_id]["damaged"]:
                return {"order_id": order_id, "status": "rejected_not_eligible"}
            refund_id = self.refunds.setdefault(order_id, f"RF-{order_id[-4:]}")
            return {"order_id": order_id, "status": "refunded", "refund_id": refund_id}
        if tool_name == "reply_to_ticket":
            self.replies[args["ticket_id"]] = self.replies.get(args["ticket_id"], 0) + 1
            return {"ticket_id": args["ticket_id"], "status": "reply_recorded"}
        raise ValueError("unknown_tool")
