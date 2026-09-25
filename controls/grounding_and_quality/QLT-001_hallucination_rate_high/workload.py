"""Synthetic IT-helpdesk knowledge base, shared by a small fleet of agents.

Each agent in the fleet represents a different team maintaining the same
three-topic knowledge base with a different level of rigor. The "drift" each
profile experiences is a scripted property of its own staleness curve, not a
database this control writes to, so a demo run is fully reproducible. Real
groundedness differences across the fleet come from two genuinely independent,
live-measured levers, not a scripted score: which KB content a profile's tool
call returns for a given window (``AgentProfile.stale_from_window`` /
``degraded_kb``), and how strictly that profile's own instructions forbid
speculation when the tool returns no article (``AgentProfile.strict_instructions``,
consumed by ``agent.py``). Continuous Evaluation then measures each profile's
real, live model output against its own real input -- nothing about the
resulting score is scripted.
"""

from typing import Literal, NamedTuple

Topic = Literal["vpn_setup", "password_reset", "license_renewal"]

TOPICS: tuple[Topic, ...] = ("vpn_setup", "password_reset", "license_renewal")

NO_CURRENT_ARTICLE = "NO_CURRENT_ARTICLE"

_CURRENT: dict[Topic, str] = {
    "vpn_setup": (
        "Current VPN client: SecureConnect 4.2. Users authenticate with their "
        "Entra ID account and the Contoso VPN profile pushed by Intune. Open a "
        "ticket in queue IT-VPN for access issues."
    ),
    "password_reset": (
        "Self-service password reset is available at "
        "https://reset.contoso.example using the registered MFA method. "
        "Helpdesk-assisted resets require manager approval logged in queue "
        "IT-ACCESS."
    ),
    "license_renewal": (
        "Software licenses renew automatically every January through the "
        "Contoso Software Center. No user action is required unless Software "
        "Center reports an expired-license error."
    ),
}

# The Regional Team profile's degraded state: an article is silently removed
# (None) or quietly loses the detail that would keep an answer grounded,
# without any error being raised -- a knowledge base that has not kept pace
# with a platform change.
_REGIONAL_DEGRADED: dict[Topic, str | None] = {
    "vpn_setup": None,
    "password_reset": "Self-service password reset is available at https://reset.contoso.example.",
    "license_renewal": None,
}

# The Contractor Team degrades at the same point as the Regional Team, but
# permissive instructions make its response to the missing articles different.
_CONTRACTOR_ABSENT: dict[Topic, str | None] = {topic: None for topic in TOPICS}


class AgentProfile(NamedTuple):
    """One fleet member's identity, KB rigor, and instruction rigor.

    ``stale_from_window`` is the first window number at or after which
    ``degraded_kb`` applies instead of ``_CURRENT``; a value greater than the
    demo's highest window (4) means the profile's KB never degrades within
    the demo. ``strict_instructions`` is consumed by ``agent.py`` to select
    between instructions that forbid speculation outright and weaker
    instructions that permit a labeled "reasonable assumption" -- the second
    lever this demo uses to produce genuinely different, live-measured
    groundedness across the fleet, independent of KB content alone.
    """

    agent_id: str
    display_name: str
    stale_from_window: int
    degraded_kb: dict[Topic, str | None]
    strict_instructions: bool


PLATFORM = AgentProfile(
    agent_id="it-helpdesk-kb-assistant-platform",
    display_name="Platform Team",
    stale_from_window=5,
    degraded_kb=_CURRENT,
    strict_instructions=True,
)
REGIONAL = AgentProfile(
    agent_id="it-helpdesk-kb-assistant-regional",
    display_name="Regional Team",
    stale_from_window=3,
    degraded_kb=_REGIONAL_DEGRADED,
    strict_instructions=True,
)
CONTRACTOR = AgentProfile(
    agent_id="it-helpdesk-kb-assistant-contractor",
    display_name="Contractor Team",
    stale_from_window=3,
    degraded_kb=_CONTRACTOR_ABSENT,
    strict_instructions=False,
)

FLEET: tuple[AgentProfile, ...] = (PLATFORM, REGIONAL, CONTRACTOR)


def article_for(profile: AgentProfile, topic: Topic, window: int) -> str | None:
    """Return the KB article visible to ``profile``'s agent in this window.

    Below ``profile.stale_from_window``, every profile sees the same current
    article; at or after it, ``profile.degraded_kb`` applies instead. This is
    the only place any profile's staleness is defined.
    """
    if topic not in _CURRENT:
        raise ValueError("Unsupported synthetic KB topic")
    if type(window) is not int or window < 1:
        raise ValueError("window must be a positive integer")
    return _CURRENT[topic] if window < profile.stale_from_window else profile.degraded_kb[topic]


def lookup(profile: AgentProfile, topic: Topic, window: int) -> str:
    """Translate the KB lookup into what the tool returns to the model.

    Kept independent of any agent SDK so this translation is testable, and
    reusable client-side when a prompt agent's tool call is executed locally
    (a prompt agent is server-side-only and cannot execute this itself).
    """
    article = article_for(profile, topic, window)
    return article if article is not None else NO_CURRENT_ARTICLE
