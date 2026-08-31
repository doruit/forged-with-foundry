"""
Shared utilities for all governance control demos.
"""

import os
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient


def get_project_client() -> AIProjectClient:
    """Returns an authenticated Azure AI Project client."""
    endpoint = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
    credential = DefaultAzureCredential()
    return AIProjectClient(endpoint=endpoint, credential=credential)


def print_result(control_name: str, result: dict):
    """Pretty-prints a governance control result."""
    print(f"\n{'='*50}")
    print(f"Control: {control_name}")
    print(f"{'='*50}")
    for key, value in result.items():
        print(f"  {key}: {value}")
    print()
