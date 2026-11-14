"""The AUT-004 stop path: every protected call reads the switch, then ACS decides.

One `StopService` exists per process so the in-flight report covers every
session the process has served. Its records are lost on restart; the stop
itself is not, because the switch lives in App Configuration.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from agent_control_specification import AgentControlBlocked, InterventionPoint

from . import STOP_REASON
from .stop_state import StopState
from .tools import PROBE_ORDER, SyntheticLedger, now

PAUSED_OUTPUT = {"error": "refunds_paused_by_operator"}
MAX_MODEL_ROUNDS = 8


@dataclass(frozen=True)
class Scope:
    protected_tool: str
    flag_name: str
    contract_sha256: str

    def metadata(self) -> dict[str, str]:
        return {
            "protected_tool": self.protected_tool,
            "flag_name": self.flag_name,
            "contract_sha256": self.contract_sha256,
        }


@dataclass
class StopService:
    control: Any
    scope: Scope
    read_state: Callable[[], StopState]
    ledger: SyntheticLedger = field(default_factory=SyntheticLedger)
    decisions: list[dict[str, Any]] = field(default_factory=list)

    async def startup(self) -> dict[str, str]:
        result = await self.control.evaluate_intervention_point(
            InterventionPoint.AGENT_STARTUP, {"metadata": self.scope.metadata()}
        )
        return {"decision": result.verdict.decision.value, "reason": result.verdict.reason or ""}

    async def _state(self) -> StopState:
        return await asyncio.to_thread(self.read_state)

    async def guarded_call(self, run_id: str, name: str, args: dict[str, Any], call_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        """Run one tool call through ACS; returns (tool output for the model, decision record)."""
        protected = name == self.scope.protected_tool
        state = await self._state() if protected else None
        record: dict[str, Any] = {
            "run_id": run_id,
            "tool_name": name,
            "order_id": args.get("order_id") if protected else None,
            "stop_state": state.as_snapshot() if state else None,
            "evaluated_at": now(),
        }
        snapshot: dict[str, Any] = {"metadata": self.scope.metadata()}
        if state is not None:
            snapshot["stop_state"] = state.as_snapshot()

        async def execute(effective_args: Any) -> dict[str, Any]:
            record["admitted_at"] = now()
            record.update(decision="allow", reason="admitted", executed=None)
            self.decisions.append(record)
            return await self.ledger.execute(name, effective_args)

        try:
            result = await self.control.run_tool(name, args, execute, tool_call_id=call_id, snapshot=snapshot)
        except AgentControlBlocked as blocked:
            if blocked.intervention_point is not InterventionPoint.PRE_TOOL_CALL:
                raise
            record.update(decision="deny", reason=blocked.result.verdict.reason or "", executed=False)
            self.decisions.append(record)
            return PAUSED_OUTPUT, record
        except Exception as error:  # noqa: BLE001 - an admitted call that failed is still accounted for
            if "admitted_at" not in record:
                raise
            record.update(decision="allow", reason="admitted_then_failed", executed=None, error_class=type(error).__name__)
            return {"error": "tool_failed"}, record
        record.update(
            decision="allow",
            reason=result.pre_tool_call_result.verdict.reason or "",
            executed=True,
            completed_at=now(),
        )
        return result.value, record

    async def handle_request(self, session: Any, prompt: str, emit: Callable[[str], Any]) -> str:
        run_id = str(uuid.uuid4())
        try:
            calls = await asyncio.to_thread(session.start, prompt)
            for _ in range(MAX_MODEL_ROUNDS):
                if not calls:
                    return session.final_text()
                outputs = []
                for call in calls:
                    output, record = await self.guarded_call(run_id, call.name, call.args, call.call_id)
                    await emit(describe(record))
                    outputs.append((call.call_id, output))
                calls = await asyncio.to_thread(session.submit, outputs)
            return "This request needed too many steps and was handed to a specialist."
        finally:
            await asyncio.to_thread(session.close)

    async def probe(self) -> dict[str, Any]:
        """Attempt one synthetic refund on purpose to verify the stop."""
        _, record = await self.guarded_call("probe-" + str(uuid.uuid4()), self.scope.protected_tool, {"order_id": PROBE_ORDER}, "probe")
        observed = (record.get("stop_state") or {}).get("status")
        verified = record["decision"] == "deny" and record["reason"] == STOP_REASON and observed == "disabled"
        return {
            "probe_decision": record["decision"],
            "probe_reason": record["reason"],
            "observed_switch": observed,
            "stop_verified": verified,
            "note": None if verified else (
                "denied because the switch could not be read: fail-closed, but the stop itself was not observed"
                if record["decision"] == "deny" else "the switch is enabled: no stop is in effect"
            ),
            "verified_at": now(),
        }

    def in_flight_report(self, current: StopState) -> dict[str, Any]:
        """Account for refunds admitted before the stop, verified against the ledger."""
        stopped_at = current.last_modified if current.status == "disabled" else None
        refunds = []
        for record in self.decisions:
            if record["tool_name"] != self.scope.protected_tool or record.get("order_id") == PROBE_ORDER:
                continue
            admitted = record.get("admitted_at")
            if admitted is None:
                refunds.append({"order_id": record["order_id"], "decision": "deny", "reason": record["reason"],
                                "evaluated_at": record["evaluated_at"]})
                continue
            committed = self.ledger.committed_at(record["order_id"])
            outcome = "completed" if committed else ("failed" if record.get("error_class") else "unknown")
            refunds.append({
                "order_id": record["order_id"],
                "decision": "allow",
                "admitted_at": admitted,
                "outcome": outcome,
                "committed_at": committed,
                "in_flight_at_stop": _before(admitted, stopped_at) and not _before(committed, stopped_at),
            })
        return {
            "switch": current.as_snapshot(),
            "stop_requested_at": stopped_at,
            "refunds": refunds,
            "scope_note": "covers this process only; the ledger is in memory and resets on restart",
        }


def _before(earlier: str | None, later: str | None) -> bool:
    return bool(earlier and later and datetime.fromisoformat(earlier) < datetime.fromisoformat(later))


def describe(record: dict[str, Any]) -> str:
    state = record.get("stop_state")
    switch = f" | switch {state['status']}" if state else ""
    if record["decision"] == "deny":
        return f"ACS pre_tool_call {record['tool_name']} -> deny ({record['reason']}){switch}; not executed"
    if record.get("executed") is None:
        return f"ACS pre_tool_call {record['tool_name']} -> allow{switch}; admitted, then failed ({record['error_class']})"
    return f"ACS pre_tool_call {record['tool_name']} -> allow ({record['reason']}){switch}; executed"
