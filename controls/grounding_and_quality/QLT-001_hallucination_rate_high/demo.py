"""Run, evaluate, and notify for the isolated QLT-001 synthetic demonstration.

Four windows tell the story this control detects: window 1-2 use the current
knowledge base (healthy); window 3 uses the degraded knowledge base (drift
begins); window 4 repeats it (drift confirmed, review triggered). Remediating
the underlying knowledge base is deliberately out of scope for this control --
see README.md "What the demo does not prove".

The authoritative groundedness signal is Microsoft Foundry's batch/cloud
evaluation against this hosted agent (``azd ai agent eval`` /
``openai_client.evals.runs.output_items``), not Continuous Evaluation:
Continuous Evaluation rules currently reject ``kind: hosted`` agents outright
(confirmed against a real deployment on two SDK versions -- see
``docs/UPSTREAM-FEEDBACK.md`` and ``ASSESSMENT.md`` revision note 3).
"""

import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from uuid import UUID, uuid4

import httpx
import truststore
from azure.ai.projects import AIProjectClient
from azure.core.exceptions import AzureError, HttpResponseError
from azure.identity import AzureCliCredential

from evaluator import evaluate
from workload import TOPICS

CONTROL = Path(__file__).resolve().parent
WINDOWS = CONTROL / ".azure/qlt001/windows"
AGENT_NAME = "it-helpdesk-kb-assistant"
FLOW_TOKEN_SCOPE = "https://service.flow.microsoft.com//.default"


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


def extract_run_id(cli_output: str) -> str | None:
    """Extract the hosted invocation's Trace ID from ``azd ai agent invoke``'s output.

    Confirmed 2026-09-23 against a real hosted invocation: ``azd ai agent
    invoke`` prints human-readable labeled text, not JSON. It reports both a
    ``Response:`` id (``caresp_...``, an OpenAI Responses-API identifier) and
    a ``Trace ID:`` (a hex OTel trace id). Continuous Evaluation links its
    scores to traces (per Microsoft's own Foundry Observability
    documentation), so the Trace ID -- not the response id -- is the
    correlation key expected to match Continuous Evaluation's output; this
    remains to be confirmed once real scores appear for a real trace id.
    """
    match = re.search(r"^Trace ID:\s*([0-9a-fA-F]{32})\s*$", cli_output, re.MULTILINE)
    return match.group(1) if match else None


def run_window(window: int) -> str:
    """Invoke the hosted agent once per synthetic topic for this window.

    This is real, observable production-like traffic against the hosted
    agent -- kept as evidence of the agent's actual behavior in each window
    (see README.md "Demo") -- but it is not what the batch evaluation in
    ``evaluate_window`` scores. Foundry's evals API drives its own dataset
    against the agent when a run executes; it does not replay or score
    already-recorded conversations. The two are deliberately separate real
    activities against the same real agent, not one pipeline correlated by
    id -- see docs/IMPLEMENTATION.md.
    """
    window_id = str(uuid4())
    folder = WINDOWS / window_id
    manifest = {
        "window_id": window_id, "window": window, "agent_id": AGENT_NAME,
        "started_at": timestamp(), "completed": False, "requests": [],
    }
    save(folder / "window.json", manifest)
    print(f"Window: {window_id} (window {window})", flush=True)
    for index, topic in enumerate(TOPICS):
        request = {"window": window, "topic": topic}
        command = ["azd", "ai", "agent", "invoke", AGENT_NAME, "--new-conversation"]
        if index == 0:
            command.append("--new-session")
        result = subprocess.run([*command, json.dumps(request)], cwd=CONTROL,
                                capture_output=True, text=True, timeout=180)
        if result.returncode:
            raise RuntimeError(f"Hosted invocation failed; window {window_id} remains incomplete")
        trace_id = extract_run_id(result.stdout)
        manifest["requests"].append({"topic": topic, "invoked_at": timestamp(), "trace_id": trace_id})
    manifest.update(completed=True, finished_at=timestamp())
    save(folder / "window.json", manifest)
    print(f"Window {window}: {len(TOPICS)} invocations completed", flush=True)
    return window_id


def run_eval(eval_config: Path) -> dict:
    """Trigger one real batch evaluation run against the hosted agent.

    Uses the ``azd ai agent eval`` CLI (confirmed working end to end against
    a real hosted agent: see ASSESSMENT.md revision note 3) rather than
    Continuous Evaluation, which rejects ``kind: hosted`` agents.
    """
    result = subprocess.run(
        ["azd", "ai", "agent", "eval", "run", "--config", str(eval_config),
         "--name", f"qlt-001-{uuid4()}", "--output", "json", "--no-prompt"],
        cwd=CONTROL, capture_output=True, text=True, timeout=590,
    )
    if result.returncode:
        raise RuntimeError("Eval run failed; see stderr for detail")
    return json.loads(result.stdout)


GROUNDEDNESS_CRITERION = "groundedness"


def fetch_eval_results(project_endpoint: str, eval_id: str, run_id: str) -> tuple[list[dict], bool]:
    """Read the real per-item pass/fail/score results for one eval run.

    Confirmed real schema (2026-09-23) via
    ``openai_client.evals.runs.output_items.list(eval_id, run_id)``: each
    item's ``results`` is a list, one entry per configured testing
    criterion (this control's eval config carries both `builtin.groundedness`
    and an auto-generated rubric evaluator) -- not always length 1. This
    control's authoritative signal is specifically the ``groundedness``
    criterion; require exactly one matching, completed entry per item and
    fail closed on anything else (missing, duplicate, or errored), rather
    than silently picking an arbitrary entry. Requires ``allow_preview=True``
    on ``AIProjectClient`` (the Evaluations v1 API surface); see
    docs/IMPLEMENTATION.md for the disclosed preview dependency this entails.
    """
    try:
        with AzureCliCredential() as credential:
            client = AIProjectClient(project_endpoint, credential, allow_preview=True)
            openai_client = client.get_openai_client()
            items = list(openai_client.evals.runs.output_items.list(eval_id=eval_id, run_id=run_id))
    except (AzureError, HttpResponseError, ValueError, KeyError):
        return [], False
    rows = []
    for item in items:
        dumped = item.model_dump()
        matches = [r for r in (dumped.get("results") or []) if r.get("name") == GROUNDEDNESS_CRITERION]
        if len(matches) != 1 or matches[0].get("status") != "completed":
            return [], False
        rows.append({"run_id": str(dumped["id"]), "passed": matches[0].get("passed"),
                     "score": matches[0].get("score"), "threshold": matches[0].get("threshold")})
    return rows, True


def card(record: dict) -> dict:
    """Build a content-minimized Teams card from the deterministic evidence."""
    decision = record["decision"]
    cannot_evaluate = decision == "cannot_evaluate"
    status = {
        "quality_review_required": {
            "icon": "●", "color": "attention", "container": "attention",
            "title": "QLT-001: Groundedness quality review required",
            "message": "This window's hallucination rate is above threshold, or a critical hallucination was confirmed. Product Owner review requested.",
        },
        "cannot_evaluate": {
            "icon": "⚠", "color": "warning", "container": "warning",
            "title": "QLT-001: Groundedness measurement unavailable",
            "message": "Restore the batch evaluation path before treating this window as healthy.",
        },
        "no_review_required": {
            "icon": "●", "color": "good", "container": "good",
            "title": "QLT-001: No sustained hallucination rate breach",
            "message": "This window's hallucination rate is within threshold and no critical hallucination was confirmed.",
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
        window = record["window"]
        facts.extend([
            {"title": "Window", "value": str(window["number"])},
            {"title": "Sampled runs", "value": str(window["total"])},
            {"title": "Ungrounded", "value": f"{window['ungrounded']}/{window['total']}"},
            {"title": "Rate", "value": f"{window['rate_percent']}%"},
            {"title": "Threshold", "value": f"{record['threshold_percent']}%"},
            {"title": "Critical items", "value": str(len(window["critical_run_ids"]))},
        ])
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
    parser.add_argument("command", choices=["run", "evaluate", "notify", "record-delivery"])
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
        if args.command == "run":
            run_window(args.window)
            return 0
        window_id = str(UUID(args.window_id))
        folder = WINDOWS / window_id
        path = folder / "evidence.json"
        config = settings()
        if args.command == "evaluate":
            with path.with_suffix(".lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                previous = json.loads(path.read_text()) if path.exists() else None
                if previous and previous["decision"] != "cannot_evaluate":
                    record = previous
                else:
                    manifest = json.loads((folder / "window.json").read_text())
                    try:
                        eval_run = run_eval(CONTROL / "eval.yaml")
                        rows, complete = fetch_eval_results(
                            config["FOUNDRY_PROJECT_ENDPOINT"], eval_run["eval_id"], eval_run["id"])
                    except (RuntimeError, KeyError, json.JSONDecodeError, subprocess.TimeoutExpired):
                        rows, complete = [], False
                    manifest["expected_run_ids"] = [row["run_id"] for row in rows]
                    record = evaluate(manifest, rows, retrieval_complete=complete)
                    record = preserve_notification(previous, record)
                    save(path, record)
        elif args.command == "notify":
            record = notify(path, config, retry_rejected=args.retry_rejected)
        else:
            record = record_delivery(path, window_id, args.flow_run_id, args.message_id)
        print(json.dumps({"window_id": window_id, "decision": record["decision"],
                          "reason": record["reason"], "window": record["window"],
                          "notification": record["notification"]}, indent=2))
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
