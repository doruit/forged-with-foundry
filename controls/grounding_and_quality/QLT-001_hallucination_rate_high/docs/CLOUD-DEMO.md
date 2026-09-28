---
title: QLT-001 cloud demo runner status
description: Why the GitHub Actions alternative is currently blocked and what must change before it can be used.
ms.date: 2026-09-28
---

# QLT-001 cloud demo runner status

> **Status: blocked, do not dispatch.** The workflow uses a GitHub-hosted
> runner but sets `timeout-minutes: 2900` and polls for up to 48 hours. GitHub
> limits a hosted job to six hours, so this workflow cannot complete its
> documented wait. It has not been run end to end. The local path does not
> need a process to remain active while Foundry scores responses; see the
> [Demo](../README.md#demo) for the supported pause-and-resume flow. Redesign
> this workflow as resumable runs before presenting it as an alternative.

This page records the incomplete GitHub Actions approach and its one-time
setup for maintainers evaluating a future redesign. It is not a runnable
community path today. GitHub's [Actions limits](https://docs.github.com/en/actions/reference/limits)
document the hosted-job execution limit.

## What this is, and is not, for

- The current workflow cannot complete its evaluation wait on a hosted runner.
- It is not a way to skip the one-time Azure setup below. Someone with
  appropriate rights on the target subscription still has to create a
  workload identity once, per fork or repository.
- The workflow's Azure deployment, synthetic traffic, billing, and cleanup
  behavior below describes the intended design, not a verified end-to-end run.

## One-time setup: a workload identity for GitHub Actions

This grants a GitHub Actions job permission to deploy and delete resources in
one resource group, using [workload identity federation](https://learn.microsoft.com/en-us/entra/workload-id/workload-identity-federation)
so no Azure secret is stored in GitHub. Run this once, from a machine already
signed in to the target subscription (`az login`) with rights to create app
registrations and role assignments:

```bash
az ad app create --display-name "qlt-001-cloud-demo" \
  --query appId -o tsv
# APP_ID=<value printed above>

az ad sp create --id "$APP_ID"
# PRINCIPAL_ID=<the sp's objectId, from `az ad sp show --id "$APP_ID" --query id -o tsv`>

az ad app federated-credential create --id "$APP_ID" --parameters '{
  "name": "github-qlt001-production",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:<owner>/<repo>:environment:production",
  "audience": "api://AzureADTokenExchange"
}'

az role assignment create --assignee-object-id "$PRINCIPAL_ID" \
  --assignee-principal-type ServicePrincipal \
  --role "Contributor" \
  --scope "/subscriptions/<subscription-id>/resourceGroups/<resource-group>"
az role assignment create --assignee-object-id "$PRINCIPAL_ID" \
  --assignee-principal-type ServicePrincipal \
  --role "Role Based Access Control Administrator" \
  --scope "/subscriptions/<subscription-id>/resourceGroups/<resource-group>"
az role assignment create --assignee-object-id "$PRINCIPAL_ID" \
  --assignee-principal-type ServicePrincipal \
  --role "Azure AI Developer" \
  --scope "/subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.CognitiveServices/accounts/<foundry-account-name>"
az role assignment create --assignee-object-id "$PRINCIPAL_ID" \
  --assignee-principal-type ServicePrincipal \
  --role "Foundry User" \
  --scope "/subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.CognitiveServices/accounts/<foundry-account-name>"
```

Replace `<owner>/<repo>` with the fork or repository that will run the
workflow, `<subscription-id>`/`<resource-group>` with the resource group that
already contains the Foundry project used for the local demo, and
`<foundry-account-name>` with that Foundry account's own resource name (not
the project name inside it). All four roles were confirmed necessary on a
real run: **Contributor** and **Role Based Access Administrator**, scoped to
the resource group, let the Bicep deployment create the Monitor resources and
their own role assignments (see [infra/main.bicep](../infra/main.bicep));
**Azure AI Developer** and **Foundry User**, scoped to the Foundry account
itself, let `demo.py` register agents, evaluation rules, and read Continuous
Evaluation results through the Foundry SDK. None of this is subscription-wide
Owner access.

In the repository's **Settings → Environments → production**, add these as
environment variables (not secrets — none of them is a credential; the
federated credential above is what actually authenticates):

| Variable | Value |
|---|---|
| `AZURE_CLIENT_ID` | the app registration's `appId` |
| `AZURE_TENANT_ID` | `az account show --query tenantId -o tsv` |
| `AZURE_SUBSCRIPTION_ID` | the target subscription id |
| `AZURE_RESOURCE_GROUP` | the resource group above |
| `FOUNDRY_PROJECT_ENDPOINT` | the Foundry project endpoint used by the local demo |
| `AZURE_AI_MODEL_DEPLOYMENT_NAME` | the model deployment name used by the local demo |

## Running it

From the **Actions** tab, select **QLT-001: run the demo in the cloud** →
**Run workflow**, choose a window (1–2 healthy, 3–4 degraded), and choose
whether the run should clean up its own resources afterward. A run takes
60–90 minutes plus however long Continuous Evaluation itself takes for that
attempt (budgeted up to roughly 24 hours; see the workflow's own
`timeout-minutes`).

## Getting the evidence back

Each run uploads a `qlt-001-cloud-demo-<run-id>` artifact (30-day retention)
containing the same minimized `window.json`/`evidence.json`/`run-summary.json`
shape the local demo writes to `.azure/qlt001/windows/<window-id>/` — no
prompts, full answers, KB content, tokens, or webhook URLs. Download it from
the completed run's summary page.
