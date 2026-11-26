"""Governance action: open or update a GitHub issue owned by the QA Lead, then read it back."""

from __future__ import annotations

import json
import subprocess

LABELS = {"change_cycle_required": "qlt-006-change-cycle", "measurement_failed": "qlt-006-measurement-failed"}
TITLES = {
    "change_cycle_required": "QLT-006: change cycle required for {agent}",
    "measurement_failed": "QLT-006: production regression could not be measured for {agent}",
}


def _gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def body(record: dict) -> str:
    """Content-minimized issue body: decision, numbers and IDs only."""

    lines = [
        f"**Decision:** `{record['decision']}` ({record['reason']})",
        f"**Accountable role:** {record['accountable_role']}",
        f"**Live agent version:** {record['live']['agent_version']} on `{record['live']['model']}`",
        f"**Release baseline:** {record['baseline']['record_sha256'][:12]} (evaluation run `{record['baseline']['evaluation_run_id']}`)",
        f"**Threshold:** {record['threshold_pp']} percentage points",
        "",
        "| Evaluator | Baseline | Live | Drop (pp) |",
        "|---|---|---|---|",
    ]
    for name, delta in record.get("deltas_pp", {}).items():
        lines.append(f"| {name} | {record['baseline']['pass_rates'][name]} | {record['live_rates'][name]} | {delta} |")
    lines += ["", f"Evidence ID: `{record['correlation_id']}`. Close this issue only after a new CHG-002-gated release or an accepted risk."]
    return "\n".join(lines)


def open_issue(repository: str, record: dict) -> dict:
    label = LABELS[record["decision"]]
    title = TITLES[record["decision"]].format(agent=record["agent"])
    _gh("label", "create", label, "-R", repository, "--color", "F59E0B", "--force",
        "--description", "Opened by the QLT-006 Forged with Foundry demo")
    existing = json.loads(_gh("issue", "list", "-R", repository, "--label", label, "--state", "open",
                              "--json", "number,title", "--limit", "50"))
    match = next((i for i in existing if i["title"] == title), None)
    if match:
        number = match["number"]
        _gh("issue", "comment", str(number), "-R", repository, "--body", body(record))
        action = "commented"
    else:
        url = _gh("issue", "create", "-R", repository, "--title", title, "--label", label, "--body", body(record)).strip()
        number = int(url.rstrip("/").rsplit("/", 1)[1])
        action = "created"
    view = json.loads(_gh("issue", "view", str(number), "-R", repository, "--json", "state,labels,url"))
    verified = view["state"] == "OPEN" and any(l["name"] == label for l in view["labels"])
    return {"action": action, "issue": number, "url": view["url"], "verified": verified}
