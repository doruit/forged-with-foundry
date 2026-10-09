"""Teams Workflows transport for the existing authenticated ACS action."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import time
from datetime import UTC, datetime
from uuid import UUID

import httpx
from azure.identity import ManagedIdentityCredential
from fastapi import Request

from .auth import Operator, operator_from_headers
from .foundry import AGENT_NAME, RECORD_ID, TOOL_NAME

_routes: dict[str, str] = {}
FLOW_SCOPE = "https://service.flow.microsoft.com//.default"


def validate_workflow_url(value: str) -> str:
    url = httpx.URL(value)
    if url.scheme != "https" or url.userinfo or url.port not in (None, 443) or not (
        url.host.endswith(".logic.azure.com") or url.host.endswith(".environment.api.powerplatform.com")
    ):
        raise ValueError("Unsupported authenticated workflow endpoint")
    return str(url)


def approval_card(pending) -> dict:
    from .cloud_chat import approval_ttl

    expires = datetime.fromtimestamp(pending.created_at + approval_ttl(pending.request.tool_name), UTC).isoformat()
    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard", "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": "AUT-002: Exact action review", "weight": "Bolder", "wrap": True},
            {"type": "FactSet", "facts": [
                {"title": "Agent", "value": AGENT_NAME},
                {"title": "Requester role", "value": ", ".join(pending.actor_roles)},
                {"title": "Actor reference", "value": pending.actor_reference[:16]},
                {"title": "Tool", "value": TOOL_NAME},
                {"title": "Target", "value": RECORD_ID},
                {"title": "Action identity", "value": pending.identity},
                {"title": "Expires (UTC)", "value": expires},
            ]},
        ],
        "actions": [{
            "type": "Action.Submit", "title": title, "associatedInputs": "none",
            "data": {"decision": decision},
        } for title, decision in [("Approve exact action", "approve"), ("Decline", "decline")]],
    }


def result_card(status: str, *, identity: str = "") -> dict:
    titles = {
        "verified": "Action executed and verified",
        "declined": "Declined: action not executed",
        "expired": "Expired: no new execution",
        "denied": "Approval denied: no new execution",
        "unresolved": "Outcome unresolved: do not retry the action",
        "unavailable": "Control unavailable: no approval granted",
    }
    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard", "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": titles[status], "weight": "Bolder", "wrap": True},
            {"type": "FactSet", "facts": [{"title": "Action identity", "value": identity}]},
        ],
    }


def forget_pending(correlation_id: str) -> None:
    _routes.pop(correlation_id, None)


async def publish_pending(pending, session_id: str) -> None:
    url = validate_workflow_url(os.environ["AUT002_WORKFLOW_URL"])
    callback_url = os.environ["AUT002_WORKFLOW_CALLBACK_URL"]
    if httpx.URL(callback_url).scheme != "https":
        raise ValueError("HTTPS callback required")
    _routes[pending.correlation_id] = session_id
    try:
        with ManagedIdentityCredential(client_id=os.environ["AZURE_CLIENT_ID"]) as credential:
            token = await asyncio.to_thread(credential.get_token, FLOW_SCOPE)
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
            response = await client.post(url, headers={"Authorization": f"Bearer {token.token}"}, json={
                "card": approval_card(pending), "callback_url": callback_url,
                "correlation_id": pending.correlation_id, "action_identity": pending.identity,
            })
            response.raise_for_status()
    except Exception:
        forget_pending(pending.correlation_id)
        raise


async def review(data: dict, operator: Operator | None) -> dict:
    from chainlit.context import context_var, init_ws_context
    from chainlit.session import WebsocketSession
    from . import cloud_chat

    status = "denied"
    if operator is None or not operator.can_approve():
        return {"status": status, "card": result_card(status)}
    if not isinstance(data, dict) or set(data) != {"correlation_id", "action_identity", "decision", "responder_object_id"}:
        return {"status": status, "card": result_card(status)}
    if not all(isinstance(value, str) and value for value in data.values()) or data["decision"] not in {"approve", "decline"}:
        return {"status": status, "card": result_card(status)}
    try:
        subject = str(UUID(data["responder_object_id"]))
        secret = os.environ["CHAINLIT_AUTH_SECRET"]
        if len(secret) < 32:
            raise ValueError("invalid_identity_key")
        reference = hmac.new(secret.encode(), f"{os.environ['AUT002_TENANT_ID']}:{subject}".encode(), hashlib.sha256).hexdigest()
    except (ValueError, KeyError):
        return {"status": status, "card": result_card(status)}
    if not hmac.compare_digest(reference, operator.reference):
        return {"status": status, "card": result_card(status)}
    session_id = _routes.get(data["correlation_id"])
    session = WebsocketSession.get_by_id(session_id) if session_id else None
    if session is None:
        return {"status": "expired", "card": result_card("expired")}
    context_token = context_var.set(context_var.get(None))
    identity = ""
    try:
        init_ws_context(session)
        pending = cloud_chat.cl.user_session.get("pending")
        if not isinstance(pending, cloud_chat.PendingDelete) or pending.correlation_id != data["correlation_id"] or pending.identity != data["action_identity"]:
            return {"status": status, "card": result_card(status)}
        identity = pending.identity
        if time.time() - pending.created_at >= cloud_chat.approval_ttl(pending.request.tool_name):
            status = "expired"
        elif data["decision"] == "approve":
            status = await cloud_chat.approve_as(operator, narrate=False)
        else:
            status = await cloud_chat.decline_action()
    except Exception:
        status = "unresolved"
    finally:
        context_var.reset(context_token)
    return {"status": status, "card": result_card(status, identity=identity)}


def install(app) -> None:
    @app.post("/api/teams/review")
    async def callback(request: Request):
        operator = operator_from_headers(
            request.headers, tenant=os.environ.get("AUT002_TENANT_ID", ""),
            secret=os.environ.get("CHAINLIT_AUTH_SECRET", ""),
        )
        try:
            data = await request.json()
        except ValueError:
            data = None
        return await review(data, operator)