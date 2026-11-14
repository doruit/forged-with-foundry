"""Run one support request with every model and tool call routed through ACS."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from agent_control_specification import AgentControlBlocked, InterventionPoint

from . import LOOP_REASON
from .contract import DEFAULT_CONTRACT, MISSING_THRESHOLD_CONTRACT, load_threshold
from .evidence import build_evidence, write_evidence
from .fingerprint import fingerprint
from .journal import RunJournal
from .tools import SyntheticSupportSystem

HANDOFF_MESSAGE = (
    "This request was stopped because the same action kept repeating without progress. "
    "A support specialist will check the refund and contact the customer."
)
BLOCKED_OUTPUT = {"error": "blocked_by_governance"}


class RunAborted(RuntimeError):
    """The run stopped on an unexpected error after evidence was written."""

    def __init__(self, evidence: dict[str, Any]) -> None:
        super().__init__(f"run aborted: {evidence['error_class']}")
        self.evidence = evidence


@dataclass(frozen=True)
class Scenario:
    name: str
    prompt: str
    replay: list[list[tuple[str, dict[str, Any]]]]
    contract: Path = DEFAULT_CONTRACT


_LOOKUP = ("lookup_order", {"order_id": "ORD-1003"})
_REFUND = ("issue_refund", {"order_id": "ORD-1003"})
_STORM_PROMPT = "Ticket TCK-2003: The customer reports that order ORD-1003 arrived damaged and asks for a refund."

SCENARIOS = {
    "healthy": Scenario(
        "healthy",
        "Ticket TCK-2001: The customer reports that order ORD-1001 arrived damaged and asks for a refund.",
        [
            [("lookup_order", {"order_id": "ORD-1001"})],
            [("issue_refund", {"order_id": "ORD-1001"})],
            [("reply_to_ticket", {"ticket_id": "TCK-2001", "summary": "Refund issued for ORD-1001."})],
        ],
    ),
    # The gateway answers `unknown` and never commits; the flawed retry
    # instruction makes the agent look the order up and retry, again and again.
    # Neither the lookups nor the refunds make progress, so the third identical
    # lookup is the first action to reach the threshold.
    "retry-storm": Scenario("retry-storm", _STORM_PROMPT, [[_LOOKUP], [_REFUND]] * 3),
    # The contract has no approved threshold, so the run must not start.
    "missing-threshold": Scenario("missing-threshold", _STORM_PROMPT, [[_LOOKUP]], MISSING_THRESHOLD_CONTRACT),
}


def _verdict(result: Any) -> dict[str, str]:
    return {"decision": result.verdict.decision.value, "reason": result.verdict.reason or ""}


async def run_scenario(
    scenario: Scenario,
    session: Any,
    control: Any,
    *,
    telemetry: Any = None,
    contract_path: Path | None = None,
    evidence_dir: Path | None = None,
    emit: Callable[[str], None] = lambda _line: None,
) -> dict[str, Any]:
    run_id = str(uuid.uuid4())
    declaration = load_threshold(contract_path or scenario.contract)
    metadata = {
        "control_id": "RUN-006",
        "run_id": run_id,
        "threshold": declaration.threshold,
        "contract_status": declaration.status,
    }
    journal = RunJournal(run_id)
    system = SyntheticSupportSystem()
    model_gate: list[dict[str, object]] = []
    outcome, error_class, stopped_at = "completed", None, None

    def snapshot() -> dict[str, Any]:
        return {"metadata": metadata, "prior_decisions": journal.snapshot()}

    emit(f"run {run_id} | repeat threshold {declaration.threshold} | contract {declaration.status}")
    startup = _verdict(
        await control.evaluate_intervention_point(InterventionPoint.AGENT_STARTUP, {"metadata": metadata})
    )
    emit(f"ACS agent_startup -> {startup['decision']} ({startup['reason']})")

    async def model_call(send) -> list:
        try:
            calls = await send(snapshot())
        except AgentControlBlocked as blocked:
            if blocked.intervention_point is not InterventionPoint.PRE_MODEL_CALL:
                raise
            reason = blocked.result.verdict.reason or "denied"
            model_gate.append({"after_journal_seq": len(journal.snapshot()), "decision": "deny", "reason": reason})
            emit(f"ACS pre_model_call -> deny ({reason}); no request sent to Foundry")
            raise
        model_gate.append({"after_journal_seq": len(journal.snapshot()), "decision": "allow"})
        return calls

    if startup["decision"] != "allow":
        outcome = "not_started"
        emit("Run not started; no model call made.")
    else:
        try:
            calls = await model_call(lambda snap: session.start(scenario.prompt, snap))
            while calls:
                outputs: list[tuple[str, dict[str, Any]]] = []
                for call in calls:
                    action = fingerprint(call.name, call.args)
                    admitted: list[int] = []

                    def execute(args: Any, call=call, action=action) -> Any:
                        admitted.append(journal.admission(tool_name=call.name, fingerprint=action)["seq"])
                        return system.execute(call.name, args)

                    try:
                        result = await control.run_tool(
                            call.name, call.args, execute, tool_call_id=call.call_id, snapshot=snapshot()
                        )
                    except AgentControlBlocked as blocked:
                        if blocked.intervention_point is not InterventionPoint.PRE_TOOL_CALL:
                            raise
                        reason = blocked.result.verdict.reason or "denied"
                        journal.denial(tool_name=call.name, fingerprint=action, reason=reason)
                        if reason == LOOP_REASON and stopped_at is None:
                            stopped_at = "pre_tool_call"
                        emit(f"ACS pre_tool_call {call.name} -> deny ({reason}); tool not executed")
                        outputs.append((call.call_id, BLOCKED_OUTPUT))
                        continue
                    journal.confirm_reason(admitted[0], result.pre_tool_call_result.verdict.reason or "")
                    progress = system.last_progress
                    journal.outcome(tool_name=call.name, fingerprint=action, progress=progress)
                    status = result.value.get("status", "ok") if isinstance(result.value, dict) else "ok"
                    emit(f"ACS pre_tool_call {call.name} -> allow; executed; result {status}; progress {progress}")
                    outputs.append((call.call_id, result.value))
                # A typical agent loop hands tool errors back to the model;
                # ACS pre_model_call is what stops the run there.
                calls = await model_call(lambda snap, outputs=outputs: session.submit(outputs, snap))
            emit(f"Agent reply: {session.final_text()}")
        except AgentControlBlocked as blocked:
            if blocked.intervention_point is not InterventionPoint.PRE_MODEL_CALL:
                outcome, error_class = "aborted", type(blocked).__name__
            else:
                outcome = "stopped"
                emit(f"Run stopped. {HANDOFF_MESSAGE}")
        except Exception as error:  # noqa: BLE001 - record, then re-raise below
            outcome, error_class = "aborted", type(error).__name__
            emit(f"Run aborted ({error_class}).")
        finally:
            session.close()

    notification_state = telemetry.flush() if telemetry is not None else "not_configured"
    notification = {
        "channel": "not_deployed" if notification_state == "not_configured" else "azure_monitor_log_alert",
        "acs_metrics_export": notification_state,
    }
    if outcome == "stopped":
        emit(f"ACS metrics export to Application Insights: {notification_state}")
    evidence = build_evidence(
        run_id=run_id,
        scenario=scenario.name,
        threshold=declaration.threshold,
        contract={"reference": declaration.reference, "sha256": declaration.sha256, "status": declaration.status},
        startup=startup,
        journal=journal.snapshot(),
        model_gate=model_gate,
        outcome=outcome,
        executed_calls=system.executed_calls,
        refund_attempts=system.refund_attempts,
        notification=notification,
        source=session.source,
        correlation=session.correlation(),
        error_class=error_class,
        stopped_at=stopped_at,
    )
    if evidence_dir is not None:
        emit(f"Evidence: {write_evidence(evidence_dir, evidence)}")
    if outcome == "aborted":
        raise RunAborted(evidence)
    return evidence
