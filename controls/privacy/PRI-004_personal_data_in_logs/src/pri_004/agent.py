"""Foundry agent that explains deterministic PRI-004 decisions."""

from __future__ import annotations

import json
import os

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.identity import AzureCliCredential

from .models import LogDecision


class LogOperationsAgent:
    """Non-authoritative agent: explain and guide, never decide, mask, purge, or change policy."""

    def __init__(self) -> None:
        self._agent = Agent(
            client=FoundryChatClient(
                project_endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"],
                model=os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"],
                credential=AzureCliCredential(),
            ),
            name="LogOperationsAssistant",
            instructions=(
                "You explain PRI-004 personal-data-in-logs decisions to a Privacy Officer. "
                "The supplied decisions were made by deterministic code and are authoritative. "
                "You only ever see metadata: a decision id, field name, and PII category names. "
                "You never see the raw log message. Never invent message content, claim a purge "
                "completed, or claim a field was suppressed; those are separate guarded actions "
                "the human must explicitly request. For pii_detected records, explain that a "
                "redacted preview can be requested and, separately, a real Azure Monitor Data "
                "Purge request can be submitted, which is asynchronous and can take up to 30 "
                "days to complete. For blocked records, explain that detection could not "
                "complete safely, so the record cannot be cleared automatically. Be concise and "
                "use plain language."
            ),
        )

    async def explain(self, decisions: list[LogDecision]) -> str:
        safe_payload = [decision.safe_dict() for decision in decisions]
        result = await self._agent.run(
            "Explain this metadata-only PRI-004 scan. Separate clean, pii_detected, and "
            "blocked outcomes. Do not infer or repeat any log message content.\n\n"
            + json.dumps(safe_payload, indent=2)
        )
        return result.text
