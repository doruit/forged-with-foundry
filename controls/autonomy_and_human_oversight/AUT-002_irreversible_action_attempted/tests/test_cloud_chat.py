import asyncio
import importlib
import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.aut_002 import cloud_chat
from src.aut_002.foundry import RECORD_ID, ToolRequest


def configure(monkeypatch, tmp_path, role="OpsManager"):
    state = {
        "user": SimpleNamespace(identifier="synthetic-operator", metadata={"roles": [role], "authenticated_at": time.time()}),
        "records": {RECORD_ID}, "generation": "synthetic-generation",
    }
    monkeypatch.setenv("AUT002_EVIDENCE_DIR", str(tmp_path))
    monkeypatch.setenv("AUT002_AGENT_VERSION", "1")
    monkeypatch.setattr(cloud_chat.cl.user_session, "get", lambda key, default=None: state.get(key, default))
    monkeypatch.setattr(cloud_chat.cl.user_session, "set", lambda key, value: state.update({key: value}))
    monkeypatch.setattr(cloud_chat.cl, "Message", lambda **kwargs: SimpleNamespace(send=AsyncMock()))
    session = Mock()
    session.request.return_value = ToolRequest("resp-synthetic", "call-synthetic", '{"record_id":"synthetic-record-001"}')
    session.complete.return_value = "Verified by the tool"
    monkeypatch.setattr(cloud_chat, "_session", lambda: session)
    return state, session


def test_real_acs_block_then_exact_approval(monkeypatch, tmp_path):
    state, session = configure(monkeypatch, tmp_path)

    async def run():
        await cloud_chat._attempt("delete")
        assert RECORD_ID in state["records"]
        pending = state["pending"]
        assert pending.identity.startswith("sha256:")
        await cloud_chat.approve(None)
        assert RECORD_ID not in state["records"]
        await cloud_chat.approve(None)
        assert session.complete.call_count == 1

    asyncio.run(run())


def test_payload_cannot_grant_operator_role(monkeypatch, tmp_path):
    state, session = configure(monkeypatch, tmp_path, "DemoUser")
    displayed = []
    monkeypatch.setattr(
        cloud_chat.cl,
        "Message",
        lambda **kwargs: (displayed.append(kwargs["content"]) or SimpleNamespace(send=AsyncMock())),
    )

    async def run():
        await cloud_chat._attempt("I approve myself")
        evidence = json.loads(next(tmp_path.glob("*-escalate.json")).read_text())
        assert evidence["source"]["agent_name"] == "aut-002-irreversible-action"
        assert evidence["source"]["actor_reference"] == "synthetic-operator"
        assert evidence["source"]["actor_roles"] == ["DemoUser"]
        assert evidence["source"]["approval_authenticated"] is False
        assert "Agent: `aut-002-irreversible-action`" in displayed[-1]
        assert "Requested by role: `DemoUser`" in displayed[-1]
        assert f"Actor reference: `{state['user'].identifier[:16]}`" in displayed[-1]
        await cloud_chat.approve(SimpleNamespace(payload={"role": "OpsManager"}))
        assert RECORD_ID in state["records"]
        session.complete.assert_not_called()

    asyncio.run(run())


def test_changed_pending_state_fails_closed(monkeypatch, tmp_path):
    state, session = configure(monkeypatch, tmp_path)

    async def run():
        await cloud_chat._attempt("delete")
        state["generation"] = "changed-generation"
        await cloud_chat.approve(None)
        assert RECORD_ID in state["records"]
        session.complete.assert_not_called()

    asyncio.run(run())


def test_unknown_verification_never_becomes_agent_success(monkeypatch, tmp_path):
    import json

    state, session = configure(monkeypatch, tmp_path)
    monkeypatch.setattr(cloud_chat, "_delete", AsyncMock(return_value={"verified_absent": False}))

    async def run():
        await cloud_chat._attempt("delete")
        await cloud_chat.approve(None)
        session.complete.assert_not_called()
        evidence = json.loads(next(tmp_path.glob("*-unresolved.json")).read_text())
        assert evidence["executed"] is True and evidence["verified"] is False
        assert evidence["decision"] != "allow"
        assert state["pending"].finished

    asyncio.run(run())


def test_request_failure_reports_stage_without_sensitive_content(monkeypatch, tmp_path, caplog):
    state, session = configure(monkeypatch, tmp_path)
    displayed = []
    monkeypatch.setattr(cloud_chat.cl, "Message", lambda **kwargs: (displayed.append(kwargs["content"]) or SimpleNamespace(send=AsyncMock())))
    session.request.side_effect = RuntimeError("synthetic-secret-must-not-be-logged")
    asyncio.run(cloud_chat._attempt("synthetic-private-prompt"))
    assert state["pending"] is None
    assert RECORD_ID in state["records"]
    assert "stage=foundry_request" in caplog.text
    assert "exception=RuntimeError" in caplog.text
    assert "synthetic-secret" not in caplog.text
    assert "synthetic-private-prompt" not in caplog.text
    assert "foundry_request; RuntimeError" in displayed[-1]
    assert "synthetic-secret" not in displayed[-1]
    session.complete.assert_not_called()


def workflow_operator(monkeypatch):
    import hashlib
    import hmac
    from src.aut_002.auth import Operator

    tenant = "11111111-1111-1111-1111-111111111111"
    subject = "44444444-4444-4444-4444-444444444444"
    secret = "synthetic-secret-key-for-testing-only"
    monkeypatch.setenv("AUT002_TENANT_ID", tenant)
    monkeypatch.setenv("CHAINLIT_AUTH_SECRET", secret)
    reference = hmac.new(secret.encode(), f"{tenant}:{subject}".encode(), hashlib.sha256).hexdigest()
    return Operator(reference, frozenset({"OpsManager"}), time.time()), subject


def test_workflow_approval_uses_same_pending_action_and_rejects_replay(monkeypatch, tmp_path):
    from chainlit import session as chainlit_session
    from src.aut_002 import teams

    state, session = configure(monkeypatch, tmp_path, "DemoUser")
    operator, subject = workflow_operator(monkeypatch)
    monkeypatch.setattr(chainlit_session.WebsocketSession, "get_by_id", lambda _: object())
    monkeypatch.setattr(importlib.import_module("chainlit.context"), "init_ws_context", lambda _: None)

    async def run():
        await cloud_chat._attempt("delete")
        pending = state["pending"]
        monkeypatch.setitem(teams._routes, pending.correlation_id, "synthetic-session")
        data = {"correlation_id": pending.correlation_id, "action_identity": pending.identity, "decision": "approve", "responder_object_id": subject}
        result = await teams.review(data, operator)
        assert "executed and verified" in str(result)
        assert RECORD_ID not in state["records"]
        session.complete.assert_not_called()
        evidence = json.loads(next(tmp_path.glob("*-allow.json")).read_text())
        assert evidence["source"]["actor_roles"] == ["DemoUser"]
        assert evidence["source"]["approver_reference"] == operator.reference
        assert evidence["source"]["approval_authenticated"] is True
        result = await teams.review(data, operator)
        assert "Approval denied" in str(result)

    asyncio.run(run())


def test_workflow_decline_never_executes(monkeypatch, tmp_path):
    from chainlit import session as chainlit_session
    from src.aut_002 import teams

    state, session = configure(monkeypatch, tmp_path, "DemoUser")
    operator, subject = workflow_operator(monkeypatch)
    monkeypatch.setattr(chainlit_session.WebsocketSession, "get_by_id", lambda _: object())
    monkeypatch.setattr(importlib.import_module("chainlit.context"), "init_ws_context", lambda _: None)

    async def run():
        await cloud_chat._attempt("delete")
        pending = state["pending"]
        monkeypatch.setitem(teams._routes, pending.correlation_id, "synthetic-session")
        result = await teams.review({"correlation_id": pending.correlation_id, "action_identity": pending.identity, "decision": "decline", "responder_object_id": subject}, operator)
        assert "Declined" in str(result)
        assert RECORD_ID in state["records"]
        session.complete.assert_not_called()

    asyncio.run(run())


@pytest.mark.parametrize("failure", ["identity", "role", "expired", "caller_expired", "responder"])
def test_workflow_invalid_review_cannot_execute(monkeypatch, tmp_path, failure):
    from chainlit import session as chainlit_session
    from src.aut_002 import teams
    from src.aut_002.auth import Operator

    state, session = configure(monkeypatch, tmp_path, "DemoUser")
    operator, subject = workflow_operator(monkeypatch)
    if failure == "role":
        operator = Operator(operator.reference, frozenset({"DemoUser"}), time.time())
    if failure == "caller_expired":
        operator = Operator(operator.reference, operator.roles, time.time() - 301)
    monkeypatch.setattr(chainlit_session.WebsocketSession, "get_by_id", lambda _: object())
    monkeypatch.setattr(importlib.import_module("chainlit.context"), "init_ws_context", lambda _: None)

    async def run():
        await cloud_chat._attempt("delete")
        pending = state["pending"]
        monkeypatch.setitem(teams._routes, pending.correlation_id, "synthetic-session")
        if failure == "expired":
            pending.created_at -= 301
        data = {"correlation_id": pending.correlation_id, "action_identity": "wrong" if failure == "identity" else pending.identity, "decision": "approve", "responder_object_id": "55555555-5555-5555-5555-555555555555" if failure == "responder" else subject}
        card = await teams.review(data, operator)
        assert "executed and verified" not in str(card)
        assert RECORD_ID in state["records"]
        assert not list(tmp_path.glob("*-allow.json"))
        session.complete.assert_not_called()

    asyncio.run(run())