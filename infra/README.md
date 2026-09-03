<p align="center">
  <img src="../media/themepack/fwf-badge-small-only-logo.png" alt="Forged with Foundry" width="223">
</p>

# Shared Infrastructure — Microsoft Foundry

Provisions only resources shared by all controls. Each control owns and
incrementally deploys any additional Azure resources from its own folder.
Configuration is read from `infra/.env`.

## What gets deployed

| Resource | Details |
|---|---|
| Foundry account | `Microsoft.CognitiveServices/accounts` (kind `AIServices`), system-assigned identity, project management enabled |
| Default project | `accounts/projects` child resource |
| `gpt-5` | GA chat/reasoning model (`2025-08-07`), `GlobalStandard` |
| `gpt-5-mini` | GA cost-efficient model (`2025-08-07`), `GlobalStandard` |
| `text-embedding-3-large` | GA embeddings model, `GlobalStandard` |

## Infrastructure design

```mermaid
flowchart TB
  DEV[Local Chainlit demo]

  subgraph RG[Azure resource group]
    subgraph F[Foundry AI Services account]
      P[Default project]
      G5[gpt-5]
      G5M[gpt-5-mini]
      E[text-embedding-3-large]
      P --> G5
      P --> G5M
      P --> E
    end

  end

  DEV -->|Entra ID| P

  classDef governance fill:#6E56CF,stroke:#A855F7,color:#FFFFFF
  classDef platform fill:#3B82F6,stroke:#00D4FF,color:#FFFFFF
  classDef evidence fill:#00D4FF,stroke:#3B82F6,color:#0D1117
  classDef intelligence fill:#A855F7,stroke:#6E56CF,color:#FFFFFF
  classDef neutral fill:#1F2937,stroke:#6E56CF,color:#FFFFFF
  class DEV neutral
  class P governance
  class G5,G5M,E intelligence
```

## Files

- [main.bicep](main.bicep) — resource definitions and outputs
- [main.bicepparam](main.bicepparam) — parameters read from environment variables
- [deploy.sh](deploy.sh) — loads `.env`, runs the deployment, writes endpoints back to `.env`

## Prerequisites

- `az login` completed
- Bash and the Azure CLI available on your PATH
- An `infra/.env` file (copy from `infra/.env.example`) with at least:

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
2. Validate and deploy the Bicep template in incremental mode (models are deployed serially).
3. Write these values back into `infra/.env`:
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
- **Control resources:** deploy shared infrastructure first, then run the
  deployment script in the relevant control folder. Incremental deployments
  preserve resources owned by other templates.
- **Deployment behavior:** a resource included in an incremental deployment is
  reapplied from its complete declaration; do not split ownership of one Azure
  resource across control templates.
- **Microsoft guidance:** see [ARM deployment modes](https://learn.microsoft.com/azure/azure-resource-manager/templates/deployment-modes)
  and [Bicep parameter files](https://learn.microsoft.com/azure/azure-resource-manager/bicep/parameter-files).
- **Clean up:** `az group delete --name <AZURE_RESOURCE_GROUP> --yes --no-wait`

---

<p align="center">
  <img src="../media/themepack/fwf-footer.png" alt="Forged with Foundry" width="814">
</p>
