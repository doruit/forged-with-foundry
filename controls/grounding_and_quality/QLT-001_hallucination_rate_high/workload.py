"""Synthetic IT-helpdesk knowledge base with a scripted staleness window.

The same (topic, window) pair always returns the same article, so a demo run
is reproducible without any external or mutable state -- the "drift" is a
scripted property of the window number, not a database this control writes
to.
"""

from typing import Literal

Topic = Literal["vpn_setup", "password_reset", "license_renewal"]

TOPICS: tuple[Topic, ...] = ("vpn_setup", "password_reset", "license_renewal")

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

# Windows 3+ simulate a knowledge base that has not kept pace with a platform
# change: an article is silently removed (None) or quietly loses the detail
# that would keep an answer grounded, without any error being raised.
_STALE: dict[Topic, str | None] = {
    "vpn_setup": None,
    "password_reset": "Self-service password reset is available at https://reset.contoso.example.",
    "license_renewal": None,
}


def article_for(topic: Topic, window: int) -> str | None:
    """Return the KB article visible to the agent in the given demo window.

    Windows 1-2 use the current article; window 3 and later use the
    degraded article -- ``None`` where it was removed entirely, or a
    shortened version where a supporting detail was dropped. This is the
    only place the demo's staleness is defined.
    """
    if topic not in _CURRENT:
        raise ValueError("Unsupported synthetic KB topic")
    if type(window) is not int or window < 1:
        raise ValueError("window must be a positive integer")
    return _CURRENT[topic] if window <= 2 else _STALE[topic]
