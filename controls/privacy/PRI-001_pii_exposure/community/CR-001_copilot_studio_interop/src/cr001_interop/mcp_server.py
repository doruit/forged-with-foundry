"""OPTIONAL: MCP Streamable HTTP tool server exposing PRI-001's PII gate.

Community-requested extension (see ASSESSMENT.md's optional-extension
section) so any MCP-compatible caller -- for example a Copilot Studio agent
via its MCP connector -- can reach the same fail-closed PII redaction PRI-001
already enforces around its Chainlit agent turn. This module wires together,
unchanged, three pieces the core demo already validated: ``text_pii``/
``document_pii`` (detection + redaction), ``escalation`` (metadata-only
escalation event), and the ACS ``pre_tool_call``/``post_tool_call`` gate in
``acs_gate.py``. It adds only the MCP transport, correlation-aware evidence
emission (``evidence.py``), and an optional identity boundary -- no new PII
decision logic.

Run locally with: ``uvicorn src.cr001_interop.mcp_server:create_app --factory``
"""

from __future__ import annotations

import base64
import logging
import os
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from src.pri_001 import document_pii, escalation, text_pii
from src.pri_001.models import PolicyAction

from .acs_gate import get_pii_tool_control
from .evidence import DEFAULT_POLICY_VERSION, EvidenceEvent, record_event, validate_identifier

logger = logging.getLogger("cr001_interop.mcp_server")

_CONTROL_ID = "PRI-001"
_PROTOCOL = "mcp"

_ACTION_TO_EVIDENCE_DECISION: dict[PolicyAction, str] = {
    PolicyAction.ALLOW: "allow",
    PolicyAction.REDACT_AND_ESCALATE: "redact",
    # BLOCK is never actually produced by enforce_text_pii/enforce_document_pii
    # (only policy.fail_closed(), used by chat.py, does that) -- kept for
    # parity with core PRI-001's acs_gate.py exhaustive mapping.
    PolicyAction.BLOCK: "deny",
}


def _allowed_hosts() -> list[str]:
    """Loopback defaults plus the App Service hostname when hosted remotely."""
    hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    hosted_name = os.environ.get("WEBSITE_HOSTNAME") or os.environ.get("CR001_PUBLIC_HOSTNAME")
    if hosted_name:
        hosts.append(hosted_name)
    return hosts


mcp = FastMCP(
    "pri-001-pii-mcp-gate",
    transport_security=TransportSecuritySettings(allowed_hosts=_allowed_hosts()),
)


async def _run_gated(tool_name: str, args: dict[str, Any], execute) -> dict[str, Any]:
    """Route one tool call through the ACS pre_tool_call/post_tool_call gate."""
    control = get_pii_tool_control()
    result = await control.run_tool(tool_name, args, execute, approval_resolver=None)
    return result.value


def _emit_control_evidence(
    *, agent_id: str, run_id: str, trace_id: str, decision: str, pii_count: int, categories: tuple[str, ...]
) -> None:
    record_event(
        EvidenceEvent(
            event_name="pii.control.evaluated",
            agent_id=agent_id,
            platform="copilot_studio",
            run_id=run_id,
            trace_id=trace_id,
            control_id=_CONTROL_ID,
            control_required=True,
            protocol=_PROTOCOL,
            policy_version=DEFAULT_POLICY_VERSION,
            decision=decision,
            redaction_count=pii_count,
            pii_categories=categories,
            outcome="success" if decision != "error" else "failure",
        )
    )


@mcp.tool()
async def redact_text(
    text: str, agent_id: str, run_id: str, trace_id: str, language: str = "en"
) -> dict[str, Any]:
    """Detect and redact PII in plain text before it reaches any calling agent."""
    # agent_id/run_id/trace_id are caller-supplied MCP tool arguments -- an
    # untrusted model could pass anything here (an email address has been
    # observed in practice). Reject before any processing or evidence write;
    # the rejected value itself is never echoed back.
    validate_identifier("agent_id", agent_id)
    validate_identifier("run_id", run_id)
    validate_identifier("trace_id", trace_id)

    async def execute(effective_args: dict[str, Any]) -> dict[str, Any]:
        enforcement = await text_pii.enforce_text_pii(
            effective_args["text"], effective_args.get("language", "en")
        )
        decision = enforcement.decision
        if decision.action is PolicyAction.REDACT_AND_ESCALATE:
            await escalation.escalate(decision, source_type="cr001_mcp_redact_text")
        return {
            "redacted_text": enforcement.redacted_text,
            "pii_count": decision.pii_count,
            "categories": list(decision.categories),
            "action": decision.action.value,
        }

    try:
        result = await _run_gated(
            "redact_text", {"text": text, "language": language}, execute
        )
    except text_pii.PiiEnforcementError:
        _emit_control_evidence(
            agent_id=agent_id, run_id=run_id, trace_id=trace_id,
            decision="error", pii_count=0, categories=(),
        )
        raise

    _emit_control_evidence(
        agent_id=agent_id,
        run_id=run_id,
        trace_id=trace_id,
        decision=_ACTION_TO_EVIDENCE_DECISION[PolicyAction(result["action"])],
        pii_count=result["pii_count"],
        categories=tuple(result["categories"]),
    )
    return result


@mcp.tool()
async def redact_document(
    filename: str,
    content_base64: str,
    agent_id: str,
    run_id: str,
    trace_id: str,
    language: str = "en",
) -> dict[str, Any]:
    """Detect and redact PII in an uploaded PDF/DOCX/TXT before any calling agent sees it."""
    validate_identifier("agent_id", agent_id)
    validate_identifier("run_id", run_id)
    validate_identifier("trace_id", trace_id)

    async def execute(effective_args: dict[str, Any]) -> dict[str, Any]:
        content = base64.b64decode(effective_args["content_base64"])
        enforcement = await document_pii.enforce_document_pii(
            effective_args["filename"], content, effective_args.get("language", "en")
        )
        decision = enforcement.decision
        if decision.action is PolicyAction.REDACT_AND_ESCALATE:
            await escalation.escalate(decision, source_type="cr001_mcp_redact_document")
        return {
            "redacted_filename": enforcement.redacted_name,
            "redacted_content_base64": base64.b64encode(enforcement.redacted_bytes).decode("ascii"),
            "pii_count": decision.pii_count,
            "categories": list(decision.categories),
            "action": decision.action.value,
        }

    try:
        result = await _run_gated(
            "redact_document",
            {"filename": filename, "content_base64": content_base64, "language": language},
            execute,
        )
    except document_pii.PiiEnforcementError:
        _emit_control_evidence(
            agent_id=agent_id, run_id=run_id, trace_id=trace_id,
            decision="error", pii_count=0, categories=(),
        )
        raise

    _emit_control_evidence(
        agent_id=agent_id,
        run_id=run_id,
        trace_id=trace_id,
        decision=_ACTION_TO_EVIDENCE_DECISION[PolicyAction(result["action"])],
        pii_count=result["pii_count"],
        categories=tuple(result["categories"]),
    )
    return result


class BearerAuthMiddleware:
    """ASGI middleware rejecting requests without a valid Entra ID access token.

    This is the identity boundary for the *optional* live-tenant appendix --
    kept separate from the ACS content boundary above, and only active when
    ``CR001_ENTRA_TENANT_ID``/``CR001_ENTRA_AUDIENCE`` are configured. The
    local-first demo runs with no auth at all.
    """

    def __init__(self, app, tenant_id: str, audience: str) -> None:
        from jwt import PyJWKClient  # local import: only needed when auth is enabled

        self._app = app
        self._audience = audience
        self._issuer = f"https://login.microsoftonline.com/{tenant_id}/v2.0"
        self._jwks_client = PyJWKClient(
            f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
        )

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        auth_header = headers.get(b"authorization", b"").decode("latin-1")
        token = auth_header[len("Bearer "):].strip() if auth_header.startswith("Bearer ") else ""
        if not token or not self._token_is_valid(token):
            await send(
                {
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [(b"content-type", b"application/json")],
                }
            )
            await send({"type": "http.response.body", "body": b'{"error": "invalid_or_missing_bearer_token"}'})
            return

        await self._app(scope, receive, send)

    def _token_is_valid(self, token: str) -> bool:
        import jwt

        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
            jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self._audience,
                issuer=self._issuer,
            )
        except jwt.PyJWTError:
            logger.warning("CR-001 MCP gate rejected an invalid bearer token.")
            return False
        return True


def create_app():
    """ASGI app factory: ``uvicorn src.cr001_interop.mcp_server:create_app --factory``.

    Runs with no authentication by default (local-first demo). Set
    ``CR001_ENTRA_TENANT_ID`` and ``CR001_ENTRA_AUDIENCE`` to enable the
    optional Entra ID bearer-token boundary described in this folder's
    README appendix.
    """
    app = mcp.streamable_http_app()
    tenant_id = os.getenv("CR001_ENTRA_TENANT_ID")
    audience = os.getenv("CR001_ENTRA_AUDIENCE")
    if tenant_id and audience:
        return BearerAuthMiddleware(app, tenant_id=tenant_id, audience=audience)
    return app

