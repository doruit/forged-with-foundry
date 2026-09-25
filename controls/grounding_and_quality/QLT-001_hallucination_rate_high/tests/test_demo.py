"""Prove notification failures cannot change decisions or cause blind resends."""

import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest

CONTROL = Path(__file__).resolve().parents[1]
_ISOLATED_MODULES = ("agent", "demo", "evaluator", "workload")
for _name in _ISOLATED_MODULES:
    sys.modules.pop(_name, None)
sys.path.insert(0, str(CONTROL))
from demo import card, notify, save  # noqa: E402
import demo  # noqa: E402
sys.path.remove(str(CONTROL))
for _name in _ISOLATED_MODULES:
    sys.modules.pop(_name, None)

PLATFORM_ID = "it-helpdesk-kb-assistant-platform"
REGIONAL_ID = "it-helpdesk-kb-assistant-regional"
CONTRACTOR_ID = "it-helpdesk-kb-assistant-contractor"


class _FakeRuleAction:
    def __init__(self, eval_id):
        self.eval_id = eval_id


class _FakeRule:
    def __init__(self, eval_id):
        self.action = _FakeRuleAction(eval_id)


class _FakeDataSource:
    def __init__(self, content):
        # ``item_generation_params`` is a plain dict in the real SDK
        # response (confirmed live 2026-09-25), not an attribute-accessible
        # model -- unlike ``data_source`` itself.
        self.item_generation_params = {"source": {"content": content}}


class _FakeRun:
    def __init__(self, run_id, content, created_at=1790000000):
        self.id = run_id
        self.data_source = _FakeDataSource(content)
        self.created_at = created_at


class _FakeOutputItem:
    def __init__(self, item_id, results):
        self._dumped = {"id": item_id, "results": results}

    def model_dump(self):
        return self._dumped


class _FakeOutputItems:
    def __init__(self, items_by_run):
        self._items_by_run = items_by_run

    def list(self, *, eval_id, run_id):
        return self._items_by_run.get(run_id, [])


class _FakeEvalsRuns:
    def __init__(self, runs_by_eval, items_by_run):
        self._runs_by_eval = runs_by_eval
        self.output_items = _FakeOutputItems(items_by_run)

    def list(self, *, eval_id):
        return self._runs_by_eval.get(eval_id, [])


class _FakeOpenAIClient:
    def __init__(self, runs_by_eval, items_by_run):
        self.evals = type("Evals", (), {"runs": _FakeEvalsRuns(runs_by_eval, items_by_run)})()


class _FakeProjectClient:
    def __init__(self, rules, runs_by_eval=None, items_by_run=None):
        self._rules = rules
        self._openai_client = _FakeOpenAIClient(runs_by_eval or {}, items_by_run or {})
        self.evaluation_rules = type("Rules", (), {"get": staticmethod(lambda rule_id: rules[rule_id])})()

    def get_openai_client(self):
        return self._openai_client


ALL_AGENT_IDS = (PLATFORM_ID, REGIONAL_ID, CONTRACTOR_ID)


def test_given_no_recorded_requests_for_an_agent_when_fetching_then_fails_closed():
    client = _FakeProjectClient(rules={})

    fleet_results, complete = demo.fetch_fleet_results(client, manifest={"requests": {}})

    assert fleet_results == {}
    assert complete is False


def test_given_a_rule_lookup_error_when_fetching_then_fails_closed():
    client = _FakeProjectClient(rules={})  # no rules registered -> KeyError inside fetch

    fleet_results, complete = demo.fetch_fleet_results(
        client, manifest={"requests": {agent_id: [{"response_id": "resp_1"}] for agent_id in ALL_AGENT_IDS}})

    assert fleet_results == {}
    assert complete is False


def test_given_the_real_two_response_per_turn_shape_when_fetching_then_the_tool_call_only_run_is_filtered_out():
    """Pin the real, live-confirmed shape (2026-09-25, see
    the current live-observed integration): each real tool-calling
    conversation produces two ``responseCompleted`` events, and Continuous
    Evaluation scores both -- the first (tool-call-only, no final answer
    yet) always has `groundedness: None`. A run matching this window's
    recorded response id but carrying only that unscored shape must not be
    treated as a real result.
    """
    rules = {f"{agent_id}-rule": _FakeRule(f"eval-{agent_id}") for agent_id in ALL_AGENT_IDS}
    runs_by_eval = {
        f"eval-{PLATFORM_ID}": [_FakeRun("run-1", content=["resp_final"])],
    }
    items_by_run = {
        "run-1": [_FakeOutputItem("1", results=[
            {"name": "groundedness", "passed": None, "score": None, "threshold": None},
            {"name": "retrieval", "passed": False, "score": 2.0, "threshold": 3},
        ])],
    }
    client = _FakeProjectClient(rules, runs_by_eval, items_by_run)
    manifest = {"requests": {PLATFORM_ID: [{"response_id": "resp_final"}]}}

    fleet_results, complete = demo.fetch_fleet_results(client, manifest)

    assert fleet_results == {}
    assert complete is False


def test_given_a_real_scored_final_answer_run_when_fetching_then_returns_it():
    """Pin the real, live-confirmed success shape (2026-09-25): the
    final-answer run, matched by its real recorded response id, carries a
    populated groundedness result with the confirmed real schema
    (name/passed/score/threshold, 1-5 scale) -- exactly what
    `evaluator.measure_agent` already expects.
    """
    rules = {f"{agent_id}-rule": _FakeRule(f"eval-{agent_id}") for agent_id in ALL_AGENT_IDS}
    runs_by_eval, items_by_run, manifest_requests = {}, {}, {}
    for agent_id in ALL_AGENT_IDS:
        run_id = f"run-{agent_id}"
        runs_by_eval[f"eval-{agent_id}"] = [_FakeRun(run_id, content=[f"resp-{agent_id}"])]
        items_by_run[run_id] = [_FakeOutputItem("1", results=[
            {"name": "groundedness", "passed": True, "score": 5.0, "threshold": 3},
        ])]
        manifest_requests[agent_id] = [{"response_id": f"resp-{agent_id}"}]
    client = _FakeProjectClient(rules, runs_by_eval, items_by_run)

    fleet_results, complete = demo.fetch_fleet_results(client, manifest={"requests": manifest_requests})

    assert complete is True
    for agent_id in ALL_AGENT_IDS:
        assert fleet_results[agent_id] == [
            {"run_id": f"run-{agent_id}:1", "passed": True, "score": 5.0, "threshold": 3}]


def test_given_only_part_of_an_agents_window_is_scored_when_fetching_then_fails_closed():
    rules = {f"{agent_id}-rule": _FakeRule(f"eval-{agent_id}") for agent_id in ALL_AGENT_IDS}
    runs_by_eval, items_by_run, manifest_requests = {}, {}, {}
    for agent_id in ALL_AGENT_IDS:
        run_id = f"run-{agent_id}"
        runs_by_eval[f"eval-{agent_id}"] = [_FakeRun(run_id, content=[f"resp-{agent_id}-1"])]
        items_by_run[run_id] = [_FakeOutputItem("1", results=[
            {"name": "groundedness", "passed": True, "score": 5.0, "threshold": 3},
        ])]
        manifest_requests[agent_id] = [
            {"response_id": f"resp-{agent_id}-1"},
            {"response_id": f"resp-{agent_id}-2"},
        ]
    client = _FakeProjectClient(rules, runs_by_eval, items_by_run)

    fleet_results, complete = demo.fetch_fleet_results(
        client, manifest={"requests": manifest_requests})

    assert fleet_results == {}
    assert complete is False


def _agent_measurement(agent_id, *, total, ungrounded, critical_run_ids, average_score):
    return {"agent_id": agent_id, "total": total, "ungrounded": ungrounded,
            "ungrounded_run_ids": ["run-2"] if ungrounded else [],
            "critical_run_ids": critical_run_ids,
            "rate_percent": (ungrounded / total) * 100, "average_score": average_score}


@pytest.fixture
def evidence(tmp_path):
    path = tmp_path / "evidence.json"
    per_agent = {
        PLATFORM_ID: _agent_measurement(PLATFORM_ID, total=3, ungrounded=0, critical_run_ids=[], average_score=0.95),
        REGIONAL_ID: _agent_measurement(REGIONAL_ID, total=3, ungrounded=0, critical_run_ids=[], average_score=0.85),
        CONTRACTOR_ID: _agent_measurement(CONTRACTOR_ID, total=3, ungrounded=1, critical_run_ids=["run-2"], average_score=0.4),
    }
    save(path, {"decision": "quality_review_required", "correlation_id": "synthetic-window",
                "threshold_percent": 5.0, "window": {"number": 3},
                "fleet": {"per_agent": per_agent, "fleet_average_score": 0.73,
                          "best_agent": {"agent_id": PLATFORM_ID, "average_score": 0.95},
                          "worst_agent": {"agent_id": CONTRACTOR_ID, "average_score": 0.4},
                          "any_agent_breach": True},
                "notification": {"status": "not_requested", "delivery_verified": False}})
    return path


@pytest.mark.parametrize("status,expected", [(202, "accepted"), (400, "rejected"), (500, "rejected")])
def test_given_http_response_when_notified_then_decision_unchanged_and_delivery_unverified(evidence, status, expected):
    calls = []
    def post(url, **kwargs):
        calls.append(url)
        assert json.loads(evidence.read_text())["notification"]["status"] == "attempted"
        return httpx.Response(status)

    config = {"QLT001_TEAMS_WEBHOOK_URL": "https://test.logic.azure.com/test"}
    result = notify(evidence, config, post=post)
    repeated = notify(evidence, config, post=post)

    assert result["decision"] == "quality_review_required"
    assert result["notification"]["status"] == expected
    assert result["notification"]["delivery_verified"] is False
    assert repeated == result and len(calls) == 1


def test_given_timeout_when_notified_then_unknown_and_no_retry(evidence):
    calls = []
    def post(url, **kwargs):
        calls.append(url)
        raise httpx.ReadTimeout("private endpoint details")

    config = {"QLT001_TEAMS_WEBHOOK_URL": "https://test.logic.azure.com/test"}
    notify(evidence, config, post=post)
    result = notify(evidence, config, post=post)

    assert result["notification"]["status"] == "delivery_unknown"
    assert len(calls) == 1 and "private endpoint" not in evidence.read_text()


def test_given_crashed_attempt_when_restarted_then_not_resent(evidence):
    record = json.loads(evidence.read_text())
    record["notification"]["status"] = "attempted"
    save(evidence, record)

    assert notify(evidence, {}) == record


def test_given_checked_receipt_when_recorded_then_verification_method_is_explicit(evidence):
    record = json.loads(evidence.read_text())
    record["notification"].update(status="accepted", http_status=202)
    save(evidence, record)

    result = demo.record_delivery(evidence, "synthetic-window", "run123", "123456")

    assert result["notification"]["delivery_verified"] is True
    assert result["notification"]["verification_method"].startswith("operator_checked_")


def test_given_unaccepted_attempt_when_receipt_recorded_then_rejected(evidence):
    with pytest.raises(ValueError, match="accepted notification"):
        demo.record_delivery(evidence, "synthetic-window", "run123", "123456")


def test_given_cannot_evaluate_when_notified_then_governance_operations_is_notified(evidence):
    record = json.loads(evidence.read_text())
    record["decision"] = "cannot_evaluate"
    record["reason"] = "evaluation_retrieval_unavailable_or_partial"
    save(evidence, record)

    calls = []
    def post(url, **kwargs):
        calls.append(url)
        return httpx.Response(202)

    result = notify(evidence, {
        "QLT001_GOVERNANCE_TEAMS_WEBHOOK_URL": "https://test.logic.azure.com/governance",
    }, post=post)

    assert result["notification"]["status"] == "accepted"
    assert result["notification"]["recipient_role"] == "AI Governance Operations"
    assert len(calls) == 1
    assert "measurement unavailable" in json.dumps(card(result))


def test_given_quality_review_card_then_red_attention_signal_is_visible(evidence):
    payload = card(json.loads(evidence.read_text()))
    content = payload["attachments"][0]["content"]
    status = content["body"][0]
    icon = status["items"][0]["columns"][0]["items"][0]
    status_text = json.dumps(status, ensure_ascii=False)

    assert status["style"] == "attention"
    assert icon["text"] == "●"
    assert icon["color"] == "attention"
    assert "quality review required" in status_text.lower()


def test_given_healthy_card_then_green_positive_signal_is_visible(evidence):
    record = json.loads(evidence.read_text())
    healthy_per_agent = {
        PLATFORM_ID: _agent_measurement(PLATFORM_ID, total=3, ungrounded=0, critical_run_ids=[], average_score=0.95),
        REGIONAL_ID: _agent_measurement(REGIONAL_ID, total=3, ungrounded=0, critical_run_ids=[], average_score=0.9),
        CONTRACTOR_ID: _agent_measurement(CONTRACTOR_ID, total=3, ungrounded=0, critical_run_ids=[], average_score=0.85),
    }
    record.update(decision="no_review_required", window={"number": 1},
                  fleet={"per_agent": healthy_per_agent, "fleet_average_score": 0.9,
                         "best_agent": {"agent_id": PLATFORM_ID, "average_score": 0.95},
                         "worst_agent": {"agent_id": CONTRACTOR_ID, "average_score": 0.85},
                         "any_agent_breach": False})
    payload = card(record)
    status = payload["attachments"][0]["content"]["body"][0]
    icon = status["items"][0]["columns"][0]["items"][0]
    status_text = json.dumps(status, ensure_ascii=False)

    assert status["style"] == "good"
    assert icon["color"] == "good"
    assert "no groundedness threshold breach" in status_text.lower()


def test_given_extra_sensitive_fields_when_card_built_then_not_exported(evidence):
    record = json.loads(evidence.read_text())
    record.update(prompt="private prompt", token="private token", kb_article="private kb content")

    assert "private" not in json.dumps(card(record))


def test_given_teams_auth_when_sending_then_audience_retains_trailing_slash(evidence, monkeypatch):
    credential = MagicMock()
    credential.get_token.return_value.token = "synthetic-token"
    credential_context = MagicMock()
    credential_context.__enter__.return_value = credential
    client_context = MagicMock()
    client_context.__enter__.return_value.post.return_value = httpx.Response(202)
    monkeypatch.setattr(demo, "AzureCliCredential", lambda **kwargs: credential_context)
    monkeypatch.setattr(demo.httpx, "Client", lambda **kwargs: client_context)

    notify(evidence, {"QLT001_TEAMS_WEBHOOK_URL": "https://test.logic.azure.com/test",
                      "AZURE_TENANT_ID": "synthetic-tenant"})

    credential.get_token.assert_called_once_with("https://service.flow.microsoft.com//.default")


@pytest.mark.parametrize("status,http_status,expected_calls", [
    ("rejected", 403, 1), ("rejected", 401, 1), ("rejected", 500, 0),
    ("delivery_unknown", None, 0), ("accepted", 202, 0), ("attempted", None, 0),
])
def test_given_explicit_recovery_when_retried_then_only_auth_rejection_is_retryable(
        evidence, status, http_status, expected_calls):
    record = json.loads(evidence.read_text())
    record["notification"].update(status=status, http_status=http_status)
    save(evidence, record)
    post = MagicMock(return_value=httpx.Response(202))

    result = notify(evidence, {"QLT001_TEAMS_WEBHOOK_URL": "https://test.logic.azure.com/test"},
                    post=post, retry_rejected=True)

    assert post.call_count == expected_calls
    if expected_calls:
        assert result["notification"]["previous_attempts"][0]["http_status"] == http_status


def test_given_real_scored_runs_across_two_days_when_fetching_agent_history_then_returns_one_event_per_scored_run():
    """``fetch_agent_history`` is not scoped to one window's manifest, unlike
    ``fetch_fleet_results`` -- it reads every real run under the agent's own
    rule, which is exactly what a real, multi-day trend (see
    ``evaluator.daily_trend``) needs.
    """
    day1 = 1790000000  # a fixed, arbitrary real Unix timestamp
    day2 = day1 + 86400
    rules = {f"{PLATFORM_ID}-rule": _FakeRule(f"eval-{PLATFORM_ID}")}
    runs_by_eval = {
        f"eval-{PLATFORM_ID}": [
            _FakeRun("run-1", content=["resp-a"], created_at=day1),
            _FakeRun("run-2", content=["resp-b"], created_at=day2),
        ],
    }
    items_by_run = {
        "run-1": [_FakeOutputItem("1", results=[{"name": "groundedness", "passed": True, "score": 5.0, "threshold": 3}])],
        "run-2": [_FakeOutputItem("1", results=[{"name": "groundedness", "passed": False, "score": 2.0, "threshold": 3}])],
    }
    client = _FakeProjectClient(rules, runs_by_eval, items_by_run)

    events = demo.fetch_agent_history(client, PLATFORM_ID)

    assert {e["score"] for e in events} == {5.0, 2.0}
    assert len({e["day"] for e in events}) == 2


class _FakeResponses:
    def __init__(self, first, final=None):
        self._responses = [first] if final is None else [first, final]
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


def _response(response_id, *output):
    return SimpleNamespace(id=response_id, output=list(output))


def _tool_call(arguments, *, name="lookup_it_kb"):
    return SimpleNamespace(
        type="function_call", name=name, arguments=json.dumps(arguments), call_id="call-1")


def _message(payload):
    return SimpleNamespace(
        type="message",
        content=[SimpleNamespace(type="output_text", text=json.dumps(payload))],
    )


def test_given_no_tool_call_when_invoking_then_fails_closed(monkeypatch):
    monkeypatch.setitem(sys.modules, "workload", SimpleNamespace(lookup=MagicMock()))
    client = SimpleNamespace(responses=_FakeResponses(_response("resp-1", _message({}))))

    with pytest.raises(RuntimeError, match="exactly_once"):
        demo.invoke(client, SimpleNamespace(agent_id=PLATFORM_ID), "vpn_setup", 1, "model")


def test_given_changed_tool_arguments_when_invoking_then_fails_closed(monkeypatch):
    lookup = MagicMock(return_value="article")
    monkeypatch.setitem(sys.modules, "workload", SimpleNamespace(lookup=lookup))
    first = _response("resp-1", _tool_call({"topic": "password_reset", "window": 1}))
    client = SimpleNamespace(responses=_FakeResponses(first))

    with pytest.raises(RuntimeError, match="do_not_match"):
        demo.invoke(client, SimpleNamespace(agent_id=PLATFORM_ID), "vpn_setup", 1, "model")

    lookup.assert_not_called()


def test_given_exact_tool_call_when_invoking_then_executes_and_returns_structured_answer(monkeypatch):
    lookup = MagicMock(return_value="current article")
    monkeypatch.setitem(sys.modules, "workload", SimpleNamespace(lookup=lookup))
    first = _response("resp-1", _tool_call({"topic": "vpn_setup", "window": 1}))
    final = _response("resp-2", _message({
        "answer": "Use the current article.",
        "self_reported_confidence": 5,
        "suggested_followups": [],
    }))
    responses = _FakeResponses(first, final)
    client = SimpleNamespace(responses=responses)

    result = demo.invoke(
        client, SimpleNamespace(agent_id=PLATFORM_ID), "vpn_setup", 1, "model")

    assert result["response_id"] == "resp-2"
    assert result["first_response_id"] == "resp-1"
    assert result["answer"] == "Use the current article."
    lookup.assert_called_once()
    assert responses.calls[1]["input"][0]["call_id"] == "call-1"


class _SetupRuleOperations:
    def __init__(self, rules, missing=()):
        self.rules = rules
        self.missing = set(missing)
        self.updates = []

    def get(self, rule_id):
        if rule_id in self.missing:
            response = SimpleNamespace(
                status_code=404, reason="Not Found", headers={}, request=None)
            raise demo.HttpResponseError("not found", response=response)
        return self.rules[rule_id]

    def create_or_update(self, rule_id, rule):
        self.updates.append((rule_id, rule))
        return rule


def _setup_client(rule_operations):
    evals = SimpleNamespace(create=MagicMock())
    return SimpleNamespace(
        evaluation_rules=rule_operations,
        get_openai_client=lambda: SimpleNamespace(evals=evals),
        _evals=evals,
    )


def test_given_first_rule_missing_but_other_rules_exist_when_setup_then_reuses_history(monkeypatch):
    profiles = tuple(
        SimpleNamespace(agent_id=agent_id, display_name=agent_id)
        for agent_id in ALL_AGENT_IDS)
    operations = _SetupRuleOperations(
        {
            f"{REGIONAL_ID}-rule": _FakeRule("eval-shared"),
            f"{CONTRACTOR_ID}-rule": _FakeRule("eval-shared"),
        },
        missing={f"{PLATFORM_ID}-rule"},
    )
    client = _setup_client(operations)
    register = MagicMock()
    monkeypatch.setattr(demo, "FLEET", profiles)
    monkeypatch.setattr(demo.agent, "register_agent", register)

    eval_id = demo.setup_fleet(client, "model")

    assert eval_id == "eval-shared"
    client._evals.create.assert_not_called()
    assert register.call_count == 3
    assert len(operations.updates) == 3


def test_given_conflicting_rule_eval_ids_when_setup_then_fails_closed(monkeypatch):
    profiles = tuple(
        SimpleNamespace(agent_id=agent_id, display_name=agent_id)
        for agent_id in ALL_AGENT_IDS)
    operations = _SetupRuleOperations({
        f"{PLATFORM_ID}-rule": _FakeRule("eval-a"),
        f"{REGIONAL_ID}-rule": _FakeRule("eval-b"),
        f"{CONTRACTOR_ID}-rule": _FakeRule("eval-a"),
    })
    client = _setup_client(operations)
    register = MagicMock()
    monkeypatch.setattr(demo, "FLEET", profiles)
    monkeypatch.setattr(demo.agent, "register_agent", register)

    with pytest.raises(RuntimeError, match="conflicting Eval ids"):
        demo.setup_fleet(client, "model")

    register.assert_not_called()
    assert operations.updates == []
