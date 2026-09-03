# PRI-001 infrastructure

This incremental deployment owns only the Azure resources required by PRI-001:

- a single-service Azure AI Language account;
- OAuth-only Blob Storage with one-day soft delete;
- private `pii-source` and `pii-redacted` containers;
- scoped Language and Storage data-plane RBAC.

Deploy the shared Foundry resources first with `../../../infra/deploy.sh`. Then,
from the repository root, run:

```bash
./controls/privacy/PRI-001_pii_exposure/infra/deploy.sh
```

The script reads generic settings from the repository's shared `infra/.env`,
reads control settings from the PRI-001 `.env`, deploys in incremental mode,
and writes the control endpoints back to the PRI-001 `.env`.

See [ARM deployment modes](https://learn.microsoft.com/azure/azure-resource-manager/templates/deployment-modes),
[Document PII managed identities](https://learn.microsoft.com/azure/ai-services/language-service/native-document-support/managed-identities),
and [authorize Blob access with Microsoft Entra ID](https://learn.microsoft.com/azure/storage/blobs/authorize-access-azure-active-directory).
