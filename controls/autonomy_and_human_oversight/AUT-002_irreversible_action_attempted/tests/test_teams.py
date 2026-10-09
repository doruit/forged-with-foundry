import asyncio
from types import SimpleNamespace

import pytest

from src.aut_002.teams import approval_card, result_card, review, validate_workflow_url


def pending_action():
    return SimpleNamespace(
        created_at=0, actor_roles=("DemoUser",), actor_reference="synthetic-actor-reference",
        identity="sha256:" + "a" * 64, correlation_id="synthetic-correlation",
        request=SimpleNamespace(tool_name="permanently_delete_demo_record"),
    )


def test_card_uses_workflow_submit_actions_without_identity_claims():
    card = approval_card(pending_action())
    assert [action["data"]["decision"] for action in card["actions"]] == ["approve", "decline"]
    assert all(action["type"] == "Action.Submit" for action in card["actions"])
    assert all(set(action["data"]) == {"decision"} for action in card["actions"])
    assert "1970-01-01T00:05:00+00:00" in str(card)
    assert pending_action().actor_reference not in str(card)


@pytest.mark.parametrize("status", ["verified", "declined", "expired", "denied", "unresolved", "unavailable"])
def test_result_cards_have_no_reusable_approval_buttons(status):
    assert "actions" not in result_card(status, identity="synthetic-action")


def test_unknown_result_is_not_treated_as_success():
    with pytest.raises(KeyError):
        result_card("approved")


@pytest.mark.parametrize("payload", [None, {}, {"roles": ["OpsManager"]}])
def test_untrusted_callback_cannot_grant_roles(payload):
    assert asyncio.run(review(payload, None))["status"] == "denied"


def test_unauthenticated_endpoint_cannot_execute():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from src.aut_002.teams import install

    app = FastAPI()
    install(app)
    with TestClient(app) as client:
        response = client.post("/api/teams/review", json={"decision": "approve", "roles": ["OpsManager"]})
    assert response.status_code == 200
    assert response.json()["status"] == "denied"


@pytest.mark.parametrize("url", ["http://example.logic.azure.com/test", "https://attacker.example/test", "https://user:password@example.logic.azure.com/test"])
def test_workflow_endpoint_is_restricted(url):
    with pytest.raises(ValueError):
        validate_workflow_url(url)


def test_workflow_endpoint_accepts_supported_hosts():
    assert validate_workflow_url("https://example.logic.azure.com/test") == "https://example.logic.azure.com/test"


def test_card_expiry_uses_the_authoritative_mandate_ttl(monkeypatch):
    from src.aut_002 import cloud_chat

    monkeypatch.setenv("AUT002_MANDATE_SHA256", "synthetic-hash")
    monkeypatch.setattr(cloud_chat, "load_mandate", lambda: {"actions": [{"toolName": "permanently_delete_demo_record", "approval": {"ttlSeconds": 60}}]})
    assert "1970-01-01T00:01:00+00:00" in str(approval_card(pending_action()))