"""Build the monitored Agent Framework workload; no governance decisions here.

This control's decision is computed later, asynchronously, from Continuous
Evaluation's own groundedness score -- nothing in this file measures or
claims groundedness itself.
"""

from typing import Annotated

from agent_framework import Agent, tool
from agent_framework.foundry import FoundryChatClient

from workload import Topic, article_for

AGENT_ID = "it-helpdesk-kb-assistant"
NO_CURRENT_ARTICLE = "NO_CURRENT_ARTICLE"


def lookup(topic: Topic, window: int) -> str:
    """Translate the KB lookup into what the tool returns to the model.

    Kept independent of ``agent_framework`` so this translation is testable
    without a Foundry connection.
    """
    article = article_for(topic, window)
    return article if article is not None else NO_CURRENT_ARTICLE


def build_agent(client: FoundryChatClient) -> Agent:
    """Connect the real model to the synthetic knowledge base tool."""

    @tool(approval_mode="never_require")
    def lookup_it_kb(
        topic: Annotated[Topic, "The synthetic IT knowledge-base topic to look up."],
        window: Annotated[int, "Copy the request's demo window number unchanged."],
    ) -> str:
        """Return the KB article visible in this demo window, or an explicit gap marker."""
        return lookup(topic, window)

    return Agent(
        client=client,
        name=AGENT_ID,
        instructions=(
            "Answer the user's IT helpdesk question about exactly one topic per "
            "request: vpn_setup, password_reset, or license_renewal. Call "
            "lookup_it_kb exactly once with the request's topic and window, and "
            "answer using only what it returns. If it returns NO_CURRENT_ARTICLE, "
            "tell the user no current article is available and to open a "
            "helpdesk ticket -- never invent a VPN client name, portal URL, "
            "approval policy, or renewal date that the lookup did not return. "
            "Never request or repeat personal data."
        ),
        tools=[lookup_it_kb],
        default_options={"store": False, "max_output_tokens": 400},
    )
