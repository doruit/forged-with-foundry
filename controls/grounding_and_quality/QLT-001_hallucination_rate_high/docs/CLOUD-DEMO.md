---
title: QLT-001 cloud demo runner
description: Run the full QLT-001 demo from GitHub Actions instead of a local machine, and what that requires and costs.
ms.date: 2026-09-25
---

# Running QLT-001 from the cloud

Continuous Evaluation's own score takes roughly a day to become queryable
(observed live, not a documented SLA). The [Demo](../README.md#demo) walkthrough
assumes a local machine that stays reachable for that whole window. This page
is for anyone who cannot keep a laptop alive that long: it moves the same
deploy → run → wait → evaluate → clean up sequence into
[.github/workflows/qlt-001-cloud-demo.yml](../../../../.github/workflows/qlt-001-cloud-demo.yml),
a manually triggered GitHub Actions workflow.

## What this is, and is not, for

- It is a convenience for the wait, not a different demo. It runs the same
  `demo.py` steps against the same Foundry project the local walkthrough uses.
- It is not a way to skip the one-time Azure setup below. Someone with
  Owner/User Access Administrator rights on the target subscription still has
  to create a workload identity once, per fork or repository.
- It is not free or side-effect-free. Every run deploys real control-owned
  Monitor resources, sends real (synthetic) traffic through a real model
  deployment, and — unless cleanup is disabled for the run — deletes those
  resources afterward. Continuous Evaluation and model tokens are billed
  Azure usage.
- It accepts whatever real, complete decision Continuous Evaluation returns
  (`quality_review_required` or `no_review_required`); it does not require or
  wait for a breach.

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
