"""The budget-extension approval channel: bound to one request, expiring, single-use."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from src.tool_003.approval import (
    DECISION_SUFFIX,
    FileApprovalChannel,
    build_request,
    decide,
    request_digest,
)

T0 = datetime(2026, 11, 15, 9, 0, tzinfo=UTC)


def _request(ttl=300):
    return build_request(
        run_id="run-1", task_type="single_refund", tool_name="lookup_order", action_identity="acs-id",
        admitted_calls=4, approved_budget=4, extra_calls=3, ttl_seconds=ttl, contract_sha256="a" * 64, now=T0,
    )


class Clock:
    def __init__(self, start=T0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += timedelta(seconds=seconds)


def _channel(tmp_path, clock, on_wait=None):
    def sleep(seconds):
        if on_wait:
            on_wait()
        clock.advance(seconds)

    return FileApprovalChannel(tmp_path, emit=lambda _line: None, poll_seconds=10, sleep=sleep, clock=clock)


def test_matching_decision_before_expiry_approves(tmp_path):
    clock, request = Clock(), _request()
    channel = _channel(tmp_path, clock, on_wait=lambda: (tmp_path / f"{request['request_id']}{DECISION_SUFFIX}").exists()
                       or decide(tmp_path, request["request_id"], approve=True, approver_ref="approver-x", now=clock.now))
    decision = channel(request)
    assert (decision["status"], decision["approved"], decision["approver_ref"]) == ("approved", True, "approver-x")


def test_no_decision_before_expiry_is_not_an_approval(tmp_path):
    decision = _channel(tmp_path, Clock())(_request(ttl=60))
    assert (decision["status"], decision["approved"]) == ("expired", False)


def test_decline_is_recorded_as_declined(tmp_path):
    clock, request = Clock(), _request()
    channel = _channel(tmp_path, clock, on_wait=lambda: (tmp_path / f"{request['request_id']}{DECISION_SUFFIX}").exists()
                       or decide(tmp_path, request["request_id"], approve=False, approver_ref="approver-x", now=clock.now))
    assert channel(request)["status"] == "declined"


@pytest.mark.parametrize("tamper", ["request_sha256", "request_id", "decision"])
def test_a_decision_that_does_not_match_the_exact_request_is_invalid(tmp_path, tamper):
    clock, request = Clock(), _request()

    def forge():
        path = tmp_path / f"{request['request_id']}{DECISION_SUFFIX}"
        if path.exists():
            return
        forged = {"request_id": request["request_id"], "request_sha256": request_digest(request),
                  "decision": "approve", "approver_ref": "approver-x", "decided_at": clock.now.isoformat()}
        forged[tamper] = "tampered"
        path.write_text(json.dumps(forged))

    assert _channel(tmp_path, clock, on_wait=forge)(request)["status"] == "invalid"


def test_decision_after_expiry_is_refused_and_a_request_takes_one_decision_only(tmp_path):
    clock, request = Clock(), _request()
    (tmp_path / f"{request['request_id']}.request.json").write_text(json.dumps(request))
    with pytest.raises(ValueError):
        decide(tmp_path, request["request_id"], approve=True, approver_ref="a", now=T0 + timedelta(seconds=300))
    decide(tmp_path, request["request_id"], approve=False, approver_ref="a", now=T0)
    with pytest.raises(FileExistsError):
        decide(tmp_path, request["request_id"], approve=True, approver_ref="a", now=T0)


def test_unknown_request_cannot_be_approved(tmp_path):
    with pytest.raises(FileNotFoundError):
        decide(tmp_path, "no-such-request", approve=True, approver_ref="a", now=T0)


def test_a_partly_written_decision_is_not_consumed(tmp_path):
    clock, request = Clock(), _request()
    path = tmp_path / f"{request['request_id']}{DECISION_SUFFIX}"
    calls = []

    def write_in_two_steps():
        calls.append(1)
        if len(calls) == 1:
            path.write_text('{"request_id": ')  # a writer caught mid-write
        elif len(calls) == 2:
            path.unlink()
            decide(tmp_path, request["request_id"], approve=True, approver_ref="approver-x", now=clock.now)

    assert _channel(tmp_path, clock, on_wait=write_in_two_steps)(request)["status"] == "approved"


def test_approver_reference_is_keyed_and_refuses_a_missing_key(monkeypatch):
    import subprocess

    from src.tool_003 import approval

    outputs = iter(["11111111-1111-1111-1111-111111111111\n", "tenant-1\n"] * 2)
    monkeypatch.setattr(approval.subprocess, "run",
                        lambda *a, **k: subprocess.CompletedProcess(a, 0, next(outputs), ""))
    first = approval.approver_reference("k" * 32)
    second = approval.approver_reference("z" * 32)
    assert first != second and "1111" not in first
    with pytest.raises(RuntimeError):
        approval.approver_reference("short")


def test_a_request_answered_and_consumed_by_the_run_cannot_be_answered_again(tmp_path):
    clock, request = Clock(), _request()
    channel = _channel(tmp_path, clock, on_wait=lambda: (tmp_path / f"{request['request_id']}{DECISION_SUFFIX}").exists()
                       or decide(tmp_path, request["request_id"], approve=True, approver_ref="approver-x", now=clock.now))
    assert channel(request)["status"] == "approved"
    with pytest.raises(FileExistsError):
        decide(tmp_path, request["request_id"], approve=True, approver_ref="approver-x", now=clock.now)
