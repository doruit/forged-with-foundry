# PRI-003 infrastructure

This incremental deployment owns only the Azure resources required by
PRI-003:

- a dedicated OAuth-only Table Storage account;
- one private table reserved for synthetic DSR records
  (`pri003dsrrequests` by default);
- scoped Storage Table Data Contributor access for the local demo identity.

Deploy the shared Foundry resources first with the repository-level
deployment. Then, from the repository root, run:

```bash
./controls/privacy/PRI-003_data_subject_request_sla_breach/infra/deploy.sh
```

The script reads generic settings from the repository's shared `infra/.env`,
reads control settings from the PRI-003 `.env`, deploys in incremental mode,
and writes the table endpoint and table name back to the PRI-003 `.env`.

Unlike PRI-002's Blob Lifecycle Management scenario, no Azure platform rule
automatically evaluates a data subject request SLA. This is why the
deterministic scan in `src/pri_003/policy.py` is the primary control here,
not a supporting exception detector. See
[Azure Table Storage overview](https://learn.microsoft.com/en-us/azure/storage/tables/table-storage-overview)
and
[Authorize access to tables with Microsoft Entra ID](https://learn.microsoft.com/en-us/azure/storage/tables/authorize-access-azure-active-directory).
