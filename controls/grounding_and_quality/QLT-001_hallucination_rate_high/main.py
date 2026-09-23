"""Serve the hosted agent whose traffic Continuous Evaluation samples and scores.

Unlike VAL-001, this control does not export its own custom telemetry: the
authoritative signal is Foundry's own Continuous Evaluation, which needs the
hosted agent's default tracing enabled to have a "responseCompleted" event to
score. Do not disable observability here.
"""

import os

import truststore

truststore.inject_into_ssl()

from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential

from agent import build_agent


def main() -> None:
    """Serve the hosted agent with Foundry's default observability enabled."""
    with DefaultAzureCredential() as credential:
        client = FoundryChatClient(
            project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
            model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
            credential=credential,
        )
        ResponsesHostServer(build_agent(client)).run()


if __name__ == "__main__":
    main()
