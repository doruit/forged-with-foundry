"""Host the synthetic workload and export its verified outcomes to Azure Monitor."""

import logging
import os

import truststore

truststore.inject_into_ssl()

from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential
from azure.monitor.opentelemetry.exporter import AzureMonitorLogExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import SimpleLogRecordProcessor
from opentelemetry.sdk.resources import Resource

from agent import build_agent


def create_event_logger(credential: DefaultAzureCredential) -> tuple[logging.Logger, LoggerProvider]:
    """Export only the namespaced outcome logger, using Entra authentication."""
    os.environ.pop("APPLICATIONINSIGHTS_CONNECTION_STRING", None)
    provider = LoggerProvider(resource=Resource.create({"service.name": "VAL-002"}))
    exporter = AzureMonitorLogExporter(
        connection_string=os.environ["VAL002_APPLICATIONINSIGHTS_CONNECTION_STRING"],
        credential=credential,
        disable_offline_storage=True,
    )
    provider.add_log_record_processor(SimpleLogRecordProcessor(exporter))
    logger = logging.getLogger("fwf.val002.outcomes")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.addHandler(LoggingHandler(logger_provider=provider))
    return logger, provider


def main() -> None:
    """Serve the hosted agent with no sensitive-content tracing enabled."""
    with DefaultAzureCredential() as credential:
        logger, provider = create_event_logger(credential)

        def emit(event: dict[str, str | int | bool]) -> None:
            logger.info("Verified synthetic ticket outcome", extra={
                "microsoft.custom_event.name": "TicketTriaged", **event,
            })

        client = FoundryChatClient(
            project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
            model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
            credential=credential,
        )
        try:
            ResponsesHostServer(build_agent(client, emit), configure_observability=None).run()
        finally:
            provider.shutdown()


if __name__ == "__main__":
    main()
