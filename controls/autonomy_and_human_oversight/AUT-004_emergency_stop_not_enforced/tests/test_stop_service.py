"""AUT-004 decisions through the real ACS runtime, with fake switch reads (no cloud)."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from azure.core.exceptions import HttpResponseError, ResourceNotFoundError

from src.aut_004.agent import ScriptedSession
from src.aut_004.auth import operator_reference
from src.aut_004.policy import get_control
from src.aut_004.service import Scope, StopService
from src.aut_004.stop_state import StopState, attempt_to_lift_stop, read_stop_state
from src.aut_004.tools import SyntheticLedger

FLAG = "aut004-support-refunds-issue-refund"
SCOPE = Scope("issue_refund", FLAG, "a" * 64)


def _setting(value, *, modified=None):
    return SimpleNamespace(value=value, etag="etag-1", last_modified=modified or datetime.now(UTC))


class FakeClient:
    def __init__(self, outcome):
        self.outcome = outcome

    def get_configuration_setting(self, key):
        assert key == ".appconfig.featureflag/" + FLAG
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def _http(status):
    error = HttpResponseError(message="synthetic")
    error.status_code = status
    return error


@pytest.mark.parametrize(
    ("outcome", "status"),
    [
        (_setting(json.dumps({"id": FLAG, "enabled": True})), "enabled"),
        (_setting(json.dumps({"id": FLAG, "enabled": False})), "disabled"),
        (ResourceNotFoundError("gone"), "missing"),
        (_setting(""), "invalid"),
        (_setting("{not json"), "invalid"),
        (_setting(json.dumps({"id": "other-flag", "enabled": True})), "invalid"),
        (_setting(json.dumps({"id": FLAG, "enabled": "true"})), "invalid"),
        (_http(429), "throttled"),
        (_http(503), "unavailable"),
        (TimeoutError("slow"), "unavailable"),
    ],
    ids=["enabled", "disabled", "missing", "empty", "malformed", "wrong-id", "string-bool", "throttled", "outage", "timeout"],
)
def test_switch_read_outcomes(outcome, status):
    assert read_stop_state(FakeClient(outcome), FLAG).status == status


class Switch:
    def __init__(self, status="enabled"):
        self.status = status
        self.modified = datetime.now(UTC).isoformat()

    def flip(self, status):
        self.status = status
        self.modified = datetime.now(UTC).isoformat()

    def read(self):
        return StopState(self.status, FLAG, "etag", self.modified, datetime.now(UTC).isoformat())


def _service(switch, slow=0.0, scope=SCOPE):
    return StopService(get_control(), scope, switch.read, ledger=SyntheticLedger(slow_seconds=slow))


REFUND_ROUNDS = [[("lookup_order", {"order_id": "ORD-1001"})], [("issue_refund", {"order_id": "ORD-1001"})],
                 [("reply_to_ticket", {"ticket_id": "TCK-4001", "summary": "done"})]]


async def _noop(_line):
    return None


def _request(service, rounds=REFUND_ROUNDS):
    return asyncio.run(service.handle_request(ScriptedSession(rounds), "refund please", _noop))


def test_refund_runs_while_switch_is_enabled():
    service = _service(Switch("enabled"))
    _request(service)
    refund = [d for d in service.decisions if d["tool_name"] == "issue_refund"][0]
    assert (refund["decision"], refund["reason"], refund["executed"]) == ("allow", "aut_004_switch_enabled", True)
    assert service.ledger.committed_at("ORD-1001")


@pytest.mark.parametrize("status", ["disabled", "missing", "invalid", "throttled", "unavailable"])
def test_refund_is_denied_unless_switch_reads_enabled_and_lookups_continue(status):
    service = _service(Switch(status))
    _request(service)
    by_tool = {d["tool_name"]: d for d in service.decisions}
    assert by_tool["issue_refund"]["decision"] == "deny"
    assert by_tool["issue_refund"]["executed"] is False
    assert service.ledger.committed_at("ORD-1001") is None
    assert by_tool["lookup_order"]["reason"] == "aut_004_outside_stop_scope"
    assert by_tool["reply_to_ticket"]["decision"] == "allow"


def test_missing_scope_denies_at_startup():
    service = _service(Switch(), scope=Scope("issue_refund", "", "a" * 64))
    assert asyncio.run(service.startup()) == {"decision": "deny", "reason": "aut_004_scope_missing"}


def test_stop_pressed_while_a_refund_is_in_flight():
    switch = Switch("enabled")
    service = _service(switch, slow=0.3)

    async def scenario():
        slow = asyncio.create_task(service.handle_request(
            ScriptedSession([[("issue_refund", {"order_id": "ORD-1006"})]]), "slow refund", _noop))
        await asyncio.sleep(0.1)
        switch.flip("disabled")
        await service.handle_request(ScriptedSession([[("issue_refund", {"order_id": "ORD-1001"})]]), "next", _noop)
        await slow

    asyncio.run(scenario())
    report = service.in_flight_report(switch.read())
    by_order = {r["order_id"]: r for r in report["refunds"]}
    assert by_order["ORD-1006"]["decision"] == "allow"
    assert by_order["ORD-1006"]["outcome"] == "completed"
    assert by_order["ORD-1006"]["in_flight_at_stop"] is True
    assert by_order["ORD-1001"]["decision"] == "deny"
    assert report["stop_requested_at"] == switch.modified


def test_refund_completed_before_the_stop_is_not_in_flight():
    switch = Switch("enabled")
    service = _service(switch)
    _request(service)
    switch.flip("disabled")
    [refund] = service.in_flight_report(switch.read())["refunds"]
    assert refund["outcome"] == "completed" and refund["in_flight_at_stop"] is False


def test_probe_verifies_only_an_observed_stop():
    assert asyncio.run(_service(Switch("disabled")).probe())["stop_verified"] is True
    outage = asyncio.run(_service(Switch("unavailable")).probe())
    assert outage["stop_verified"] is False and outage["probe_decision"] == "deny"
    enabled = asyncio.run(_service(Switch("enabled")).probe())
    assert enabled["stop_verified"] is False and "enabled" in enabled["note"]


def test_probe_never_commits_a_refund_even_when_enabled():
    service = _service(Switch("enabled"))
    asyncio.run(service.probe())
    assert service.ledger.refunds == {}


def test_runtime_identity_cannot_lift_the_stop():
    class ReadOnly:
        def set_configuration_setting(self, _setting):
            raise _http(403)

    assert attempt_to_lift_stop(ReadOnly(), FLAG) == {"lifted": False, "http_status": 403}


def test_operator_reference_requires_role_and_tenant():
    import base64

    def headers(roles, tenant="t-1"):
        claims = [{"typ": "tid", "val": tenant}, {"typ": "oid", "val": "00000000-0000-0000-0000-000000000001"}]
        claims += [{"typ": "roles", "val": role} for role in roles]
        principal = {"auth_typ": "aad", "role_typ": "roles", "claims": claims}
        return {"X-MS-CLIENT-PRINCIPAL": base64.b64encode(json.dumps(principal).encode()).decode()}

    secret = "s" * 40
    assert operator_reference(headers(["SupportOperator"]), tenant="t-1", secret=secret)
    assert operator_reference(headers([]), tenant="t-1", secret=secret) is None
    assert operator_reference(headers(["SupportOperator"], tenant="t-2"), tenant="t-1", secret=secret) is None


def test_unknown_protected_tool_fails_closed_instead_of_skipping_the_switch():
    service = _service(Switch("disabled"), scope=Scope("issue_refunds", FLAG, "a" * 64))
    assert asyncio.run(service.startup()) == {"decision": "deny", "reason": "aut_004_protected_tool_unknown"}
    _request(service)
    refund = [d for d in service.decisions if d["tool_name"] == "issue_refund"][0]
    assert refund["decision"] == "deny" and service.ledger.committed_at("ORD-1001") is None


def test_report_taken_while_an_admitted_refund_is_still_running_lists_it_as_unknown():
    switch = Switch("enabled")
    service = _service(switch, slow=0.3)

    async def scenario():
        slow = asyncio.create_task(service.handle_request(
            ScriptedSession([[("issue_refund", {"order_id": "ORD-1006"})]]), "slow refund", _noop))
        await asyncio.sleep(0.1)
        switch.flip("disabled")
        report = service.in_flight_report(switch.read())
        await slow
        return report

    [refund] = asyncio.run(scenario())["refunds"]
    assert (refund["order_id"], refund["outcome"], refund["in_flight_at_stop"]) == ("ORD-1006", "unknown", True)
