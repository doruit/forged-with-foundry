"""Unit tests for the PRI-001 ACS enforcement boundary (no live Foundry call)."""

import asyncio

from src.pri_001.acs_gate import PiiPolicyDispatcher, enforce_boundary
from src.pri_001.models import PolicyAction, PolicyDecision


def _decision(action: PolicyAction, **overrides) -> PolicyDecision:
    defaults = dict(
        control_id="PRI-001",
        action=action,
        pii_count=0,
        categories=(),
        escalate=False,
        reason="test",
    )
    defaults.update(overrides)
    return PolicyDecision(**defaults)


def test_policy_dispatcher_maps_allow_to_acs_allow() -> None:
    dispatcher = PiiPolicyDispatcher()

    verdict = dispatcher.evaluate(
        {"input": {"policy_target": {"value": {"action": "allow", "pii_count": 0, "categories": []}}}}
    )

    assert verdict["decision"] == "allow"


def test_policy_dispatcher_maps_redact_and_escalate_to_acs_warn() -> None:
    dispatcher = PiiPolicyDispatcher()

    verdict = dispatcher.evaluate(
        {
            "input": {
                "policy_target": {
                    "value": {
                        "action": "redact_and_escalate",
                        "pii_count": 1,
                        "categories": ["Email"],
                    }
                }
            }
        }
    )

    assert verdict["decision"] == "warn"
    assert "Email" in verdict["message"]


def test_policy_dispatcher_maps_block_to_acs_deny() -> None:
    dispatcher = PiiPolicyDispatcher()

    verdict = dispatcher.evaluate(
        {"input": {"policy_target": {"value": {"action": "block", "pii_count": 0, "categories": []}}}}
    )

    assert verdict["decision"] == "deny"


def test_enforce_boundary_allows_allow_decision() -> None:
    result = asyncio.run(enforce_boundary(_decision(PolicyAction.ALLOW), "chat_input"))

    assert result.action is PolicyAction.ALLOW


def test_enforce_boundary_passes_redact_and_escalate_through() -> None:
    decision = _decision(
        PolicyAction.REDACT_AND_ESCALATE, pii_count=1, categories=("Email",), escalate=True
    )

    result = asyncio.run(enforce_boundary(decision, "agent_output"))

    assert result.action is PolicyAction.REDACT_AND_ESCALATE
    assert result.escalate is True


def test_enforce_boundary_fails_closed_on_block() -> None:
    result = asyncio.run(enforce_boundary(_decision(PolicyAction.BLOCK), "native_document"))

    assert result.action is PolicyAction.BLOCK
    assert "Agent Control Specification" in result.reason
