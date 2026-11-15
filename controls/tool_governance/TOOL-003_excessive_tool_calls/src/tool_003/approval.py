"""Approval channel for a TOOL-003 budget extension.

ACS decides that a person must approve (the policy returns `escalate`) and
calls the host's approval resolver. This module is that resolver's channel for
a command-line demo: the runner writes one request file and waits; the
accountable person runs `python -m src.tool_003 approve <request-id>` (or
`decline`) in a second terminal. Nothing here decides policy.

A decision counts only if it names the exact request (by SHA-256), arrives
before the request expires, and has not been used before. Anything else is
treated as not approved.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import subprocess
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Protocol

REQUEST_SUFFIX = ".request.json"
DECISION_SUFFIX = ".decision.json"
USED_SUFFIX = ".used.json"


class Approver(Protocol):
    def __call__(self, request: dict[str, Any]) -> dict[str, Any]: ...


def _now() -> datetime:
    return datetime.now(UTC)


def build_request(
    *,
    run_id: str,
    task_type: str,
    tool_name: str,
    action_identity: str,
    admitted_calls: int,
    approved_budget: int,
    extra_calls: int,
    ttl_seconds: int,
    contract_sha256: str | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    requested_at = now or _now()
    return {
        "request_id": str(uuid.uuid4()),
        "control_id": "TOOL-003",
        "run_id": run_id,
        "task_type": task_type,
        "tool_name": tool_name,
        "action_identity": action_identity,
        "admitted_calls": admitted_calls,
        "approved_budget": approved_budget,
        "extra_calls_requested": extra_calls,
        "contract_sha256": contract_sha256,
        "requested_at": requested_at.isoformat(),
        "expires_at": (requested_at + timedelta(seconds=ttl_seconds)).isoformat(),
        "accountable_role": "AI Ops Lead",
    }


def request_digest(request: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(request, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _write_private(path: Path, data: dict[str, Any]) -> None:
    """Publish a complete file atomically; fail if the final name already exists."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)  # raises FileExistsError: one publication only
    finally:
        temporary.unlink(missing_ok=True)


def _not_approved(status: str, request: dict[str, Any]) -> dict[str, Any]:
    return {"status": status, "approved": False, "approver_ref": None, "decided_at": None,
            "request_id": request["request_id"]}


def _parses(path: Path) -> bool:
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return True


class FileApprovalChannel:
    """Write a request, then wait for a matching decision until the request expires."""

    def __init__(
        self,
        directory: Path,
        *,
        emit: Callable[[str], None] = print,
        poll_seconds: float = 2.0,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], datetime] = _now,
    ) -> None:
        self.directory = directory
        self.emit = emit
        self.poll_seconds = poll_seconds
        self.sleep = sleep
        self.clock = clock

    def __call__(self, request: dict[str, Any]) -> dict[str, Any]:
        request_id = request["request_id"]
        _write_private(self.directory / f"{request_id}{REQUEST_SUFFIX}", request)
        self.emit(
            f"Approval needed from the {request['accountable_role']}: {request['extra_calls_requested']} extra tool calls "
            f"for run {request['run_id']}. In a second terminal run:\n"
            f"    python -m src.tool_003 approve {request_id}\n"
            f"or  python -m src.tool_003 decline {request_id}\n"
            f"Waiting until {request['expires_at']}; no decision means no extra calls."
        )
        expires_at = datetime.fromisoformat(request["expires_at"])
        decision_path = self.directory / f"{request_id}{DECISION_SUFFIX}"
        while self.clock() < expires_at:
            if decision_path.is_file() and _parses(decision_path):
                return self._consume(decision_path, request, expires_at)
            self.sleep(self.poll_seconds)
        return _not_approved("expired", request)

    def _consume(self, path: Path, request: dict[str, Any], expires_at: datetime) -> dict[str, Any]:
        used = path.with_name(path.name.replace(DECISION_SUFFIX, USED_SUFFIX))
        try:
            path.rename(used)  # single use: a decision file can be consumed once
            decision = json.loads(used.read_text(encoding="utf-8"))
            decided_at = datetime.fromisoformat(decision["decided_at"])
        except (OSError, ValueError, KeyError, TypeError):
            return _not_approved("invalid", request)
        if (
            decision.get("request_id") != request["request_id"]
            or decision.get("request_sha256") != request_digest(request)
            or decided_at > expires_at
            or decision.get("decision") not in {"approve", "decline"}
            or not isinstance(decision.get("approver_ref"), str)
        ):
            return _not_approved("invalid", request)
        approved = decision["decision"] == "approve"
        return {
            "status": "approved" if approved else "declined",
            "approved": approved,
            "approver_ref": decision["approver_ref"],
            "decided_at": decision["decided_at"],
            "request_id": request["request_id"],
        }


def approver_reference(secret: str) -> str:
    """Keyed, opaque reference to the signed-in Azure CLI user.

    An HMAC over tenant and object ID, keyed with a per-deployment secret that
    evidence readers do not hold, so the reference cannot be matched back to a
    person by hashing a directory listing. Never a name or email.
    """
    if len(secret) < 32:
        raise RuntimeError("No approval reference key; run infra/deploy.sh first.")
    result = subprocess.run(
        ["az", "ad", "signed-in-user", "show", "--query", "id", "-o", "tsv"],
        capture_output=True, text=True, check=False,
    )
    tenant = subprocess.run(
        ["az", "account", "show", "--query", "tenantId", "-o", "tsv"],
        capture_output=True, text=True, check=False,
    )
    object_id, tenant_id = result.stdout.strip(), tenant.stdout.strip()
    if result.returncode != 0 or tenant.returncode != 0 or not object_id or not tenant_id:
        raise RuntimeError("Sign in with az login first; the approver must be an identified person.")
    return "approver-" + hmac.new(secret.encode(), f"{tenant_id}:{object_id}".encode(), hashlib.sha256).hexdigest()[:16]


def decide(directory: Path, request_id: str, *, approve: bool, approver_ref: str, now: datetime | None = None) -> dict[str, Any]:
    """Record the accountable person's decision for one pending request."""
    request_path = directory / f"{request_id}{REQUEST_SUFFIX}"
    if not request_path.is_file():
        raise FileNotFoundError(f"No pending request {request_id} in {directory}.")
    if (directory / f"{request_id}{USED_SUFFIX}").exists() or (directory / f"{request_id}{DECISION_SUFFIX}").exists():
        raise FileExistsError(f"A decision was already recorded for request {request_id}.")
    request = json.loads(request_path.read_text(encoding="utf-8"))
    decided_at = now or _now()
    if decided_at >= datetime.fromisoformat(request["expires_at"]):
        raise ValueError("The request has expired; the run already denied the call.")
    decision = {
        "request_id": request_id,
        "request_sha256": request_digest(request),
        "decision": "approve" if approve else "decline",
        "approver_ref": approver_ref,
        "decided_at": decided_at.isoformat(),
    }
    _write_private(directory / f"{request_id}{DECISION_SUFFIX}", decision)  # O_EXCL: one decision only
    return {"request": request, "decision": decision}


class ScriptedApprover:
    """Replay and test stand-in: a fixed answer, recorded as synthetic."""

    def __init__(self, approve: bool) -> None:
        self.approve = approve
        self.requests: list[dict[str, Any]] = []

    def __call__(self, request: dict[str, Any]) -> dict[str, Any]:
        self.requests.append(request)
        return {
            "status": "approved" if self.approve else "declined",
            "approved": self.approve,
            "approver_ref": "approver-scripted-replay",
            "decided_at": _now().isoformat(),
            "request_id": request["request_id"],
        }
