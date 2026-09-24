"""Run, evaluate, and notify for the QLT-001 fleet synthetic demonstration.

Four windows tell the story this control detects across a small fleet of
three agents (see ``workload.FLEET``), each representing a different team's
KB rigor and instruction rigor. The Platform Team's KB never degrades within
the demo's 4 windows; the Regional Team's KB is current through window 2 and
degrades from window 3; the Contractor Team's KB was never populated at all
-- it is degraded from window 1 onward, and its weaker instructions turn
that absence into fabricated, labeled-as-assumption answers from the very
first window (confirmed live 2026-09-25: real, unscripted fabricated content
appeared in window 1, not only window 4 -- a genuinely different-severity
breach present throughout the demo, not one that only appears later; see
ASSESSMENT.md revision note 5 and README.md "What the demo does not prove").
Remediating the underlying knowledge base or rewriting a team's instructions
is deliberately out of scope for this control's own automation.

The authoritative groundedness signal is Microsoft Foundry's Continuous
Evaluation against each fleet agent's real live traffic (`kind: prompt`,
confirmed accepted -- see ``docs/UPSTREAM-FEEDBACK.md``), not periodic batch
evaluation. This control also displays a second, independent, non-authoritative
signal in real time: each response's own self-reported groundedness confidence
and, when low, its own suggested follow-up questions (see agent.py) -- a
user-facing nudge that, combined with Continuous Evaluation's async,
governance-facing signal, gives this control two complementary mechanisms
that can each raise groundedness over time, from two different perspectives
(see README.md "Two self-healing mechanisms, not one").
"""

import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from uuid import UUID, uuid4

import httpx
import truststore
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import ContinuousEvaluationRuleAction, EvaluationRule, EvaluationRuleFilter
from azure.ai.projects.telemetry import AIProjectInstrumentor
from azure.core.exceptions import AzureError, HttpResponseError
from azure.identity import AzureCliCredential
from azure.monitor.opentelemetry import configure_azure_monitor

import agent
from evaluator import evaluate
from workload import FLEET, TOPICS

CONTROL = Path(__file__).resolve().parent
WINDOWS = CONTROL / ".azure/qlt001/windows"
FLOW_TOKEN_SCOPE = "https://service.flow.microsoft.com//.default"
GENAI_TRACING_ENV_VAR = "AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING"
EVAL_NAME = "qlt001-fleet-groundedness"
CRITERIA = ("groundedness", "relevance", "retrieval")


def timestamp() -> str:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def save(path: Path, value: dict) -> None:
    """Atomically persist the one authoritative record before external effects."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def settings() -> dict:
    """Read azd's local configuration without printing its secret values."""
    result = subprocess.run(["azd", "env", "get-values", "--output", "json"],
                            cwd=CONTROL, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def instrument(client: AIProjectClient, credential) -> None:
    """Wire this process's own outgoing traffic into Application Insights.

    None of this is automatic (confirmed live 2026-09-25; see
    ``docs/UPSTREAM-FEEDBACK.md``'s "Resolution pass"): `AIProjectInstrumentor`
    silently no-ops unless ``AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING=true`` is
    set; `configure_azure_monitor` needs an explicit ``credential=`` because
    this control's Application Insights resource has ``DisableLocalAuth: true``
    (see ``infra/main.bicep``); and the identity used here needs the
    Monitoring Metrics Publisher role on that resource (``infra/main.bicep``'s
    ``publisher`` role assignment) -- without all three, Continuous Evaluation
    has no trace data to sample at all, regardless of how the rule itself is
    configured.
    """
    os.environ.setdefault(GENAI_TRACING_ENV_VAR, "true")
    connection_string = client.telemetry.get_application_insights_connection_string()
    configure_azure_monitor(connection_string=connection_string, credential=credential)
    AIProjectInstrumentor().instrument(enable_content_recording=True)


def setup_fleet(client: AIProjectClient, model: str) -> str:
    """Register every fleet agent and attach its own continuous-evaluation rule.

    One shared ``Eval`` definition (multi-criterion: groundedness, relevance,
    retrieval); one rule per agent, because ``EvaluationRuleFilter`` matches a
    single agent name -- one rule cannot cover multiple fleet members.
    Re-running this against an already-registered agent creates a new version
    under the same name, which keeps any existing rule attached (filters match
    by name, not version). Returns the shared eval's id.
    """
    openai_client = client.get_openai_client()
    eval_obj = openai_client.evals.create(
        name=EVAL_NAME,
        data_source_config={"type": "logs"},
        testing_criteria=[
            {"type": "azure_ai_evaluator", "name": criterion, "evaluator_name": f"builtin.{criterion}",
             "initialization_parameters": {"deployment_name": model}}
            for criterion in CRITERIA
        ],
    )
    for profile in FLEET:
        agent.register_agent(client, profile, model=model)
        client.evaluation_rules.create_or_update(
            f"{profile.agent_id}-rule",
            EvaluationRule(
                display_name=f"QLT-001 continuous groundedness -- {profile.display_name}",
                action=ContinuousEvaluationRuleAction(eval_id=eval_obj.id, sampling_rate=100),
                filter=EvaluationRuleFilter(agent_name=profile.agent_id),
                event_type="responseCompleted",
                enabled=True,
            ),
        )
    return eval_obj.id


def invoke(openai_client, profile, topic: str, window: int, model: str) -> dict:
    """Send one real request through one fleet agent; execute its tool call locally.

    A prompt agent is server-side-only and cannot execute ``lookup_it_kb``
    itself (see agent.py's module docstring); this loop sends the request,
    executes the tool locally against this profile's own KB state, and sends
    the result back, exactly as any Responses API function-calling caller
    would. Returns the parsed structured response plus both response ids for
    the window manifest.
    """
    from workload import lookup

    request = json.dumps({"topic": topic, "window": window})
    first = openai_client.responses.create(
        model=model, input=request,
        extra_body={"agent_reference": {"name": profile.agent_id, "type": "agent_reference"}},
    )
    call = next((item for item in first.output if item.type == "function_call"), None)
    final = first
    if call is not None:
        final = openai_client.responses.create(
            model=model, previous_response_id=first.id,
            input=[{"type": "function_call_output", "call_id": call.call_id,
                    "output": lookup(profile, topic, window)}],
            extra_body={"agent_reference": {"name": profile.agent_id, "type": "agent_reference"}},
        )
    text = next((c.text for item in final.output if item.type == "message"
                for c in item.content if c.type == "output_text"), None)
    parsed = json.loads(text) if text else {}
    return {"response_id": final.id, "first_response_id": first.id, **parsed}


def display(profile, topic: str, result: dict) -> None:
    """Print the response alongside its self-reported groundedness confidence.

    This is the user-facing self-healing mechanism this control combines with
    Continuous Evaluation's async, governance-facing one -- see the module
    docstring and README.md "Two self-healing mechanisms, not one". Printed,
    not persisted as evidence: the self-report is a UX nudge, never this
    control's authoritative signal.
    """
    confidence = result.get("self_reported_confidence")
    followups = result.get("suggested_followups") or []
    print(f"[{profile.display_name}] {topic}: {result.get('answer', '')}")
    print(f"  self-reported confidence: {confidence}/5")
    if confidence is not None and confidence < 4 and followups:
        print("  suggested follow-ups to improve groundedness:")
        for question in followups:
            print(f"    - {question}")


def run_window(client: AIProjectClient, window: int, model: str) -> str:
    """Invoke every fleet agent once per topic for this window; display each result live."""
    window_id = str(uuid4())
    folder = WINDOWS / window_id
    manifest = {
        "window_id": window_id, "window": window,
        "started_at": timestamp(), "completed": False,
        "requests": {profile.agent_id: [] for profile in FLEET},
    }
    save(folder / "window.json", manifest)
    print(f"Window: {window_id} (window {window})", flush=True)
    openai_client = client.get_openai_client()
    for profile in FLEET:
        for topic in TOPICS:
            result = invoke(openai_client, profile, topic, window, model)
            display(profile, topic, result)
            manifest["requests"][profile.agent_id].append({
                "topic": topic, "invoked_at": timestamp(),
                "response_id": result["response_id"],
            })
    manifest.update(completed=True, finished_at=timestamp())
    save(folder / "window.json", manifest)
    print(f"Window {window}: {len(FLEET) * len(TOPICS)} invocations completed across {len(FLEET)} agents", flush=True)
    return window_id


def fetch_fleet_results(credential, config: dict, manifest: dict) -> tuple[dict, bool]:
    """Read each fleet agent's real, continuously-computed groundedness results.

    **Not yet live-confirmed as of this control's 2026-09-25 refactor.** Real
    trace content (``InputMessages``/``OutputMessages``/``AgentName``) is
    confirmed reaching ``AppGenAIContent`` in Log Analytics (see
    ``docs/UPSTREAM-FEEDBACK.md``'s "Resolution pass"), and that table's
    schema includes an ``EvaluationExplanation`` column -- structural
    evidence this is Microsoft's intended read path for a sampled trace's
    evaluation result, since no other observed table carries anything
    evaluation-shaped. But no request sent during this refactor's live
    verification had a populated ``EvaluationExplanation`` by the time of
    writing, so its real contents (and therefore how to parse a per-criterion
    ``passed``/``score``/``threshold`` out of it) remain unconfirmed. This
    function queries for it and fails closed -- returns ``complete=False`` --
    whenever it finds nothing populated, rather than guess at a parsing
    format never actually observed. Update this function's body once a real
    populated row is observed and its shape is known; until then, every
    ``evaluate`` run against fresh traffic will correctly report
    ``cannot_evaluate`` rather than a fabricated score.
    """
    from azure.monitor.query import LogsQueryClient, LogsQueryStatus

    logs_client = LogsQueryClient(credential)
    workspace_id = config.get("QLT001_WORKSPACE_ID", "")
    if not workspace_id:
        return {}, False
    fleet_results: dict[str, list[dict]] = {}
    for profile_agent_id in manifest.get("requests", {}):
        query = (
            "AppGenAIContent | where TimeGenerated > ago(2h) "
            f"| where AgentName == '{profile_agent_id}' "
            "| where isnotempty(EvaluationExplanation) | take 100"
        )
        try:
            response = logs_client.query_workspace(workspace_id, query, timespan=None)
        except Exception:
            return {}, False
        if response.status != LogsQueryStatus.SUCCESS or not response.tables[0].rows:
            return {}, False
        # Parsing intentionally not implemented -- see docstring: no real
        # populated row has been observed yet to confirm its shape.
        return {}, False
    return fleet_results, bool(fleet_results)


def card(record: dict) -> dict:
    """Build a content-minimized Teams card from the deterministic fleet evidence."""
    decision = record["decision"]
    cannot_evaluate = decision == "cannot_evaluate"
    status = {
        "quality_review_required": {
            "icon": "●", "color": "attention", "container": "attention",
            "title": "QLT-001: Fleet groundedness quality review required",
            "message": "At least one fleet agent's hallucination rate is above threshold, or a critical hallucination was confirmed. Product Owner review requested.",
        },
        "cannot_evaluate": {
            "icon": "⚠", "color": "warning", "container": "warning",
            "title": "QLT-001: Fleet groundedness measurement unavailable",
            "message": "Restore the continuous-evaluation read path before treating this window as healthy.",
        },
        "no_review_required": {
            "icon": "●", "color": "good", "container": "good",
            "title": "QLT-001: No sustained fleet hallucination rate breach",
            "message": "Every fleet agent's hallucination rate is within threshold and no critical hallucination was confirmed.",
        },
    }.get(decision, {
        "icon": "⚠", "color": "warning", "container": "warning",
        "title": "QLT-001: Decision requires attention",
        "message": "The control returned an unexpected decision. Check the evidence record.",
    })
    facts = [{"title": "Correlation", "value": record["correlation_id"]},
             {"title": "Recipient role",
              "value": record["notification"].get("recipient_role", "unknown")},
             {"title": "Reason", "value": record.get("reason", "not_recorded")}]
    if cannot_evaluate:
        facts.append({"title": "Accountable role", "value": "AI Governance Operations"})
    else:
        window, fleet = record["window"], record["fleet"]
        facts.extend([
            {"title": "Window", "value": str(window["number"])},
            {"title": "Fleet average score", "value": f"{fleet['fleet_average_score']:.2f}"},
            {"title": "Best performing", "value": f"{fleet['best_agent']['agent_id']} ({fleet['best_agent']['average_score']:.2f})"},
            {"title": "Worst performing", "value": f"{fleet['worst_agent']['agent_id']} ({fleet['worst_agent']['average_score']:.2f})"},
            {"title": "Threshold", "value": f"{record['threshold_percent']}%"},
        ])
        for agent_id, measurement in fleet["per_agent"].items():
            facts.append({"title": agent_id,
                         "value": f"{measurement['ungrounded']}/{measurement['total']} ungrounded ({measurement['rate_percent']}%), {len(measurement['critical_run_ids'])} critical"})
    return {"type": "message", "attachments": [{
        "contentType": "application/vnd.microsoft.card.adaptive", "contentUrl": None,
        "content": {"$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard", "version": "1.2", "body": [
                        {"type": "Container", "style": status["container"], "bleed": True,
                         "items": [{"type": "ColumnSet", "columns": [
                             {"type": "Column", "width": "auto", "items": [
                                 {"type": "TextBlock", "text": status["icon"],
                                  "color": status["color"], "size": "ExtraLarge",
                                  "weight": "Bolder", "horizontalAlignment": "Center"}]},
                             {"type": "Column", "width": "stretch", "items": [
                                 {"type": "TextBlock", "text": status["title"],
                                  "color": status["color"], "size": "Medium",
                                  "weight": "Bolder", "wrap": True},
                                 {"type": "TextBlock", "text": status["message"],
                                  "wrap": True, "spacing": "Small"}]}]}]},
                        {"type": "FactSet", "facts": facts}]}}]}


def notification_route(record: dict, config: dict) -> tuple[str, str] | None:
    """Route quality findings and measurement failures to different roles."""
    if record["decision"] == "quality_review_required":
        return config.get("QLT001_TEAMS_WEBHOOK_URL", ""), "Product Owner"
    if record["decision"] == "cannot_evaluate":
        return config.get("QLT001_GOVERNANCE_TEAMS_WEBHOOK_URL", ""), "AI Governance Operations"
    return None


def notify(path: Path, config: dict, *, post=None, retry_rejected: bool = False) -> dict:
    """Send at most once; persist ambiguous attempts and never infer delivery."""
    with path.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        record = json.loads(path.read_text())
        previous = record["notification"]
        confirmed_rejection = (retry_rejected and previous["status"] == "rejected"
                               and previous.get("http_status") in (401, 403))
        if previous["status"] != "not_requested" and not confirmed_rejection:
            return record
        route = notification_route(record, config)
        if route is None:
            return record
        endpoint, recipient_role = route
        record["notification"] = {
            "status": "attempted", "attempted_at": timestamp(),
            "delivery_verified": False, "recipient_role": recipient_role,
        }
        if confirmed_rejection:
            record["notification"]["previous_attempts"] = [
                *previous.get("previous_attempts", []),
                {key: value for key, value in previous.items() if key != "previous_attempts"},
            ]
        save(path, record)
        try:
            url = httpx.URL(endpoint)
            if url.scheme != "https" or not (url.host.endswith(".environment.api.powerplatform.com")
                    or url.host.endswith(".logic.azure.com")):
                raise ValueError("Invalid Teams workflow endpoint")
            if post is None:
                with AzureCliCredential(tenant_id=config["AZURE_TENANT_ID"]) as credential:
                    token = credential.get_token(FLOW_TOKEN_SCOPE).token
                with httpx.Client(timeout=30, follow_redirects=False) as client:
                    response = client.post(str(url), json=card(record),
                                           headers={"Authorization": f"Bearer {token}"})
            else:
                response = post(str(url), json=card(record))
            record["notification"].update(
                status="accepted" if 200 <= response.status_code < 300 else "rejected",
                http_status=response.status_code,
            )
        except httpx.RequestError:
            record["notification"]["status"] = "delivery_unknown"
        except (AzureError, KeyError, ValueError):
            record["notification"]["status"] = "configuration_or_auth_failed"
        save(path, record)
        return record


def create_parser() -> argparse.ArgumentParser:
    """Define the explicitly invoked demo steps; no production scheduler."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["setup", "run", "evaluate", "notify", "record-delivery"])
    parser.add_argument("--window", type=int, choices=[1, 2, 3, 4], default=1)
    parser.add_argument("--window-id")
    parser.add_argument("--retry-rejected", action="store_true",
                        help="Explicitly retry only a prior HTTP 401/403 rejection after fixing authentication")
    parser.add_argument("--flow-run-id")
    parser.add_argument("--message-id")
    return parser


def preserve_notification(previous: dict | None, current: dict) -> dict:
    """Retain attempts across measurement retries and record decision transitions."""
    if previous is None:
        return current
    current["prior_notifications"] = previous.get("prior_notifications", [])
    if previous["decision"] == current["decision"]:
        current["notification"] = previous["notification"]
    elif previous["notification"]["status"] != "not_requested":
        current["prior_notifications"] = [*current["prior_notifications"], {
            "decision": previous["decision"], "notification": previous["notification"],
        }]
    return current


def record_delivery(path: Path, window_id: str, flow_run_id: str, message_id: str) -> dict:
    """Record an operator's checked service receipt, not an automatic delivery claim."""
    if not flow_run_id or not flow_run_id.isalnum() or not message_id or not message_id.isdecimal():
        raise ValueError("Valid service receipt identifiers are required")
    with path.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        record = json.loads(path.read_text())
        if record["correlation_id"] != window_id or record["notification"]["status"] != "accepted":
            raise ValueError("Receipt requires this window's accepted notification")
        record["notification"].update(
            status="delivered", delivery_verified=True,
            verification_method="operator_checked_matching_flow_input_and_teams_201_receipt",
            verified_at=timestamp(), flow_run_id=flow_run_id, message_id=message_id,
        )
        save(path, record)
        return record


def main() -> int:
    """Execute one step and report a minimized result."""
    truststore.inject_into_ssl()
    args = create_parser().parse_args()
    try:
        config = settings()
        if args.command in ("setup", "run", "evaluate"):
            with AzureCliCredential() as credential:
                client = AIProjectClient(config["FOUNDRY_PROJECT_ENDPOINT"], credential, allow_preview=True)
                model = config["AZURE_AI_MODEL_DEPLOYMENT_NAME"]
                if args.command == "setup":
                    eval_id = setup_fleet(client, model)
                    print(json.dumps({"eval_id": eval_id, "agents": [p.agent_id for p in FLEET]}, indent=2))
                    return 0
                if args.command == "run":
                    instrument(client, credential)
                    run_window(client, args.window, model)
                    return 0
                window_id = str(UUID(args.window_id))
                folder = WINDOWS / window_id
                path = folder / "evidence.json"
                with path.with_suffix(".lock").open("a") as lock:
                    fcntl.flock(lock, fcntl.LOCK_EX)
                    previous = json.loads(path.read_text()) if path.exists() else None
                    if previous and previous["decision"] != "cannot_evaluate":
                        record = previous
                    else:
                        manifest = json.loads((folder / "window.json").read_text())
                        try:
                            fleet_results, complete = fetch_fleet_results(credential, config, manifest)
                        except (RuntimeError, KeyError, json.JSONDecodeError):
                            fleet_results, complete = {}, False
                        record = evaluate(manifest, fleet_results, retrieval_complete=complete)
                        record = preserve_notification(previous, record)
                        save(path, record)
        elif args.command == "notify":
            window_id = str(UUID(args.window_id))
            path = WINDOWS / window_id / "evidence.json"
            record = notify(path, config, retry_rejected=args.retry_rejected)
        else:
            window_id = str(UUID(args.window_id))
            path = WINDOWS / window_id / "evidence.json"
            record = record_delivery(path, window_id, args.flow_run_id, args.message_id)
        print(json.dumps({"window_id": window_id, "decision": record["decision"],
                          "reason": record["reason"], "notification": record["notification"]}, indent=2))
        if record["decision"] == "cannot_evaluate":
            return 2
        if args.command == "notify" and record["notification"]["status"] not in (
                "accepted", "delivered", "not_requested"):
            return 1
        return 0
    except (OSError, ValueError, TypeError, RuntimeError, subprocess.SubprocessError):
        print("Step failed. Check configuration and retained window state; no healthy result is inferred.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
