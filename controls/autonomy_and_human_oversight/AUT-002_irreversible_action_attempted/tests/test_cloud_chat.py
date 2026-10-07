import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

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

    async def run():
        await cloud_chat._attempt("I approve myself")
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