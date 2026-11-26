import subprocess

from src.qlt_006 import __main__ as cli
from src.qlt_006.contract import Declaration
from src.qlt_006.policy import Decision

DECLARATION = Declaration("valid", "s" * 64, None, 5.0, 12, "contoso/demo")


def test_failed_issue_creation_is_reported_and_exits_2(monkeypatch, tmp_path) -> None:
    def broken(*_args, **_kwargs):
        raise subprocess.CalledProcessError(1, "gh")
    monkeypatch.setattr("src.qlt_006.route.open_issue", broken)
    monkeypatch.setattr(cli, "write", lambda record: tmp_path / "evidence.json")
    code = cli.finish({"agent": "a"}, Decision("change_cycle_required", "qlt_006_regression_above_threshold"), DECLARATION, route=True)
    assert code == 2


def test_within_tolerance_opens_nothing(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("src.qlt_006.route.open_issue", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no issue")))
    monkeypatch.setattr(cli, "write", lambda record: tmp_path / "evidence.json")
    assert cli.finish({"agent": "a"}, Decision("within_tolerance", "qlt_006_within_tolerance"), DECLARATION, route=True) == 0


def test_measurement_failure_is_routed_too(monkeypatch, tmp_path) -> None:
    seen = {}
    monkeypatch.setattr("src.qlt_006.route.open_issue", lambda repo, record: seen.update(decision=record["decision"]) or {"verified": True})
    monkeypatch.setattr(cli, "write", lambda record: tmp_path / "evidence.json")
    assert cli.finish({"agent": "a"}, Decision("measurement_failed", "qlt_006_baseline_unavailable"), DECLARATION, route=True) == 1
    assert seen["decision"] == "measurement_failed"
