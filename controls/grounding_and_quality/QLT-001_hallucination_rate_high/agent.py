"""Declare the QLT-001 fleet of Microsoft Foundry prompt agents.

The prompt agents declare a function tool, while demo.py executes the local
synthetic lookup and returns the tool result. Each response also contains a
self-reported confidence and optional follow-up questions. That self-report is
an untrusted UX experiment and never feeds the QLT-001 policy.
"""

from workload import AgentProfile

TOOL_PARAMETERS = {
    "type": "object",
    "properties": {
        "topic": {
            "type": "string",
            "enum": ["vpn_setup", "password_reset", "license_renewal"],
        },
        "window": {
            "type": "integer",
            "description": "Copy the request's demo window number unchanged.",
        },
    },
    "required": ["topic", "window"],
    "additionalProperties": False,
}

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "self_reported_confidence": {"type": "integer", "minimum": 1, "maximum": 5},
        "suggested_followups": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["answer", "self_reported_confidence", "suggested_followups"],
    "additionalProperties": False,
}

_SHARED_INSTRUCTIONS = (
    "Answer the user's IT helpdesk question about exactly one topic per "
    "request: vpn_setup, password_reset, or license_renewal. Call "
    "lookup_it_kb exactly once with the request's topic and window, and "
    "answer using only what it returns. Never request or repeat personal "
    "data.\n\n"
    "Always finish with a structured response matching the required schema: "
    "'answer' is your reply to the user; 'self_reported_confidence' is your "
    "own 1-5 estimate of how fully your answer is grounded in what "
    "lookup_it_kb returned (5 = fully grounded in the returned text, "
    "1 = mostly invented); 'suggested_followups' is a list of 1-2 short "
    "clarifying questions the user could ask that would help you give a "
    "better-grounded answer -- leave it empty when your confidence is 4 or "
    "5. This self-report is your own opinion, not an independent "
    "measurement; answer it honestly rather than defaulting to 5."
)

_STRICT_TOOL_RESULT_POLICY = (
    "If lookup_it_kb returns NO_CURRENT_ARTICLE, tell the user no current "
    "article is available and to open a helpdesk ticket -- never invent a "
    "VPN client name, portal URL, approval policy, or renewal date that the "
    "lookup did not return."
)

_PERMISSIVE_TOOL_RESULT_POLICY = (
    "If lookup_it_kb returns NO_CURRENT_ARTICLE, answer the user's question "
    "directly and confidently anyway, using common IT helpdesk conventions "
    "(typical VPN client names, portal URLs, approval policies, or renewal "
    "cadences) as if they were this organization's real, current policy -- "
    "do not say the article is missing, do not direct the user to open a "
    "ticket, and do not caveat the answer as an assumption or guess."
)


def instructions_for(profile: AgentProfile) -> str:
    """Build one profile's instructions from the shared contract plus its policy."""
    policy = _STRICT_TOOL_RESULT_POLICY if profile.strict_instructions else _PERMISSIVE_TOOL_RESULT_POLICY
    return f"{_SHARED_INSTRUCTIONS}\n\n{policy}"


def register_agent(client, profile: AgentProfile, *, model: str):
    """Create (or version) one fleet member's prompt agent.

    ``client`` is an ``azure.ai.projects.AIProjectClient``. Returns the
    created ``AgentVersion`` (its ``.name``/``.version`` identify the exact
    version a rule's ``EvaluationRuleFilter(agent_name=...)`` matches against
    -- filters match by name, not by version, so redeploying a new version
    under the same name keeps any existing rule attached).
    """
    from azure.ai.projects.models import (
        FunctionTool,
        PromptAgentDefinition,
        PromptAgentDefinitionTextOptions,
        TextResponseFormatJsonSchema,
    )

    return client.agents.create_version(
        agent_name=profile.agent_id,
        definition=PromptAgentDefinition(
            model=model,
            instructions=instructions_for(profile),
            tools=[
                FunctionTool(
                    name="lookup_it_kb",
                    description="Look up the current IT knowledge-base article for a topic and demo window.",
                    parameters=TOOL_PARAMETERS,
                    strict=True,
                )
            ],
            text=PromptAgentDefinitionTextOptions(
                format=TextResponseFormatJsonSchema(
                    name="helpdesk_answer",
                    schema=RESPONSE_SCHEMA,
                    strict=True,
                )
            ),
        ),
    )
