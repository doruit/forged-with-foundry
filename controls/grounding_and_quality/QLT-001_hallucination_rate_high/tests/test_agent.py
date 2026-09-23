"""Verify the tool's KB-lookup translation; the model's answer is out of scope here.

Requires this control's own .venv with requirements.txt installed (agent
imports agent_framework at module load time), matching repository convention
for per-control tests.
"""

import importlib.util
from pathlib import Path
import sys

import pytest

CONTROL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CONTROL))
SPEC = importlib.util.spec_from_file_location("qlt001_agent", CONTROL / "agent.py")
agent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(agent)


@pytest.mark.parametrize("topic,window", [
    ("vpn_setup", 1), ("password_reset", 2), ("license_renewal", 1),
])
def test_given_healthy_window_when_looked_up_then_real_article_returned(topic, window):
    result = agent.lookup(topic, window)

    assert result != agent.NO_CURRENT_ARTICLE
    assert "SecureConnect" not in result or topic == "vpn_setup"


def test_given_removed_article_when_looked_up_then_explicit_gap_marker():
    assert agent.lookup("vpn_setup", 3) == agent.NO_CURRENT_ARTICLE


def test_given_shortened_article_when_looked_up_then_dropped_detail_is_absent():
    result = agent.lookup("password_reset", 3)

    assert result != agent.NO_CURRENT_ARTICLE
    assert "MFA" not in result and "IT-ACCESS" not in result
