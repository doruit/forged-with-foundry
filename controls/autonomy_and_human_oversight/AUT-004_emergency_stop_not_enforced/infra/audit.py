"""Show who changed the AUT-004 stop switch, from App Configuration's own audit log.

Run locally as the operator after a stop or recovery. Resource logs reach
Log Analytics a few minutes after the change. Callers are reported as a role
(operator / runtime identity / other) plus an opaque reference; names, emails,
object IDs and IP addresses are never printed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

STATE_PATH = Path(__file__).resolve().parents[1] / ".azure" / "deployment.json"
QUERY = """
AACAudit
| where TimeGenerated > ago(1d)
| where OperationName in ("set-keyvalue", "delete-keyvalue") and Status == "Finished"
| where tostring(parse_json(TargetResource).TargetResourceName) contains "{flag}"
| project TimeGenerated, OperationName, ResultType, CallerIdentity = tostring(CallerIdentity)
| order by TimeGenerated asc
"""


def caller_object_id(caller_identity: str) -> str:
    try:
        entries = json.loads(caller_identity or "[]")
    except json.JSONDecodeError:
        return ""
    for entry in entries if isinstance(entries, list) else []:
        if entry.get("callerIdentityType") == "ObjectId":
            return str(entry.get("callerIdentity", ""))
    return ""


def describe_actor(object_id: str, state: dict) -> dict:
    if not object_id:
        return {"role": "not_recorded", "actor": "not_recorded"}
    if object_id == state.get("operator_principal_id"):
        role = "operator"
    elif object_id == state.get("identityPrincipalId"):
        role = "runtime_identity"
    else:
        role = "other"
    return {"role": role, "actor": "caller-" + hashlib.sha256(object_id.encode()).hexdigest()[:12]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--flag", default="aut004-support-refunds-issue-refund", help="Feature flag name to audit.")
    args = parser.parse_args(argv)
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    workspace = subprocess.run(
        ["az", "monitor", "log-analytics", "workspace", "show", "--ids", state["workspaceId"], "--query", "customerId", "-o", "tsv"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    result = subprocess.run(
        ["az", "monitor", "log-analytics", "query", "--workspace", workspace, "--analytics-query", QUERY.format(flag=args.flag), "-o", "json"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"Audit query failed: {result.stderr.strip()}", file=sys.stderr)
        return 1
    rows = json.loads(result.stdout)
    if not rows:
        print("No audit entries yet; App Configuration resource logs can take several minutes to arrive.")
        return 0
    for row in rows:
        print(json.dumps({
            "time": row["TimeGenerated"],
            "operation": row["OperationName"],
            "result": row["ResultType"],
            **describe_actor(caller_object_id(row["CallerIdentity"]), state),
        }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
