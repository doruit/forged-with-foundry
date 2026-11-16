"""Host-owned, append-only journal of ACS decisions and verified progress for one run.

ACS is stateless: it evaluates the history the host supplies. This journal is
that history. It records ACS decisions and system-of-record verifications; it
never makes a governance decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RunJournal:
    run_id: str
    _entries: list[dict[str, object]] = field(default_factory=list)

    def _append(self, **entry: object) -> dict[str, object]:
        entry = {"seq": len(self._entries) + 1, "run_id": self.run_id, **entry}
        self._entries.append(entry)
        return dict(entry)

    def admission(self, *, tool_name: str, fingerprint: str) -> dict[str, object]:
        return self._append(kind="admission", tool_name=tool_name, fingerprint=fingerprint, reason="acs_admitted")

    def denial(self, *, tool_name: str, fingerprint: str, reason: str) -> dict[str, object]:
        return self._append(kind="denial", tool_name=tool_name, fingerprint=fingerprint, reason=reason)

    def outcome(self, *, tool_name: str, fingerprint: str, progress: bool) -> dict[str, object]:
        return self._append(kind="outcome", tool_name=tool_name, fingerprint=fingerprint, progress=progress)

    def confirm_reason(self, seq: int, reason: str) -> None:
        entry = self._entries[seq - 1]
        if entry["kind"] != "admission":
            raise ValueError("only_admissions_are_confirmed")
        entry["reason"] = reason

    def snapshot(self) -> list[dict[str, object]]:
        return [dict(entry) for entry in self._entries]

    def count(self, kind: str) -> int:
        return sum(1 for entry in self._entries if entry["kind"] == kind)
