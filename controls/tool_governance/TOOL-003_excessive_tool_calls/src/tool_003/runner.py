"""Run one support request through ACS with the approved tool-call budget."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from agent_control_specification import AgentControlBlocked, InterventionPoint

from .agent import AgentSession, ScriptedSession
from .contract import DEFAULT_CONTRACT, load_budgets
from .evidence import build_evidence, write_evidence
from .journal import RunJournal
from .policy import get_control
from .tools import SyntheticSupportSystem

HANDOFF_MESSAGE = (
    "This request needs more steps than are approved for this type of task. "
    "A support specialist will take it from here."
)

_MULTI_ORDER_PROMPT = (
    "Ticket TCK-2002: The customer says several deliveries arrived damaged and asks for refunds on "
    "orders ORD-1001, ORD-1002, ORD-1003, ORD-1004, ORD-1005 and ORD-1006."
)


class RunAborted(RuntimeError):
    """The run stopped on an unexpected error after evidence was written."""

    def __init__(self, evidence: dict[str, Any]) -> None:
        super().__init__(f"run aborted: {evidence['error_class']}")
        self.evidence = evidence


@dataclass(frozen=True)
class Scenario:
    name: str
    task_type: str
    prompt: str
    replay: list[list[tuple[str, dict[str, Any]]]]


_SIX_LOOKUPS = [("lookup_order", {"order_id": f"ORD-100{index}"}) for index in range(1, 7)]

SCENARIOS = {
    "healthy": Scenario(
        "healthy",
        "single_refund",
        "Ticket TCK-2001: The customer reports that order ORD-1001 arrived damaged and asks for a refund.",
        [
            [("lookup_order", {"order_id": "ORD-1001"})],
            [("issue_refund", {"order_id": "ORD-1001"})],
            [("reply_to_ticket", {"ticket_id": "TCK-2001", "summary": "Refund issued for ORD-1001."})],
        ],
    ),
    # Intake routed a multi-order request as a single refund: every call is
    # legitimate, but the run needs more calls than the approved budget.
    "over-budget": Scenario("over-budget", "single_refund", _MULTI_ORDER_PROMPT, [_SIX_LOOKUPS]),
    # No budget is declared for this task type, so the run must not start.
    "undeclared-task": Scenario("undeclared-task", "bulk_refund", _MULTI_ORDER_PROMPT, [_SIX_LOOKUPS]),
}


def _verdict(result: Any) -> dict[str, str]:
    return {"decision": result.verdict.decision.value, "reason": result.verdict.reason or ""}


async def run_scenario(
    scenario: Scenario,
    session: AgentSession,
    *,
    contract_path: Path = DEFAULT_CONTRACT,
    evidence_dir: Path | None = None,
    emit: Callable[[str], None] = lambda _line: None,
) -> dict[str, Any]:
    control = get_control()
    run_id = str(uuid.uuid4())
    declaration = load_budgets(contract_path)
    budget = declaration.budget_for(scenario.task_type)
    metadata = {
        "control_id": "TOOL-003",
        "run_id": run_id,
        "task_type": scenario.task_type,
        "budget": budget,
        "contract_status": declaration.status,
    }
    journal = RunJournal(run_id)
    system = SyntheticSupportSystem()
    outcome, denied_tool, error_class = "completed", None, None

    emit(f"run {run_id} | task type {scenario.task_type} | approved budget {budget} | contract {declaration.status}")
    startup = _verdict(
        await control.evaluate_intervention_point(InterventionPoint.AGENT_STARTUP, {"metadata": metadata})
    )
    emit(f"ACS agent_startup -> {startup['decision']} ({startup['reason']})")

    if startup["decision"] != "allow":
        outcome = "not_started"
        emit(f"Run not started; no model call made. {HANDOFF_MESSAGE}")
    else:
        try:
            calls = session.start(scenario.prompt)
            while calls and outcome == "completed":
                outputs: list[tuple[str, dict[str, Any]]] = []
                for call in calls:
                    admitted_seq: list[int] = []

                    def execute(args: Any, call=call) -> dict[str, Any]:
                        # ACS has admitted the call: record it before the tool runs.
                        entry = journal.record(
                            decision="allow", tool_name=call.name, call_id=call.call_id, reason="acs_admitted"
                        )
                        admitted_seq.append(entry["seq"])
                        return system.execute(call.name, args)

                    try:
                        result = await control.run_tool(
                            call.name,
                            call.args,
                            execute,
                            tool_call_id=call.call_id,
                            snapshot={"metadata": metadata, "prior_decisions": journal.snapshot()},
                        )
                    except AgentControlBlocked as blocked:
                        if blocked.intervention_point is not InterventionPoint.PRE_TOOL_CALL:
                            raise
                        reason = blocked.result.verdict.reason or "denied"
                        journal.record(decision="deny", tool_name=call.name, call_id=call.call_id, reason=reason)
                        emit(f"ACS pre_tool_call #{journal.admitted() + 1} {call.name} -> deny ({reason}); tool not executed")
                        outcome, denied_tool = "handed_off", call.name
                        break
                    journal.confirm_reason(admitted_seq[0], result.pre_tool_call_result.verdict.reason or "")
                    emit(f"ACS pre_tool_call #{journal.admitted()} {call.name} -> allow; executed")
                    outputs.append((call.call_id, result.value))
                if outcome == "completed":
                    calls = session.submit(outputs)
            if outcome == "completed":
                emit(f"Agent reply: {session.final_text()}")
            else:
                emit(f"Run ended. {HANDOFF_MESSAGE}")
        except Exception as error:  # noqa: BLE001 - record, then re-raise below
            # Admitted calls may already have run; evidence must still be written.
            outcome, error_class = "aborted", type(error).__name__
            emit(f"Run aborted ({error_class}). {HANDOFF_MESSAGE}")
        finally:
            session.close()

    evidence = build_evidence(
        run_id=run_id,
        scenario=scenario.name,
        task_type=scenario.task_type,
        budget=budget,
        contract={"reference": declaration.reference, "sha256": declaration.sha256, "status": declaration.status},
        startup=startup,
        journal=journal.snapshot(),
        outcome=outcome,
        denied_tool=denied_tool,
        executed_calls=system.executed_calls,
        source=session.source,
        correlation=session.correlation(),
        error_class=error_class,
    )
    if evidence_dir is not None:
        path = write_evidence(evidence_dir, evidence)
        emit(f"Evidence: {path}")
    if outcome == "aborted":
        raise RunAborted(evidence)
    return evidence


def replay_session(scenario: Scenario) -> ScriptedSession:
    return ScriptedSession(scenario.replay)
