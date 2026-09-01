"""Agent Framework adapter that accepts governed content only."""

from __future__ import annotations

import os

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.identity import AzureCliCredential


class GovernedAgent:
    def __init__(self) -> None:
        self._agent = Agent(
            client=FoundryChatClient(
                project_endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"],
                model=os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"],
                credential=AzureCliCredential(),
            ),
            name="GovernedAssistant",
            instructions=(
                "You are a concise assistant. All content you receive has already passed "
                "the deterministic PRI-001 boundary. Never attempt to reconstruct redacted "
                "values. Clearly state when you are reasoning over redacted content."
            ),
        )

    async def run(self, governed_text: str) -> str:
        result = await self._agent.run(governed_text)
        return result.text
