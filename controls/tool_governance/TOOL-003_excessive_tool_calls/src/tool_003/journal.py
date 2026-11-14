"""Host-owned, append-only journal of ACS pre_tool_call decisions for one run.

ACS is stateless: it evaluates the history the host supplies. This journal is
that history. It records ACS decisions; it never makes one.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RunJournal:
    run_id: str
    _entries: list[dict[str, object]] = field(default_factory=list)

    def record(self, *, decision: str, tool_name: str, call_id: str, reason: str) -> dict[str, object]:
        if decision not in {"allow", "deny"}:
            raise ValueError("unsupported_decision")
        entry = {
            "seq": len(self._entries) + 1,
            "run_id": self.run_id,
            "point": "pre_tool_call",
            "decision": decision,
            "tool_name": tool_name,
            "call_id": call_id,
            "reason": reason,
        }
        self._entries.append(entry)
        return dict(entry)

    def snapshot(self) -> list[dict[str, object]]:
        return [dict(entry) for entry in self._entries]

    def confirm_reason(self, seq: int, reason: str) -> None:
        """Replace the provisional admission reason with the one ACS returned."""
        entry = self._entries[seq - 1]
        if entry["decision"] != "allow":
            raise ValueError("only_admissions_are_confirmed")
        entry["reason"] = reason

    def admitted(self) -> int:
        return sum(1 for entry in self._entries if entry["decision"] == "allow")
