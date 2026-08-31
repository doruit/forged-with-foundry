# Infrastructure — Microsoft Foundry + GPT-5 Models

Provisions a **Microsoft Foundry** account with a **default project** and deploys
the latest GA GPT-5 models, using **Bicep**. Configuration is read from the
repo-root `.env` file; deployment is driven by a small shell wrapper.

## What gets deployed

| Resource | Details |
|---|---|
| Foundry account | `Microsoft.CognitiveServices/accounts` (kind `AIServices`), system-assigned identity, project management enabled |
| Default project | `accounts/projects` child resource |
| `gpt-5` | GA chat/reasoning model (`2025-08-07`), `GlobalStandard` |
| `gpt-5-mini` | GA cost-efficient model (`2025-08-07`), `GlobalStandard` |
| `text-embedding-3-large` | GA embeddings model, `GlobalStandard` |

## Files

- [main.bicep](main.bicep) — resource definitions and outputs
- [main.bicepparam](main.bicepparam) — parameters read from environment variables
- [deploy.sh](deploy.sh) — loads `.env`, runs the deployment, writes endpoints back to `.env`

## Prerequisites

- `az login` completed
- Bash and the Azure CLI available on your PATH
- A `.env` file at the repo root (copy from `.env.example`) with at least:

  ```dotenv
  AZURE_SUBSCRIPTION_ID=<your-subscription-id>
  AZURE_RESOURCE_GROUP=rg-forged-with-foundry
  AZURE_LOCATION=swedencentral
  FOUNDRY_ACCOUNT_NAME=<globally-unique-name>
  ```

## Deploy

```bash
./infra/deploy.sh
```

The script will:

1. Create the resource group if it doesn't exist.
2. Deploy the Bicep template (models are deployed serially).
3. Write these values back into `.env`:
   - `AZURE_AI_PROJECT_ENDPOINT`
   - `AZURE_CONTENT_SAFETY_ENDPOINT`
   - `AZURE_OPENAI_DEPLOYMENT` (gpt-5-mini)
   - `AZURE_OPENAI_CHAT_DEPLOYMENT` (gpt-5)
   - `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` (text-embedding-3-large)

## Notes

- **Quota:** GA `gpt-5` / `gpt-5-mini` deploy on most Tier 1+ subscriptions. If a
  region lacks capacity, change `AZURE_LOCATION` (e.g. `eastus2`) and adjust the
  `*_CAPACITY` values in `.env`.
- **Newer models:** GPT-5.5 / GPT-5.6 require Tier 5–6 quota by default, so this
  template uses GA GPT-5 for reliability. To use them, change the `name`/`version`
  in [main.bicep](main.bicep).
- **Clean up:** `az group delete --name <AZURE_RESOURCE_GROUP> --yes --no-wait`
