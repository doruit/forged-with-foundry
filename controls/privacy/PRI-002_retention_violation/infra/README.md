# PRI-002 infrastructure

This incremental deployment owns only the Azure resources required by PRI-002:

- a dedicated OAuth-only Blob Storage account;
- a private `pri-002-*` demo container;
- one-day Blob soft delete for recovery;
- a lifecycle rule that deletes 30-day records under `records/` when their
  `LifecycleClass` Blob index tag matches the configured retention class;
- scoped Storage Blob Data Contributor access for the local demo identity.

Deploy the shared Foundry resources first with `../../../infra/deploy.sh`. Then,
from the repository root, run:

```bash
./controls/privacy/PRI-002_retention_violation/infra/deploy.sh
```

The script reads generic settings from the repository's shared `infra/.env`,
reads control settings from the PRI-002 `.env`, deploys in incremental mode,
and writes the Blob endpoint and container back to the PRI-002 `.env`.

A Storage account has one complete lifecycle management policy. PRI-002 owns
that dedicated account so another control deployment cannot replace its policy.
See [Azure Blob lifecycle management](https://learn.microsoft.com/azure/storage/blobs/lifecycle-management-overview),
[manage Blob data with lifecycle policies](https://learn.microsoft.com/azure/storage/blobs/lifecycle-management-policy-configure),
and [Blob index tags](https://learn.microsoft.com/azure/storage/blobs/storage-manage-find-blobs).
