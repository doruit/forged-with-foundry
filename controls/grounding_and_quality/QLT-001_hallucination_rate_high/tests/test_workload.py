"""The knowledge base is the only place each fleet profile's drift is scripted."""

from pathlib import Path
import sys

import pytest

CONTROL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CONTROL))
from workload import CONTRACTOR, FLEET, PLATFORM, REGIONAL, TOPICS, article_for  # noqa: E402


@pytest.mark.parametrize("topic", TOPICS)
@pytest.mark.parametrize("window", [1, 2])
def test_given_healthy_window_when_looked_up_then_current_article_returned(topic, window):
    assert article_for(REGIONAL, topic, window) is not None


@pytest.mark.parametrize("topic,expected_none", [
    ("vpn_setup", True), ("license_renewal", True), ("password_reset", False),
])
def test_given_drift_window_when_looked_up_then_degraded_or_missing_article(topic, expected_none):
    result = article_for(REGIONAL, topic, 3)

    assert (result is None) == expected_none


def test_given_unsupported_topic_when_looked_up_then_rejected():
    with pytest.raises(ValueError):
        article_for(REGIONAL, "unsupported_topic", 1)


@pytest.mark.parametrize("window", [0, -1, "3"])
def test_given_invalid_window_when_looked_up_then_rejected(window):
    with pytest.raises(ValueError):
        article_for(REGIONAL, "vpn_setup", window)


@pytest.mark.parametrize("window", [1, 2, 3, 4])
@pytest.mark.parametrize("topic", TOPICS)
def test_given_platform_profile_when_looked_up_at_any_demo_window_then_current_article_returned(topic, window):
    assert article_for(PLATFORM, topic, window) is not None


@pytest.mark.parametrize("window", [1, 2, 3, 4])
@pytest.mark.parametrize("topic", TOPICS)
def test_given_contractor_profile_when_looked_up_at_any_demo_window_then_no_article_returned(topic, window):
    assert article_for(CONTRACTOR, topic, window) is None


def test_given_the_fleet_when_inspected_then_three_distinctly_identified_profiles():
    assert len(FLEET) == 3
    assert len({profile.agent_id for profile in FLEET}) == 3
    assert {profile.strict_instructions for profile in FLEET} == {True, False}
