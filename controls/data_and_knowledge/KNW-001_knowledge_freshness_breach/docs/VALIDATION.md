# KNW-001 validation boundary

## Captured Azure results

Captured on 2026-10-27 from the documented `infra/deploy.py deploy` invocation:

```text
ARM validation: Succeeded (Free Search, LRS storage, West Europe).
Foundation deployed. No monitor, review endpoint, indexer, or Teams sender is deployed.
```

The subsequent `inspect` command returned:

```json
[
  {
    "name": "srch-knw001-zg2elyromiexs",
    "type": "Microsoft.Search/searchServices",
    "owned": true
  },
  {
    "name": "stknw001zg2elyromiexs",
    "type": "Microsoft.Storage/storageAccounts",
    "owned": true
  }
]
```

Read-only Azure CLI service inspection returned these projections:

```json
{
  "disableLocalAuth": true,
  "region": "West Europe",
  "sku": "free",
  "state": "Succeeded"
}
```

```json
{
  "allowBlobPublicAccess": false,
  "allowSharedKeyAccess": false,
  "minimumTlsVersion": "TLS1_2",
  "sku": "Standard_LRS",
  "state": "Succeeded"
}
```

The non-destructive cleanup plan returned:

```text
Deletes only the KNW-001 Search service and Storage Account (including all their data/scoped grants).
Keeps the resource group, deployment history, and subscription policy.
```

These are real terminal results, not example success records. They prove
foundation provisioning/configuration, not live monitoring or Teams delivery.
Subscription/tenant IDs, user identities, and credentials are omitted. No
destructive cleanup was authorized or executed.

## Policy change

Initial ARM validation failed with `RequestDisallowedByPolicy`. With explicit
owner approval, five resource types were appended to the strict subscription
allowlist: `Microsoft.Search/searchServices`,
`Microsoft.Storage/storageAccounts/blobServices`, `Microsoft.Web/sites/config`,
`Microsoft.Insights/components`, and `Microsoft.OperationalInsights/workspaces`.
All 23 existing entries, assignment scope, exclusions, and enforcement mode were
verified unchanged. The definition still uses `Deny` for types not in the
allowlist; no exemption was created. Subsequent ARM validation succeeded.
The pre-change snapshot is local-only under `.azure/`.

This is a subscription-wide type allowance, not a per-control exception. It
does not authorize an arbitrary deployment, enforce a SKU, or certify costs.

## Local checks

- Policy baseline: 25 tests passed.
- Deployment scope/ownership/template guardrails: nine tests passed.
- The documented isolated local-test command passed all 34 control tests; the repository README structure gate passed all 11 tests.
- Bicep compiled without warnings after correcting Search `hostingMode` casing.
- Deployment CLI `--help`, real ARM validation/deployment, inspection, and non-destructive cleanup plan were exercised.
- Static preview: all three states were captured at 1365 x 1100. At 390 x 844, scenario controls worked without horizontal overflow or visible text overlap. No browser console errors were observed.
- Preview capture used ephemeral Playwright tooling; no runtime/UI dependency was added to the control.

## Remaining release gates

There is no index/indexer, SAS configurator, authenticated review endpoint,
scheduled Function, persisted decision evidence, or Teams sender. The empty
review container does not establish actor identity or review time. Future
runtime evidence must never derive trust from user-editable metadata alone.

Live source/index synchronization, SAS expiry/renewal, review identity/ETag/time
binding, managed-identity runtime access, unavailable-service handling,
notification receipt, and destructive cleanup remain unvalidated. Real Teams
delivery also requires a licensed tenant. The control remains Planned.