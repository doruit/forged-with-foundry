# Copilot Instructions

This is a demo project showcasing AI Governance Controls using Azure AI Foundry.

## Project Overview
- **Language:** Python
- **Framework:** Azure AI Foundry / Azure AI Evaluation SDK
- **Purpose:** Demonstrate governance controls like PII detection, groundedness checks, content safety, and prompt injection detection.

## Guidelines
- Use Azure AI Foundry SDK and Azure AI Evaluation SDK for all AI interactions.
- Keep demos self-contained per governance control.
- Use `.env` files for secrets; never hardcode credentials.
- Each control lives in its own subfolder under `controls/`.
- Shared utilities go in `shared/`.
