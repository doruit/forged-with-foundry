"""Run, evaluate, and notify for the isolated VAL-001 synthetic demonstration."""

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
from azure.core.exceptions import AzureError
from azure.identity import AzureCliCredential
from azure.monitor.query import LogsQueryClient, LogsQueryStatus

from evaluator import evaluate

CONTROL = Path(__file__).resolve().parent
RUNS = CONTROL / ".azure/val001/runs"
FLOW_TOKEN_SCOPE = "https://service.flow.microsoft.com//.default"
CONTRACT = CONTROL.parent / "VAL-PRE-001_value_hypothesis_missing/fixtures/complete-workload/.fwf/agents/helpdesk-tier1-triage/governance.yaml"


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


def run_scenario(scenario: str) -> str:
    """Record expected tickets before invoking the real hosted workload."""
    run_id = str(uuid4())
    folder = RUNS / run_id
    counts, total = {"underperforming": ((1, 1), 5), "healthy": ((2, 2), 5),
                     "mixed": ((1, 2), 5), "boundary": ((7, 7), 25)}[scenario]
    manifest = {"run_id": run_id, "scenario": scenario, "started_at": timestamp(),
                "completed": False, "periods": []}
    for sequence, count in enumerate(counts, 1):
        tickets = [{"ticket_id": f"ticket-{number:04d}",
                    "kind": "account_unlock" if number <= count else "hardware_repair"}
                   for number in range(1, total + 1)]
        manifest["periods"].append({"sequence": sequence, "tickets": tickets})
    save(folder / "run.json", manifest)
    print(f"Run: {run_id}", flush=True)
    first = True
    for period in manifest["periods"]:
        for ticket in period["tickets"]:
            request = {"run_id": run_id, "period": period["sequence"], **ticket}
            command = ["azd", "ai", "agent", "invoke", "helpdesk-tier1-triage", "--new-conversation"]
            if first:
                command.append("--new-session")
            first = False
            result = subprocess.run([*command, json.dumps(request)], cwd=CONTROL,
                                    capture_output=True, text=True, timeout=180)
            if result.returncode:
                raise RuntimeError(f"Hosted invocation failed; run {run_id} remains incomplete")
        print(f"Period {period['sequence']}: {total} invocations completed", flush=True)
    manifest.update(completed=True, finished_at=timestamp())
    save(folder / "run.json", manifest)
    return run_id


def query_outcomes(workspace_id: str, run_id: str) -> tuple[list[dict], bool]:
    """Query raw events without filtering away malformed outcomes or duplicates."""
    if str(UUID(run_id)) != run_id:
        return [], False
    query = ("AppEvents | where Name == 'TicketTriaged' "
             f"| where tostring(Properties.run_id) == '{run_id}' "
             "| project Properties, ItemCount")
    try:
        with AzureCliCredential() as credential, LogsQueryClient(credential) as client:
            result = client.query_workspace(workspace_id, query, timespan=None)
        if result.status != LogsQueryStatus.SUCCESS or len(result.tables) != 1:
            return [], False
        rows = []
        for properties, count in result.tables[0].rows:
            rows.append({"properties": json.loads(properties) if isinstance(properties, str)
                         else properties, "item_count": count})
        return rows, True
    except (AzureError, ValueError, TypeError):
        return [], False


def card(record: dict) -> dict:
    """Build a content-minimized Teams card from the deterministic evidence."""
    decision = record["decision"]
    cannot_evaluate = decision == "cannot_evaluate"
    status = {
        "review_required": {
            "icon": "●", "color": "attention", "container": "attention",
            "title": "VAL-001: Value review required",
            "message": "Both measured periods are below threshold. Business Owner review requested.",
        },
        "cannot_evaluate": {
            "icon": "⚠", "color": "warning", "container": "warning",
            "title": "VAL-001: KPI measurement unavailable",
            "message": "Restore the measurement path before treating this KPI as healthy.",
        },
        "no_review_required": {
            "icon": "●", "color": "good", "container": "good",
            "title": "VAL-001: No sustained underperformance",
            "message": "At least one measured period is at or above the threshold. No two-period review trigger was observed.",
        },
    }.get(decision, {
        "icon": "⚠", "color": "warning", "container": "warning",
        "title": "VAL-001: Decision requires attention",
        "message": "The control returned an unexpected decision. Check the evidence record.",
    })
    facts = [{"title": "Correlation", "value": record["correlation_id"]},
             {"title": "Recipient role",
              "value": record["notification"].get("recipient_role", "unknown")},
             {"title": "Reason", "value": record.get("reason", "not_recorded")}]
    if cannot_evaluate:
        facts.append({"title": "Accountable role", "value": "AI Governance Operations"})
    else:
        facts.extend([
            {"title": "Owner", "value": record["owner"]},
            {"title": "Target", "value": f"{record['target_percent']}%"},
            {"title": "Threshold", "value": f"{record['threshold_percent']}%"},
        ])
        facts.extend({"title": f"Period {period['sequence']}",
                      "value": f"{period['deflected']}/{period['total']} ({period['percent']}%)"}
                     for period in record["periods"])
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
    """Route business findings and measurement failures to different roles."""
    if record["decision"] == "review_required":
        return config.get("VAL001_TEAMS_WEBHOOK_URL", ""), "Business Owner"
    if record["decision"] == "cannot_evaluate":
        return config.get("VAL001_GOVERNANCE_TEAMS_WEBHOOK_URL", ""), "AI Governance Operations"
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
    parser.add_argument("--scenario", choices=["underperforming", "healthy", "mixed", "boundary"], default="underperforming")
    parser.add_argument("--run-id")
    parser.add_argument("--retry-rejected", action="store_true",
                        help="Explicitly retry only a prior HTTP 401/403 rejection after fixing authentication")
    parser.add_argument("--contract", type=Path, default=CONTRACT)
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


def record_delivery(path: Path, run_id: str, flow_run_id: str, message_id: str) -> dict:
    """Record an operator's checked service receipt, not an automatic delivery claim."""
    if not flow_run_id or not flow_run_id.isalnum() or not message_id or not message_id.isdecimal():
        raise ValueError("Valid service receipt identifiers are required")
    with path.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        record = json.loads(path.read_text())
        if record["correlation_id"] != run_id or record["notification"]["status"] != "accepted":
            raise ValueError("Receipt requires this run's accepted notification")
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
            run_scenario(args.scenario)
            return 0
        run_id = str(UUID(args.run_id))
        folder = RUNS / run_id
        path = folder / "evidence.json"
        config = settings()
        if args.command == "evaluate":
            folder.mkdir(parents=True, exist_ok=True)
            with path.with_suffix(".lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                previous = json.loads(path.read_text()) if path.exists() else None
                if previous and previous["decision"] != "cannot_evaluate":
                    record = previous
                else:
                    manifest = json.loads((folder / "run.json").read_text())
                    rows, complete = query_outcomes(config.get("VAL001_WORKSPACE_ID", ""), run_id)
                    record = evaluate(args.contract, manifest, rows, query_complete=complete)
                    record = preserve_notification(previous, record)
                    save(path, record)
        elif args.command == "notify":
            record = notify(path, config, retry_rejected=args.retry_rejected)
        else:
            record = record_delivery(path, run_id, args.flow_run_id, args.message_id)
        print(json.dumps({"run_id": run_id, "decision": record["decision"],
                          "reason": record["reason"], "periods": record["periods"],
                          "notification": record["notification"]}, indent=2))
        if record["decision"] == "cannot_evaluate":
            return 2
        if args.command == "notify" and record["notification"]["status"] not in (
                "accepted", "delivered", "not_requested"):
            return 1
        return 0
    except (OSError, ValueError, TypeError, RuntimeError, subprocess.SubprocessError):
        print("Step failed. Check configuration and retained run state; no healthy result is inferred.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())