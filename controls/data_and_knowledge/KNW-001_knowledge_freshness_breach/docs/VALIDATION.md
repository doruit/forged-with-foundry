# KNW-001 validation boundary

This record is chronological. The current result is
[Follow-up live validation — 2026-11-08](#follow-up-live-validation--2026-11-08).
The earlier sections record the foundation-only attempts and the initial
end-to-end run.

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
    "name": "<knw001-search-service>",
    "type": "Microsoft.Search/searchServices",
    "owned": true
  },
  {
    "name": "<knw001-storage-account>",
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
owner approval, required resource types were added to the subscription's strict
allowlist. The existing `Deny` effect remained enabled; no exemption was
created. Subsequent ARM validation succeeded.
The pre-change snapshot is local-only under `.azure/`.

This is a subscription-wide type allowance, not a per-control exception. It
does not authorize an arbitrary deployment, enforce a SKU, or certify costs.

## Deployment attempt — 2026-11-06

The dedicated resource group exists and is tagged for KNW-001, but currently
contains only its Storage account; no Search service is present. The Free-tier
ARM preflight is blocked because the subscription's Free Search quota is
already consumed. The explicit S1 preflight succeeded, but deployment failed
with `ResourcesForSkuUnavailable` in West Europe. No paid Search service was
created. Do not select another region or tier without approval.

## Current deployment state — 2026-11-08

After the user authorized Sweden Central, both ARM validation and deployment
succeeded. Read-only service inspection returned these non-sensitive fields:

```json
{
  "disableLocalAuth": true,
  "partitions": 1,
  "region": "Sweden Central",
  "replicas": 1,
  "sku": "standard",
  "status": "running",
  "tags": {
    "control-id": "KNW-001",
    "purpose": "synthetic-knowledge-freshness-demo"
  }
}
```

Resource inspection confirmed Storage remained in West Europe and Search is
in Sweden Central, both in the dedicated resource group. The non-destructive
Search-only cleanup plan printed:

```text
Deletes only the KNW-001 Search service; the Storage account and its data are retained.
```

At that point S1 was deployed and no deletion had been performed. This proved only
foundation deployment/configuration, not indexing, review, or Foundry behavior.
The runtime run and the verified cleanup that followed are recorded below.

## Local checks

- Policy baseline: 25 tests passed.
- Deployment scope/ownership/template guardrails: nine tests passed.
- The documented isolated local-test command passed all 34 control tests; the repository README structure gate passed all 11 tests.
- Bicep compiled without warnings after correcting Search `hostingMode` casing.
- Deployment CLI `--help`, real ARM validation/deployment, inspection, and non-destructive cleanup plan were exercised.
- Earlier local validation: 89 KNW-001 tests passed; 23 README and governance-contract repository gates pass. These tests use fakes and do not establish live service behavior.
- Static preview: all three states were captured at 1365 x 1100. At 390 x 844, scenario controls worked without horizontal overflow or visible text overlap. No browser console errors were observed.
- Preview capture used ephemeral Playwright tooling; no runtime/UI dependency was added to the control.

## Initial end-to-end runtime validation — 2026-11-08

The documented core path ran against Azure in this order:
`infra/deploy.py deploy`, then `infra/runtime.py deploy`, `configure-entra`,
and `publish`, then the scenarios in the README's Steps 3-8. Search (S1) and
Foundry were in Sweden Central; Storage and the Flex Consumption Function were
in West Europe. Environment identities are omitted.

### Defects found and fixed during the run

- **Function indexing.** The host reported `Worker failed to index functions`.
  HTTP-trigger parameters must be named `req`; `function_app.py` was corrected
  and republished.
- **Foundry citations.** The Foundry Search tool builds citations only from
  literal `url` and `title` index fields. Both fields were added to the index
  schema and indexer mappings, and the indexer was reset and rerun.
- **Probe instructions.** Runs without a citation annotation recorded
  `citation_matches_configured_blob=false`. The probe now uses the documented
  instruction to always cite tool results. After the change, four of five runs
  matched the configured Blob; one returned no annotation. Citation output is
  model behavior, so the probe records it per run instead of assuming it.

### Scenario results

Each monitor run was requested with `HTTP 202`. Each row comes from the
`freshness_decision` evidence that run produced:

| Scenario | `review_state` | `index_state` | `overall_state` | Notified roles | Notification outcome |
|---|---|---|---|---|---|
| New revision, no review | `review_required` | `current` | `review_required` | Knowledge Owner | `accepted` |
| Owner review recorded (`HTTP 201`) | `fresh` | `current` | `fresh` | none | not sent |
| Source edited, index behind | `review_required` | `sync_pending` | `review_required` | Knowledge Owner, Control Operator | `accepted` (two outcomes) |
| Reviewed but `valid_until` passed | `review_required` | `current` | `review_required` | Knowledge Owner | `accepted` |
| Malformed `valid_until` | `cannot_evaluate` | `cannot_evaluate` | `cannot_evaluate` | Control Operator | `accepted` |
| Restored and reviewed | `fresh` | `current` | `fresh` | none | not sent |

The expired case kept the owner review as current for the ETag and failed
validity on the passed expiry date. The malformed case failed closed and did
not report `fresh`. `accepted` means the built-in inbox route stored a hashed
receipt; it does not prove that a person read it.

### Authority boundaries

| Request | Result |
|---|---|
| `POST /api/review` without a token | `HTTP 401` (Easy Auth) |
| Owner token to `POST /api/notifications` | `HTTP 403`, "Only the KNW-001 monitor identity may notify." |
| Owner review with a stale ETag | `HTTP 409`, "The source revision or policy changed; reload before reviewing." |

### Foundry observation

The probe created a versioned prompt agent with the Azure AI Search tool
against the KNW-001 index. A captured run reported `response_status:
completed`, `azure_ai_search_call` and `azure_ai_search_call_output` items,
`citation_matches_configured_blob: true`, and
`blob_etag_unchanged_during_probe: true`. Evidence stores only hashed URLs and
ETags plus service response and tool-call IDs, not the prompt or answer. This
shows what the agent retrieved; it does not show that the answer was correct
or that freshness was enforced during retrieval.

### Temporary policy and debugging resources

The subscription policy `deny-unapproved-azure-resource-types` was temporarily
extended with three types the runtime needed:
`Microsoft.CognitiveServices/accounts/projects/connections`,
`Microsoft.Web/sites/config`, and `Microsoft.Insights/components`. While
diagnosing the indexing defect, one Application Insights component and one Log
Analytics workspace were created. Both were deleted, along with the
auto-created "Application Insights Smart Detection" action group.

### Cleanup verification

```text
$ python infra/runtime.py cleanup --approve-delete
Runtime resources, Entra application and runtime role assignments removed.
$ python infra/deploy.py cleanup --approve-delete
Control resources removed; subscription policy left unchanged.
```

Follow-up checks confirmed:

- the dedicated resource group contained no resources;
- no KNW-001 Entra application remained;
- no soft-deleted Foundry account remained.

The policy allowlist was then restored from the pre-runtime snapshot to its
original 38 types; none of the three temporary types remains. The empty
resource group is left in place by design.

### Local checks after the run

- 106 KNW-001 tests pass, using the isolated command in the README.
- 23 README-structure and governance-contract repository tests pass.

## Follow-up live validation — 2026-11-08

The revised README sequence was rerun against Azure. The deployment order was
foundation, runtime deployment/configuration/publication, then Steps 3-8.
Search (S1) and Foundry were in Sweden Central; Storage and the Function App
were in West Europe. The subscription and tenant identifiers are omitted.

### Redeployment defect found and fixed

The first runtime redeployment failed with Microsoft Graph
`Request_ResourceNotFound`. Cleanup had left the deleted Entra application's
object, client, and service-principal IDs in `.azure/runtime.json`, and
deployment reused those stale values. `infra/runtime.py` now carries prior
state only when it has not been cleaned and removes those three IDs during
cleanup. The runtime redeployed and published after the fix; regression
coverage is in `tests/test_runtime.py`.

### Scenario results

Every monitor invocation returned HTTP 202. The results below are from the
live `freshness_decision` and associated inbox records:

The `knw review --confirm-reviewed` commands for Steps 4, 5, and 6 were
executed by the assistant in the signed-in owner's Azure CLI session after
the user asked the assistant to handle the run. The API accepted the token
for the configured owner, but the owner did not personally inspect and
confirm each revision. These records therefore demonstrate the authenticated
API and downstream state transitions, not a human review or approval.

| README step | Scenario | Review state | Index state | Overall state | Notified role(s) |
|---|---|---|---|---|---|
| 3 | New revision, no owner review | `review_required` | `current` | `review_required` | Knowledge Owner |
| 4 | Entra owner-authenticated attestation accepted (`HTTP 201`) | `fresh` | `current` | `fresh` | none |
| 5, first run | Source edited, index behind | `review_required` | `sync_pending` | `review_required` | Knowledge Owner, Control Operator |
| 5, after Entra owner-authenticated attestation | Current review, index still behind | `fresh` | `sync_pending` | `sync_pending` | Control Operator |
| 6, expiry decision | Past `valid_until` despite current attestation | `review_required` | `current` | `review_required` | Knowledge Owner |
| 7 | Malformed `valid_until` | `cannot_evaluate` | `cannot_evaluate` | `cannot_evaluate` | Control Operator |

The Step 5 source edit changed the Blob ETag; without a new indexer run and
accepted attestation, the policy returned `review_required` and
`sync_pending` together. The scenario-sequence test also verifies that a
metadata-only expiry edit has the same conservative effect. In Step 6, after
re-indexing and an accepted attestation, the expired date remained the sole trigger. The
malformed value failed closed. Notices returned HTTP 202 and produced hashed
inbox receipts.

The live Step 4 `fresh` record named `Control Operator` as `accountable_role`
despite having no notification recipients. The monitor now retains the
configured Knowledge Owner as accountable when no notification is routed,
and the scenario test asserts that field. This code fix was tested locally
after cleanup, not re-exercised against Azure.

### Expired-state Foundry probe

The Step 6 decision was observed, but the documented Foundry probe did not
complete. The ARM project, Search connection, and model deployment reported
`Succeeded`. The SDK probe nevertheless received `404 Project not found` on
the connection lookup. Repeating with the project path's uppercase spelling
passed that lookup but the subsequent Responses request also returned 404
`Project not found`. During the wait, a direct `agents` list request began
returning HTTP 200, but the probe still failed and no expired-state citation
was captured. The earlier `media/run-foundry-probe.png` is from a healthy-
source run and is not evidence for the expired scenario. The exact Step 6
Foundry behavior therefore remains unvalidated.

### Authority boundaries

| Request | Result |
|---|---|
| `POST /api/review` without a token | `HTTP 401` (Easy Auth) |
| Owner token to `POST /api/notifications` | `HTTP 403`, "Only the KNW-001 monitor identity may notify." |
| Owner review with a stale ETag | `HTTP 409`, "The source revision or policy changed; reload before reviewing." |

### Cleanup and retained policy

The runtime cleanup ran before foundation cleanup. The runtime removed the
Function App, plan, Foundry account, Entra app, and its role assignments; the
foundation cleanup removed Storage and Search. Follow-up inspection found an
empty resource group, zero matching Entra applications, and no soft-deleted
Foundry account. Runtime state is marked `cleaned` and no longer contains
Entra application IDs.

With the owner's approval, the subscription policy
`deny-unapproved-azure-resource-types` kept the two types added for this
rerun: `Microsoft.Web/sites/config` and
`Microsoft.CognitiveServices/accounts/projects/connections`. The allowlist
contains 40 types; the Deny effect remains enabled. No policy restoration was
performed.

### Local checks after the follow-up

- `uv run --python 3.12 --with-requirements "$CONTROL/requirements.txt" --with pytest python -m pytest "$CONTROL/tests" -q` — 109 passed.
- `.venv/bin/python -m pytest tests/test_control_readme_structure.py tests/test_governance_contract_consistency.py tests/test_knw_001_governance_contract.py -q` — 32 passed.
