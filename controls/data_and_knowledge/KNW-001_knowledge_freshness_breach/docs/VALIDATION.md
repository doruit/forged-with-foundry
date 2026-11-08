# KNW-001 validation boundary

This record is chronological. The current result is the
[third live run](#third-live-run--2026-11-08), completed with the
[Foundry route repair](#foundry-probe-route-repair) and malformed-metadata
check. The earlier attempts remain below as history.

The technical scenarios pass, including expired-source retrieval and
citation, and the documented control-owned cleanup was verified after the
latest run. Status remains **Implemented** because attestations in the latest
run were submitted through delegated automation, not personal owner review.

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
Foundry behavior was unvalidated at that point. The
[later route repair](#foundry-probe-route-repair) closes the expired-source
retrieval gap.

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

## Third live run — 2026-11-08

The README's technical scenarios ran against Azure once more after
foundation deployment and runtime deployment, configuration, and
publication. Search (S1) and Foundry were in Sweden Central; Storage and the
Function App were in West Europe. Subscription and tenant identifiers are
omitted. The run had five goals:

1. confirm on Azure that a `fresh` decision with no recipients still names
   the Knowledge Owner as accountable (the monitor fix from the follow-up);
2. have each revision read in the Azure Portal before it was attested;
3. observe a document expire by the clock alone, with its Blob ETag and
   review unchanged;
4. complete the expired-state Foundry probe that returned HTTP 404 in the
   follow-up;
5. verify cleanup (first only the temporary agents, while the owner kept the
   deployment for a while; the full control cleanup ran afterwards; see
   [Probe cleanup and control cleanup](#probe-cleanup-and-control-cleanup)).

### Review provenance

The user allowed the assistant to test the human-review steps itself, using
a browser as the reader's surface. Before each `knw review
--confirm-reviewed`, the assistant opened the blob in the Azure Portal, in
the user's already signed-in browser, and read that revision's text. It then
ran the command in the owner's Azure CLI session. The portal's ETag, quoted
as HTTP sends it, hashes (SHA-256) to the `source_etag_sha256` of the
decision that followed, so the revision it read was the revision attested.

This validates identity binding, ETag binding, the HTTP 201 record, and the
downstream decisions. It does not validate a human review: the owner did not
read and confirm these revisions personally. README Step 4 still tells the
owner to run the attestation, and the control records only that the
configured owner identity invoked the review action for that ETag.

### Scenario results

Every monitor invocation returned HTTP 202. Each row comes from the
`freshness_decision` and inbox records of that run:

| README step | Scenario | Review state | Index state | Overall state | Notified role(s) |
|---|---|---|---|---|---|
| 3 | New revision, no owner review | `review_required` | `current` | `review_required` | Knowledge Owner |
| 4 | Review accepted (`HTTP 201`) | `fresh` | `current` | `fresh` | none; `accountable_role` is Knowledge Owner |
| 5, first run | Source edited, index behind | `review_required` | `sync_pending` | `review_required` | Knowledge Owner, Control Operator |
| 5, after review | Current review, index behind | `fresh` | `sync_pending` | `sync_pending` | Control Operator |
| 6 variant, before the date | Future `valid_until`, current review | `fresh` | `current` | `fresh` | none |
| 6 variant, after the date | Same ETag and review, `valid_until` passed | `review_required` | `current` | `review_required` | Knowledge Owner |
| 7, after the repaired probe | Malformed `valid_until` | `cannot_evaluate` | `cannot_evaluate` | `cannot_evaluate` | Control Operator |

The Step 4 `fresh` record named `Knowledge Owner` as `accountable_role` with
an empty `notification_roles`. The follow-up run had shown `Control Operator`
there, so the monitor fix now holds on Azure as well as in the scenario test.

Step 5's second run was routed to the Control Operator only, because the
Knowledge Owner's review for the edited revision was current. The Step 5 edit
and the Step 6 metadata update each changed the ETag, so each needed a new
index run and a new review before the next decision.

### Expiry by the clock alone

README Step 6 sets `valid_until` to a past date. This run used a date about
nine minutes ahead instead, so the policy branch was reached by time passing
rather than by a different input. The metadata update changed the ETag
(content unchanged), so the revision was re-indexed and reviewed, and the
monitor reported `fresh`. After `valid_until` passed, with no Blob write and
no new review, the next run reported the following selected fields
(the review record ID is abbreviated):

```json
{
  "overall_state": "review_required",
  "reason": "Review: Owner review 17b0628d-… is current for the Blob ETag. Document valid-until date has passed. Index: Indexed modification time matches or exceeds the Blob time for policy knw001-v1.",
  "notification_roles": ["Knowledge Owner"],
  "accountable_role": "Knowledge Owner",
  "source_valid_until": "2026-11-08T20:17:14+00:00",
  "source_etag_sha256": "cb743cec3ac4d49d082be15fd8940c15b772c5438b3548c4dee8a53ed619f6c6",
  "timestamp": "2026-11-08T20:17:37.013966Z"
}
```

The earlier `fresh` decision for this revision carried the same
`source_etag_sha256` and `review_record_id`; only the clock changed. The
Knowledge Owner notice was accepted (HTTP 202) and produced a receipt with a
`payload_sha256`.

### Authority boundaries

| Request | Result |
|---|---|
| `POST /api/review` without a token | `HTTP 401` (Easy Auth) |
| Owner token to `POST /api/notifications` | `HTTP 403`, "Only the KNW-001 monitor identity may notify." |
| Owner review with a stale ETag | `HTTP 409`, "The source revision or policy changed; reload before reviewing." |

### Foundry lookup failures

The Foundry project was created at 19:51:38Z. ARM reported the project, the
Search connection, and the model deployment as `Succeeded` while the
some data-plane routes still returned HTTP 404. Two
bodies appeared: `Project not found`, and `ResourceNotFound` with
`Subdomain does not map to a resource.` Status codes observed, as minutes
after project creation:

| Minutes | Observation |
|---|---|
| about 4 | `connections/knw001-search` under the lowercase project name changed from 404 to 200 |
| about 24 | Six project-name spellings that had never been queried answered 200 on `agents`, `connections/knw001-search`, and `deployments`. The lowercase `agents` and `deployments` routes, polled every 30 s since about minute 1, still answered 404 |
| 27-29 | Seven probe attempts: six failed at `agents.create_version` (404). The seventh created the agent, then failed at the old per-agent Responses route (404) |
| about 35 | Lowercase `agents` and `deployments` still 404 after about 10 minutes without a request to them |
| about 42 | One probe attempt under another project-name spelling passed `connections.get` and `create_version`, then failed at the old per-agent Responses route (404). Its agent was deleted |
| about 43 | Lowercase `agents` and `deployments` still 404; the other spelling's `agents` list answered 200 |

A changed query string or `api-version` did not alter a 404. These
observations show that a 404 can persist for one project-name spelling and
route while another spelling or route of the same project answers; they do
not show why. In particular, failures on the old per-agent Responses route
are not evidence of propagation delay. No run tested the repaired route
immediately after project creation, so no readiness duration for that route
has been established.

At 20:55Z the canonical lowercase `GET agents` still returned `404 Project
not found`, while the read-only `Knw-001` spelling returned HTTP 200 with an
empty agent list. This list-route discrepancy remains unexplained. It did
not block the repaired probe: all three successful probes below used
`knw-001` exactly as supplied by `runtime.py env`, with no casing override.

### Defect found and fixed: orphaned probe agent

During the seven attempts above, the seventh created agent
`knw001-probe-a8aa4edd`. The `finally` block's delete then returned the same
404, which replaced the original error and left the agent behind. It was
removed with a REST delete under another project-name spelling (HTTP 200),
after which the agent list was empty.

`foundry_probe.py` now:

- retries HTTP 404 `Project not found` every 20 seconds
  for `--wait-minutes` (default 20; 0 tries once), using a new agent name per
  attempt, and gives up with `ProbeNotReadyError`;
- retries the delete for up to 300 seconds, and if it still fails raises
  `AgentCleanupError` naming the agent, after the evidence has been written;
- does not retry `Subdomain does not map to a resource` or other errors;
  that message accompanied the wrong invocation route in this environment;
- rejects non-finite or negative wait budgets before contacting services,
  and keeps stdout to one JSON line (progress goes to stderr).

The cleanup retry reports an unresolved agent rather than claiming success.
The tests cover retry exhaustion, cleanup failure, the exact SDK request
route and agent version, non-retryable errors, and invalid wait budgets.

### Foundry probe route repair

The installed versions were `azure-ai-projects 2.3.0`, `openai 2.54.0`,
and `azure-identity 1.27.0`. In this environment,
`get_openai_client(agent_name=agent.name)` sent Responses requests to
`/api/projects/knw-001/agents/<agent-name>/endpoint/protocols/openai/responses`.
Agent creation succeeded, but that invocation returned HTTP 404
`ResourceNotFound: Subdomain does not map to a resource.`

The [official SDK 2.3.0 Search-tool sample](https://github.com/Azure/azure-sdk-for-python/blob/azure-ai-projects_2.3.0/sdk/ai/azure-ai-projects/samples/agents/tools/sample_agent_ai_search.py)
uses `get_openai_client()` and an `extra_body.agent_reference` instead.
The probe now follows that project-level `/openai/v1/responses` route and
also pins the reference to the version it just created. The request keeps
`tool_choice="required"`, `max_tool_calls=1`, `max_output_tokens=256`, and
`store=False`. A real-SDK `httpx.MockTransport` test checks the URL and body.

This diagnosis concerns the current deployment and installed SDK. The first
committed probe also used the per-agent client, and the initial validation
record contains a successful healthy-source run. That run did not record its
exact resolved SDK/service revision; its success is not reinterpreted as a
failure or used to claim that the old route never worked.

Three consecutive repaired probes completed against the unchanged,
already-expired source. All used the canonical lowercase endpoint from
`runtime.py env`; none used a casing workaround or a longer retry budget.
The first two used `--wait-minutes 0`; the third used the README command
`knwpy "$CONTROL/foundry_probe.py"` with its default budget and needed no
retry. The third run loaded the same `knw env` assignments without executing
the emitted shell text.

| UTC observation time | Correlation ID | Response | Matching Blob citation |
|---|---|---|---|
| 20:40:28.314388 | `cddde8be-00c0-4e42-a5a4-0bbae4a42b5f` | `completed` | `false` (no citation annotation) |
| 20:40:58.896770 | `5d4ac4fc-5aa9-4f74-8cb5-acac05ad461f` | `completed` | `true` |
| 20:54:45.108189 | `cf5979ca-c00e-41fc-a081-8bfef2b1217c` | `completed` | `false` (no citation annotation) |

Each response contained `azure_ai_search_call`, `azure_ai_search_call_output`,
and `message` items. Each observation was written to the evidence container
and reported `blob_etag_unchanged_during_probe: true`. The shared ETag digest
was `cb743cec3ac4d49d082be15fd8940c15b772c5438b3548c4dee8a53ed619f6c6`.
The no-citation outcomes are retained, not counted as matching citations.

Selected fields from the matching-citation observation:

```json
{
  "control_id": "KNW-001",
  "policy_version": "knw001-v1",
  "event_type": "foundry_agent_observation",
  "correlation_id": "5d4ac4fc-5aa9-4f74-8cb5-acac05ad461f",
  "timestamp": "2026-11-08T20:40:58.896770Z",
  "response_id": "resp_012f934c407c13a1016af0de58e230819594a45b024416fe49",
  "response_status": "completed",
  "search_call_ids": [
    "fc_012f934c407c13a1016af0de597a508195a0b0ce15a387238e",
    "fco_012f934c407c13a1016af0de59bda8819590916df3d8bdc2fd"
  ],
  "citation_matches_configured_blob": true,
  "source_etag_sha256": "cb743cec3ac4d49d082be15fd8940c15b772c5438b3548c4dee8a53ed619f6c6",
  "blob_etag_unchanged_during_probe": true
}
```

The live monitor invocation at 20:40:57Z returned HTTP 202. Its decision
`97e7e61b-8fc0-484b-b9f5-40a3414f59f5` carried the same ETag digest, with
`review_state: review_required`, `index_state: current`, and
`overall_state: review_required`. Its reason identified the passed
`valid_until` despite the current attestation. The Knowledge Owner notice
returned HTTP 202 and produced a hashed receipt under that correlation ID.
No new attestation was submitted for these probe checks.

This demonstrates expired-source retrieval and a matching citation alongside
the expiry decision. It does not prove exact indexed-text parity, answer
accuracy, or personally performed review.

### Malformed metadata and final boundary checks

After the repaired probe, the documented Step 7 metadata command set
`valid_until=next-quarter`. The monitor returned HTTP 202 and produced this
decision (selected fields):

```json
{
  "event_type": "freshness_decision",
  "correlation_id": "732b7b9e-c605-47eb-8646-cb7b2e5313da",
  "timestamp": "2026-11-08T20:55:09.485564Z",
  "decision": {
    "index_state": "cannot_evaluate",
    "overall_state": "cannot_evaluate",
    "reason": "Document valid-until metadata is malformed.",
    "review_state": "cannot_evaluate"
  },
  "notification_roles": ["Control Operator"],
  "accountable_role": "Control Operator"
}
```

The associated `notification_outcome` was `accepted` with HTTP 202; its
`notification_receipt` had payload digest
`b22293ab7b34bea5dfe0317d10013de92ae1348ce3784479d804fbedd6a4edd1`.
Step 8 was then repeated:

```text
HTTP 401
Only the KNW-001 monitor identity may notify. HTTP 403
The source revision or policy changed; reload before reviewing. HTTP 409
```

These are captured results, not expected-output fixtures. No successful
review was submitted by these negative checks.

### Probe cleanup and control cleanup

Each repaired probe completed its delete operation. The read-only agent
listing described above returned HTTP 200 and zero agents. The previous
long-running retry process was stopped, and no probe process remains.
Subscription policy and permissions were not changed during the route repair.

At the end of the run the source was still revision 2 with the deliberately
malformed `valid_until=next-quarter` from the Step 7 check. The successful
expiry and probe records came before that metadata edit and refer to the
earlier ETag.

The documented cleanup was then run on 2026-11-08, after the owner approved
it:

```text
$ knw cleanup --approve-delete                      # 21:12:16Z-21:14:15Z
Runtime resources, Entra application and runtime role assignments removed.
$ deploy.py cleanup --approve-delete                # 21:14:51Z-21:15:04Z
Control resources removed; subscription policy left unchanged.
```

Both commands exited with code 0. Both `cleanup-plan` actions were run first
and listed only KNW-001 resources. The README verification step then
returned:

- `az resource list -g rg-knw001-demo`: an empty table;
- the control's Entra application lookup: `0`;
- `az cognitiveservices account list-deleted` filtered on `knw001`: no
  output, so the Foundry account was purged;
- role assignments scoped to `rg-knw001-demo`: `0`.

The local runtime and foundation state files both record phase `cleaned`.
The empty resource group and its deployment history remain, as documented.

At the owner's request, the subscription policy
`deny-unapproved-azure-resource-types` keeps the two types added for this
control: `Microsoft.Web/sites/config` and
`Microsoft.CognitiveServices/accounts/projects/connections`. The control
cleanup does not change subscription policy.

### Local checks after the route repair

- `uv run --python 3.12 --with-requirements "$CONTROL/requirements.txt" --with pytest python -m pytest "$CONTROL/tests" -q` — 124 passed.
- `foundry_probe.py --help` — passed; documents the bounded project-lookup retry.
- `.venv/bin/python -m pytest tests/test_control_readme_structure.py tests/test_governance_contract_consistency.py tests/test_knw_001_governance_contract.py -q` — 32 passed.
- `.venv/bin/python scripts/generate_roadmap.py` — passed; 161 controls,
  15 implemented; generated content unchanged.
