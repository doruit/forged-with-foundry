"""The knowledge base is the only place this demo's drift is scripted."""

from pathlib import Path
import sys

import pytest

CONTROL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CONTROL))
from workload import TOPICS, article_for  # noqa: E402


@pytest.mark.parametrize("topic", TOPICS)
@pytest.mark.parametrize("window", [1, 2])
def test_given_healthy_window_when_looked_up_then_current_article_returned(topic, window):
    assert article_for(topic, window) is not None


@pytest.mark.parametrize("topic,expected_none", [
    ("vpn_setup", True), ("license_renewal", True), ("password_reset", False),
])
def test_given_drift_window_when_looked_up_then_degraded_or_missing_article(topic, expected_none):
    result = article_for(topic, 3)

    assert (result is None) == expected_none


def test_given_unsupported_topic_when_looked_up_then_rejected():
    with pytest.raises(ValueError):
        article_for("unsupported_topic", 1)


@pytest.mark.parametrize("window", [0, -1, "3"])
def test_given_invalid_window_when_looked_up_then_rejected(window):
    with pytest.raises(ValueError):
        article_for("vpn_setup", window)
