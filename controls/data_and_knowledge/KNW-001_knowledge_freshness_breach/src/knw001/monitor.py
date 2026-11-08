"""Evaluate one KNW-001 run, persist evidence, and route non-fresh decisions."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Callable, Protocol
from uuid import uuid4

import httpx

from .azure_facts import SearchReader, collect_freshness_facts
from .policy import FreshnessDecision, FreshnessPolicy, State, evaluate_freshness


class EvidenceWriter(Protocol):
    def write(self, record: dict) -> None: ...


class BlobEvidenceWriter:
    def __init__(self, container_client) -> None:
        self.container_client = container_client

    def write(self, record: dict) -> None:
        run_id = record["correlation_id"]
        event = record["event_type"]
        if event in {"notification_outcome", "notification_receipt"}:
            role = record.get("notification_role")
            if not isinstance(role, str) or not role:
                raise ValueError("Notification outcome requires its recipient role.")
            role_hash = hashlib.sha256(role.encode()).hexdigest()[:12]
            event = f"{event}-{role_hash}"
        day = record["timestamp"][:10]
        self.container_client.upload_blob(
            name=f"{day}/{run_id}/{event}.json",
            data=json.dumps(record, sort_keys=True),
            overwrite=False,
        )


class HttpNotificationSink:
    def __init__(
        self,
        endpoint: str,
        audience: str,
        credential,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        url = httpx.URL(endpoint)
        if url.scheme != "https" or url.userinfo or url.port not in (None, 443):
            raise ValueError("Notification endpoint must be an HTTPS URL.")
        if not audience.strip():
            raise ValueError("Notification token audience is required.")
        self.endpoint = str(url)
        self.audience = audience
        self.credential = credential
        self.client = client or httpx.Client(timeout=15.0)

    def send(self, payload: dict) -> int:
        token = self.credential.get_token(self.audience).token
        response = self.client.post(
            self.endpoint,
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
        return response.status_code


def run_monitor(
    *,
    policy: FreshnessPolicy,
    source_id: str,
    source_uri: str,
    blob_client,
    reviews_container,
    search_reader: SearchReader,
    evidence_writer: EvidenceWriter,
    accountable_role: str,
    notify: Callable[[dict], int],
    operator_role: str = "Control Operator",
    evaluated_at: datetime | None = None,
    correlation_id: str | None = None,
) -> tuple[FreshnessDecision, dict]:
    timestamp = evaluated_at or datetime.now(UTC)
    run_id = correlation_id or str(uuid4())
    source, attestations, search = collect_freshness_facts(
        source_id=source_id,
        source_uri=source_uri,
        blob_client=blob_client,
        reviews_container=reviews_container,
        search_reader=search_reader,
    )
    decision = evaluate_freshness(policy, source, attestations, search, timestamp)
    notification_roles = _notification_roles(
        decision,
        owner_role=accountable_role,
        operator_role=operator_role,
    )
    evidence = _decision_evidence(
        decision=decision,
        policy=policy,
        source=source,
        attestations=attestations,
        search=search,
        timestamp=timestamp,
        correlation_id=run_id,
        accountable_role=notification_roles[0] if notification_roles else accountable_role,
        notification_roles=notification_roles,
    )
    evidence_writer.write(evidence)

    if not notification_roles:
        return decision, {"status": "not_required"}

    outcomes = []
    for role in notification_roles:
        try:
            status_code = notify(_notification_payload(evidence, recipient_role=role))
            action_status = "accepted" if 200 <= status_code < 300 else "rejected"
            outcome = {
                "status": action_status,
                "http_status": status_code,
                "notification_role": role,
            }
        except Exception as error:
            outcome = {
                "status": "failed",
                "error_type": type(error).__name__,
                "notification_role": role,
            }
        evidence_writer.write({
            "control_id": "KNW-001",
            "policy_version": policy.version,
            "correlation_id": run_id,
            "timestamp": timestamp.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "event_type": "notification_outcome",
            "accountable_role": role,
            **outcome,
        })
        outcomes.append(outcome)

    statuses = {item["status"] for item in outcomes}
    status = "accepted" if statuses == {"accepted"} else "partial" if "accepted" in statuses else "failed"
    return decision, {"status": status, "notifications": outcomes}


def _notification_roles(
    decision: FreshnessDecision,
    *,
    owner_role: str,
    operator_role: str,
) -> list[str]:
    roles = []
    if decision.review_state is State.REVIEW_REQUIRED:
        roles.append(owner_role)
    if decision.review_state is State.CANNOT_EVALUATE or decision.index_state in {
        State.SYNC_PENDING,
        State.CANNOT_EVALUATE,
    }:
        roles.append(operator_role)
    return list(dict.fromkeys(roles))


def _decision_evidence(
    *,
    decision: FreshnessDecision,
    policy: FreshnessPolicy,
    source,
    attestations,
    search,
    timestamp: datetime,
    correlation_id: str,
    accountable_role: str,
    notification_roles: list[str],
) -> dict:
    matching = [
        item for item in (attestations or ())
        if source is not None
        and item.source_id == source.source_id
        and item.source_etag == source.etag
        and item.policy_version == policy.version
        and item.owner_object_id == policy.owner_object_id
    ]
    latest = max(matching, key=lambda item: item.recorded_at) if matching else None
    return {
        "control_id": "KNW-001",
        "policy_version": policy.version,
        "correlation_id": correlation_id,
        "timestamp": timestamp.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "event_type": "freshness_decision",
        "source_id": decision.source_id,
        "source_etag_sha256": hashlib.sha256(source.etag.encode()).hexdigest() if source else None,
        "source_last_modified": source.last_modified.isoformat() if source else None,
        "source_valid_until": source.valid_until.isoformat() if source and source.valid_until else None,
        "indexed_last_modified": search.indexed_last_modified.isoformat()
        if search and search.indexed_last_modified else None,
        "review_record_id": latest.record_id if latest else None,
        "review_recorded_at": latest.recorded_at.isoformat() if latest else None,
        "review_age_days": decision.review_age_days,
        "decision": {
            "overall_state": decision.overall_state.value,
            "review_state": decision.review_state.value,
            "index_state": decision.index_state.value,
            "reason": decision.reason,
        },
        "accountable_role": accountable_role,
        "notification_roles": notification_roles,
    }
def _notification_payload(evidence: dict, *, recipient_role: str) -> dict:
    return {
        "control_id": evidence["control_id"],
        "policy_version": evidence["policy_version"],
        "correlation_id": evidence["correlation_id"],
        "timestamp": evidence["timestamp"],
        "source_id": evidence["source_id"],
        "decision": evidence["decision"],
        "accountable_role": recipient_role,
    }