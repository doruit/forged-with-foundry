# DAT-PRE-002 infrastructure

**Not applicable.** DAT-PRE-002's core mechanism is Microsoft Purview
Information Protection, read and assigned through Microsoft Graph against
the signed-in demo user's own OneDrive. This control owns no Azure resource
and has no `main.bicep`/`deploy.sh` of its own.

## Prerequisites (Microsoft 365 tenant, not Azure)

1. Register a public-client Microsoft Entra app (Azure Portal → **Microsoft
   Entra ID** → **App registrations** → **New registration**). No redirect
   URI or client secret is required for the device-code flow used here.
2. Under **Authentication**, enable **Allow public client flows**.
3. Under **API permissions**, add Microsoft Graph delegated permissions
   `Files.ReadWrite.All` and `User.Read`, and grant admin consent if your
   tenant requires it.
4. Confirm at least two sensitivity labels are already published for your
   account in Microsoft Purview (most Microsoft 365 Business/Enterprise
   tenants already have default labels).
5. Enable metered Microsoft Graph APIs for your tenant — required by
   `assignSensitivityLabel` — following
   [Enable metered APIs and services in Microsoft Graph](https://learn.microsoft.com/en-us/graph/metered-api-setup?tabs=azurecloudshell).
6. Copy `.env.example` to `.env` and fill in the app's client ID, your
   tenant ID (or leave `organizations`), and the two label GUIDs.

## Optional: shared Foundry infrastructure

The Foundry explanation step is optional. If you want it, deploy the shared
root infrastructure first, exactly as for the other controls:

```bash
./infra/deploy.sh
```

No control-specific Foundry resources are created for DAT-PRE-002; it reads
`AZURE_AI_PROJECT_ENDPOINT` and `AZURE_OPENAI_CHAT_DEPLOYMENT` from the
shared `infra/.env` the same way other controls do.

## Cleanup

Use the **Cleanup demo folder** action in the running demo, or call the
`cleanup()` method directly — it deletes only the `DAT-PRE-002-demo` OneDrive
folder and the synthetic files inside it. No Azure resource or shared
infrastructure is affected because none is owned by this control.
