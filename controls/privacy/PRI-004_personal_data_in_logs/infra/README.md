# PRI-004 infrastructure

This incremental deployment owns only the Azure resources required by
PRI-004:

- a dedicated Log Analytics workspace;
- one custom table reserved for synthetic log records (`PRI004AppLogs_CL`
  by default);
- a `kind: 'Direct'` data collection rule, which gets its own logs-ingestion
  endpoint so no separate Data Collection Endpoint is deployed;
- scoped Data Purger, Log Analytics Data Reader, and Monitoring Metrics
  Publisher access for the local demo identity.

Deploy the shared Foundry resources first with the repository-level
deployment. Then, from the repository root, run:

```bash
./controls/privacy/PRI-004_personal_data_in_logs/infra/deploy.sh
```

The script reads generic settings from the repository's shared `infra/.env`,
reads control settings from the PRI-004 `.env`, deploys in incremental mode,
and writes the workspace, table, and data collection rule details back to
the PRI-004 `.env`.

This control uses the real Azure Monitor **Data Purge API** for deletion, not
an immediate delete call. Purge requests are asynchronous (Microsoft states
completion can take up to 30 days) and rate-limited to 50 requests per hour.
The demo discloses this rather than simulating instant deletion. See
[Manage personal data in Azure Monitor Logs](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/personal-data-mgmt),
[Logs Ingestion API overview](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/logs-ingestion-api-overview),
and
[Workspace Purge API](https://learn.microsoft.com/en-us/rest/api/loganalytics/workspace-purge/purge).
