from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import logging
import os
from pathlib import Path
import sys

import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from knw001.auth import authenticated_object_id
from knw001.azure_facts import AzureSearchReader
from knw001.monitor import BlobEvidenceWriter, HttpNotificationSink, run_monitor
from knw001.policy import FreshnessPolicy
from knw001.review import record_review_attestation

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"Required application setting {name} is missing.")
    return value


def _policy() -> FreshnessPolicy:
    return FreshnessPolicy(
        source_id=_required("KNW001_SOURCE_ID"),
        owner_object_id=_required("KNW001_OWNER_OBJECT_ID").lower(),
        maximum_review_age_days=int(_required("KNW001_MAX_REVIEW_AGE_DAYS")),
        version=_required("KNW001_POLICY_VERSION"),
    )


def _clients():
    credential = DefaultAzureCredential()
    blob_endpoint = _required("KNW001_BLOB_ENDPOINT")
    blob_service = BlobServiceClient(blob_endpoint, credential=credential)
    source_container = _required("KNW001_SOURCE_CONTAINER")
    source_blob = _required("KNW001_SOURCE_BLOB")
    source_client = blob_service.get_blob_client(source_container, source_blob)
    reviews = blob_service.get_container_client(_required("KNW001_REVIEWS_CONTAINER"))
    evidence = BlobEvidenceWriter(
        blob_service.get_container_client(_required("KNW001_EVIDENCE_CONTAINER"))
    )
    source_uri = source_client.url
    search = AzureSearchReader(
        endpoint=_required("KNW001_SEARCH_ENDPOINT"),
        index_name=_required("KNW001_SEARCH_INDEX"),
        indexer_name=_required("KNW001_SEARCH_INDEXER"),
        credential=credential,
    )
    return credential, source_client, reviews, evidence, search, source_uri


def _notifier(credential):
    endpoint = os.environ.get("KNW001_NOTIFICATION_ENDPOINT", "").strip()
    audience = os.environ.get("KNW001_NOTIFICATION_AUDIENCE", "").strip()
    if not endpoint and not audience:
        return lambda _payload: (_ for _ in ()).throw(
            RuntimeError("Notification sink is not configured.")
        )
    if not endpoint or not audience:
        raise ValueError("Notification endpoint and audience must be configured together.")
    return HttpNotificationSink(endpoint, audience, credential).send


@app.timer_trigger(schedule="0 0 7 * * *", arg_name="timer", use_monitor=True)
def freshness_timer(timer: func.TimerRequest) -> None:
    del timer
    policy = _policy()
    credential, source, reviews, evidence, search, source_uri = _clients()
    try:
        decision, action = run_monitor(
            policy=policy,
            source_id=policy.source_id,
            source_uri=source_uri,
            blob_client=source,
            reviews_container=reviews,
            search_reader=search,
            evidence_writer=evidence,
            accountable_role=os.environ.get("KNW001_ACCOUNTABLE_ROLE", "Knowledge Owner"),
            notify=_notifier(credential),
        )
        logging.info(
            "knw001_run_complete overall_state=%s notification_status=%s",
            decision.overall_state.value,
            action["status"],
        )
    except Exception as error:
        logging.error("knw001_run_failed error_type=%s", type(error).__name__)
        raise


_NOTIFICATION_FIELDS = {
    "control_id", "policy_version", "correlation_id", "timestamp",
    "source_id", "decision", "accountable_role",
}


def _evidence_writer() -> BlobEvidenceWriter:
    blob_service = BlobServiceClient(
        _required("KNW001_BLOB_ENDPOINT"), credential=DefaultAzureCredential()
    )
    return BlobEvidenceWriter(
        blob_service.get_container_client(_required("KNW001_EVIDENCE_CONTAINER"))
    )


@app.route(route="notifications", methods=["POST"])
def notification_inbox(req: func.HttpRequest) -> func.HttpResponse:
    """Minimal operator inbox: records an authenticated, minimized receipt."""
    if os.environ.get("KNW001_EASY_AUTH_CONFIGURED") != "true":
        return func.HttpResponse("Notification authentication is not configured.", status_code=503)
    try:
        sender_id = authenticated_object_id(req.headers.get("X-MS-CLIENT-PRINCIPAL"))
    except PermissionError:
        return func.HttpResponse("Authenticated sender required.", status_code=403)
    if sender_id != os.environ.get("KNW001_NOTIFIER_OBJECT_ID", "").strip().lower():
        return func.HttpResponse("Only the KNW-001 monitor identity may notify.", status_code=403)
    try:
        payload = req.get_json()
    except ValueError:
        return func.HttpResponse("Invalid JSON body.", status_code=400)
    if (
        not isinstance(payload, dict)
        or set(payload) != _NOTIFICATION_FIELDS
        or payload.get("control_id") != "KNW-001"
        or not isinstance(payload.get("decision"), dict)
        or not isinstance(payload.get("accountable_role"), str)
        or not isinstance(payload.get("correlation_id"), str)
    ):
        return func.HttpResponse("Unexpected notification payload.", status_code=400)
    received_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    record = {
        "control_id": "KNW-001",
        "policy_version": payload["policy_version"],
        "correlation_id": payload["correlation_id"],
        "timestamp": received_at,
        "event_type": "notification_receipt",
        "notification_role": payload["accountable_role"],
        "accountable_role": payload["accountable_role"],
        "overall_state": payload["decision"].get("overall_state"),
        "payload_sha256": hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode()
        ).hexdigest(),
    }
    try:
        _evidence_writer().write(record)
    except Exception as error:
        logging.error("knw001_receipt_failed error_type=%s", type(error).__name__)
        return func.HttpResponse("Receipt could not be recorded.", status_code=503)
    return func.HttpResponse(status_code=202)


@app.route(route="review", methods=["POST"])
def review_source(req: func.HttpRequest) -> func.HttpResponse:
    if os.environ.get("KNW001_EASY_AUTH_CONFIGURED") != "true":
        return func.HttpResponse("Review authentication is not configured.", status_code=503)
    try:
        actor_id = authenticated_object_id(
            req.headers.get("X-MS-CLIENT-PRINCIPAL")
        )
    except PermissionError:
        return func.HttpResponse("Authenticated Entra owner required.", status_code=403)

    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse("Invalid JSON body.", status_code=400)
    if (
        not isinstance(body, dict)
        or set(body) != {"confirm_review", "source_etag", "policy_version"}
        or body.get("confirm_review") is not True
        or not isinstance(body.get("source_etag"), str)
        or not isinstance(body.get("policy_version"), str)
    ):
        return func.HttpResponse("A review confirmation for the displayed revision is required.", status_code=400)

    try:
        policy = _policy()
        _, source, reviews, _, _, _ = _clients()
        attestation = record_review_attestation(
            policy=policy,
            blob_client=source,
            reviews_container=reviews,
            authenticated_owner_object_id=actor_id,
            submitted_etag=body["source_etag"],
            submitted_policy_version=body["policy_version"],
        )
        response = {
            "record_id": attestation.record_id,
            "recorded_at": attestation.recorded_at.isoformat().replace("+00:00", "Z"),
            "source_etag_sha256": hashlib.sha256(attestation.source_etag.encode()).hexdigest(),
        }
        return func.HttpResponse(json.dumps(response), status_code=201, mimetype="application/json")
    except PermissionError:
        return func.HttpResponse("Only the configured Knowledge Owner may attest review.", status_code=403)
    except ValueError:
        return func.HttpResponse("The source revision or policy changed; reload before reviewing.", status_code=409)
    except Exception as error:
        logging.error("knw001_review_failed error_type=%s", type(error).__name__)
        return func.HttpResponse("Review could not be recorded.", status_code=503)