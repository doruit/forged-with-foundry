"""The synthetic support assistant whose model CHG-002 governs.

It has no tools: it answers refund-policy questions from its instructions
only, so evaluating a candidate can never change a system (see the agent
optimizer warning about tools that modify production systems).
"""

from __future__ import annotations

from azure.ai.projects.models import PromptAgentDefinition

from . import AGENT_ID

REFUND_POLICY = """Contoso refund policy (synthetic demo data):
1. Customers may return unused items within 30 days of delivery for a full refund.
2. Damaged or defective items may be returned within 90 days; Contoso pays return shipping.
3. Gift cards, downloadable software and personalised items cannot be refunded.
4. Refunds go back to the original payment method within 5 business days after the return arrives.
5. Orders above EUR 500 need a support specialist to approve the refund.
6. Without an order number, ask for it before promising anything."""

INSTRUCTIONS = (
    "You are Contoso's customer support assistant. Answer only from the refund policy below. "
    "Be short and factual: one to three sentences. If the policy does not cover a question, say so "
    "and offer to connect the customer with a support specialist. Never invent policy.\n\n"
    + REFUND_POLICY
)


def definition(deployment_name: str, instructions: str = INSTRUCTIONS) -> PromptAgentDefinition:
    return PromptAgentDefinition(model=deployment_name, instructions=instructions)


def create_version(project_client, deployment_name: str, *, instructions: str = INSTRUCTIONS, description: str = "") -> str:
    """Create a new immutable agent version that uses the given model deployment."""

    agent = project_client.agents.create_version(
        agent_name=AGENT_ID,
        definition=definition(deployment_name, instructions),
        description=description or f"CHG-002 demo version on deployment {deployment_name}",
    )
    return str(agent.version)
