# KNW-001 - Knowledge freshness breach assessment

## Candidate

- **Control ID:** KNW-001
- **Name:** Knowledge freshness breach
- **Lifecycle phase:** Live
- **Accountable role:** Knowledge Owner, represented by a configured Data Owner for the synthetic Blob source.

## Governance problem

- **Risk:** An instruction may remain available after its owner review is overdue or its explicit `valid_until` date has passed; separately, Azure AI Search may lag behind the source.
- **Control objective:** Determine document validity from an ETag-bound owner review, the maximum review age, and optional Blob metadata `valid_until`; separately report whether Search reflects the latest Blob modification. A real Foundry knowledge agent is an observed consumer, not the freshness decision-maker.
- **Authoritative signals:** Blob properties provide source ETag and `Last-Modified`; optional Blob metadata `valid_until` provides the owner's explicit expiry instant in timezone-aware RFC 3339 format. A Data Owner review attestation records the ETag and policy version reviewed, with authenticated actor and server-created time. Azure AI Search provides indexed `metadata_storage_last_modified` and indexer execution status. Blob ETag can change after content or metadata edits; `Last-Modified` is not proof of review.
- **Required decision:** One per-source report with document `review_state` (`fresh`, `review_required`, or `cannot_evaluate`) and separate `index_state` (`current`, `sync_pending`, or `cannot_evaluate`). Expired `valid_until` is `review_required` even if review and index are otherwise current. Index lag is not a document-validity breach.
- **Required governance action:** Notify the Data Owner for overdue review, changed ETag, or passed `valid_until`; route `sync_pending` and `cannot_evaluate` to the operator. This notifies but does not remove a document from Search or block retrieval. Neither notification authorizes modifying content or index configuration.
- **Required evidence:** Control/policy version, correlation ID, safe Blob reference, ETag digest, source `valid_until`, attestation reference/actor/time, review age, Blob and indexed timestamps, indexer result, separate document/index states and reasons, accountable role, and notification attempt/acceptance. Exclude document content, review notes, workflow URLs, and access tokens.

## Enforcement classification

- **Deterministic policy:** Yes. Compare configured Blob identity/current ETag, optional `valid_until`, latest eligible review record, actor and recorded time, maximum review age, and the Search index's per-document indexed modification time against Blob `Last-Modified`.
- **Model-assisted evaluation:** No. A model cannot establish owner review or index synchronization.
- **Human approval:** The Data Owner explicitly records a review. This is not approval for an agent action.
- **Configuration assessment:** Yes. Blob scope, owner identity, maximum review age, Search index/indexer, attestation storage, and schedule are explicit. Missing, empty, invalid, or ambiguous values cannot produce a healthy result.
- **Monitoring/detection:** A Python Azure Functions Timer Trigger reads Blob/review state and Search index state on a documented schedule.
- **Required fail-closed behavior:** Missing/invalid policy, ETag, present-but-malformed `valid_until`, attestation, actor, timestamp, Search document/field, permission, or service response cannot produce `fresh`. Use `review_required` for an overdue review, changed ETag, or passed expiry; use `cannot_evaluate` for unavailable/malformed facts and `sync_pending` for confirmed index lag.
- **Model/Foundry role:** **Monitored workload.** A temporary Foundry Prompt Agent uses the built-in Azure AI Search tool against the same index the monitor observes. The repaired project-level Responses path retrieved and cited an expired source on 2026-11-08, with the Blob ETag unchanged and matching the expiry decision. The probe records response/tool identifiers, citation digests, and the Blob ETag before/after the call; the citation itself does not identify an indexed revision. Agent prose is not proof of freshness. This remains asynchronous source monitoring, not an inline retrieval gate; no ACS intervention point is introduced.

## Existing capability review

| Capability | Applicable? | What it already provides | Role in the core demo or reason not used |
|---|---:|---|---|
| Microsoft Agent Governance Toolkit | No | Governance capabilities for agent behavior | This is not agent behavior. |
| Agent Control Specification | No | Runtime intervention points and tool-call governance | No model/agent action is governed. |
| Microsoft Foundry | Yes, for the monitored workload | Versioned Prompt Agent, model execution, built-in Azure AI Search tool, and citation annotations | `foundry_probe.py` uses the project-level Responses API with an explicit agent name/version reference and records minimized service IDs. The local index schema declares a vector field/profile but the Blob indexer does not populate vectors and the probe uses `simple` queries. Live runs showed keyword-only retrieval of healthy and expired sources with the project's Search roles. Citations require literal `url`/`title` index fields and are not returned on every run. The current route follows the official SDK 2.3.0 sample; see the [route repair](docs/VALIDATION.md#foundry-probe-route-repair). No second freshness evaluator or explanatory agent is needed. |
| Foundry Control Plane | No | Foundry control-plane management | No Foundry resource/configuration is managed. |
| Azure API Management AI Gateway | No | Gateway controls for model traffic | No model traffic exists. |
| Microsoft Purview | No for primary decision | Labels and data-governance capabilities | Labels do not establish that an owner reviewed the current Blob version. |
| Microsoft Defender | No | Security posture and threat detections | No threat signal is part of this decision. |
| Microsoft Entra | Yes | Managed identity and Azure RBAC | The Function's managed identity holds Storage Blob Data Owner, Search Index Data Reader, and Search Service Contributor; Easy Auth admits only the Data Owner and the Function identity. Free-tier Search cannot use its own managed identity to read the Blob indexer source; planned ingestion uses a short-lived container user-delegation SAS. The deployed setup user has resource-scoped Storage Blob Data Contributor (including delegation-key generation), Search Service Contributor, and Search Index Data Reader. Owner writes go through the authenticated review action, not direct review-container access. |
| Azure AI Content Safety / Language | No | Content and language analysis | The control does not inspect or judge content. |
| Azure Monitor / Application Insights / OTel | Optional | Function logs, failures, latency, and correlation diagnostics | Not deployed by the core path. One instance was created temporarily to diagnose a Function indexing defect and then deleted. Never a second decision/evidence authority. |
| Azure Blob Storage | Yes | Synthetic source, ETag, Last-Modified, Entra-protected data access | Authoritative source state. Bind review records to ETag; metadata/property changes conservatively invalidate review. |
| Azure AI Search | Yes | Blob indexer, incremental change detection, searchable metadata, and run status/history | Temporary S1 is deployed in Sweden Central; Storage remains in West Europe. Cross-region Blob ingestion, the index/indexer, and `sync_pending` detection were validated on 2026-11-08. The local helper uses a short-lived user-delegation SAS. Indexer success alone is not per-document proof. |
| Azure Functions | Yes | Python timer-triggered execution | Scheduled monitor; requires host storage. Reads and evaluates state, then sends notifications. |
| Configurable HTTPS notification sink | Yes | Authenticated endpoint for minimized role-directed notifications | Core transport contract; verify endpoint audience, recipient routing, and acceptance. HTTP 2xx is acceptance, not proof of final delivery. Power Automate/Teams is one optional receiver. |
| Microsoft Graph / SharePoint | No | SharePoint/OneDrive APIs | This alternative uses Blob and does not depend on SharePoint licensing. |
| Power Automate Approvals | No | Approval tasks and response workflows | This action is a review request, not approval for a consequential action. |

The connected tenant currently has no Microsoft 365 license, so Teams delivery
cannot be validated there. Teams is optional; the core path uses a configurable
authenticated HTTPS sink and does not claim delivery from a successful HTTP
response or the local preview.

## Existing samples and implementations

| Repository, documentation, or sample | Overlap | What is still missing |
|---|---|---|
| [Azure Blob Indexer](https://learn.microsoft.com/en-us/azure/search/search-how-to-index-azure-blob-storage) | Incrementally indexes Blob content and metadata, including `metadata_storage_last_modified` when declared. | Owner-review-age policy and separation of review age from index lag. |
| [Azure AI Search managed identities](https://learn.microsoft.com/en-us/azure/search/search-how-to-managed-identities) | Documents the Basic-tier minimum for Search's managed identity to connect to Blob. | Free-tier indexing uses a scoped user-delegation SAS; its expiry/renewal and secret handling must be documented. |
| [User-delegation SAS with Azure CLI](https://learn.microsoft.com/en-us/azure/storage/blobs/storage-blob-user-delegation-sas-create-cli) | Supports read/list SAS for a container, signed with Entra credentials; maximum validity is seven days. | Create and renew the indexer credential without account keys, logs, or source-control exposure. |
| [Get Blob Properties](https://learn.microsoft.com/en-us/rest/api/storageservices/get-blob-properties) | Returns ETag and Last-Modified; Last-Modified changes for content, metadata, and property changes. | Human review evidence bound to current Blob state. |
| [Azure AI Search Get Indexer Status](https://learn.microsoft.com/en-us/rest/api/searchservice/indexers/get-status?view=rest-searchservice-2026-04-01) | Returns indexer state and execution history. | Run-level status does not prove a specific document's indexed metadata matches the current Blob. |
| [Azure AI Search RBAC](https://learn.microsoft.com/en-us/azure/search/search-security-rbac) | Supports Entra data-plane roles on any tier when RBAC is enabled. | KNW-001 role assignment and a tested Function query. |
| [Azure Functions Timer Trigger](https://learn.microsoft.com/en-us/azure/azure-functions/functions-bindings-timer?tabs=python-v2) | Scheduled Python execution. | Control-specific policy, evidence, Blob/Search comparison, and notifications. |
| [Power Automate OAuth HTTP triggers](https://learn.microsoft.com/en-us/power-automate/oauth-authentication?tabs=classic-designer) | Authenticated HTTP trigger and required claims. | Optional receiver; verify the Function identity and message receipt if selected. |
| [Microsoft Teams connector](https://learn.microsoft.com/en-us/connectors/teams/) | Adaptive cards in chat or channel. | Optional receiver; KNW-001 payload, routing, privacy filtering, and live receipt verification. |
| QLT-001 `demo.py:card` / `notify` and `docs/TEAMS-DELIVERY.md` | Minimized Teams cards, role routes, delivery-state conventions. | Scheduled Blob/Search monitoring; existing sender uses Azure CLI identity. |
| AUT-002 `src/aut_002/teams.py` | Candidate managed-identity-to-Flow token pattern. | KNW-001 live validation of claims, audience, tenant allow-list, license, and receipt. |
| PRI-002 `src/pri_002/storage.py` | Blob SDK and `DefaultAzureCredential` patterns. | Read-only monitoring plus a version-bound owner review. |
| DAT-PRE-002 `evaluate_classification` and tests | Pure policy and unavailable-evidence handling. | Review-age and Search-index state decision. |
| QLT-001 remediation guidance | Identifies stale source as a possible groundedness cause, but does not implement freshness monitoring. | Independent owner-review and Search synchronization states. |

## Repository overlap

- **Related controls:** KNW-PRE-001 owner assignment; KNW-PRE-002 source precedence; CHG-003 source change without validation; KNW-002 unanswered rate; KNW-003 source conflict; KNW-004 retrieval relevance; QLT-001 groundedness.
- **Existing components to reuse:** PRI-002 Blob SDK/identity patterns; DAT-PRE-002 deterministic policy tests; QLT-001/VAL-001 Teams cards; AUT-002 managed-identity-to-Flow pattern as a candidate; repository Bicep/deployment/cleanup conventions.
- **Duplication risk:** High if reduced to indexer status or groundedness. Keep owner review bound to Blob ETag and Search sync as a separate component of one overall decision. Indexer activity alone is not per-document proof.
- **Category architecture:** No `controls/data_and_knowledge/ARCHITECTURE.md` exists at assessment time; recheck before implementation.

## Proposed contribution

- **Classification:** `IMPLEMENT_GAP`
- **Demo format:** `DEPLOYABLE_DEMO`
- **Deployment:** Required for the core learning outcome.
- **Capabilities reused:** Blob Storage source; Free Azure AI Search Blob Indexer; a Foundry prompt agent with its built-in Azure AI Search tool; Entra-authenticated project connection; Azure Functions Timer Trigger; Application Insights; Power Automate Teams Workflows / Teams connector once licensed.
- **Visible roles:** Inspect the registered Foundry agent/tool configuration and real retrieval/citation evidence alongside Blob ETag/Last-Modified, review attestation, Search indexed metadata, indexer execution result, Function decision, and (after licensing) workflow run and Teams card.
- **Minimum custom work:** Pure policy, Blob/Search metadata adapter, owner review-attestation action/store, scheduled orchestration, minimized evidence, notification deduplication only if necessary, scoped deployment/cleanup, and a deployment-time short-lived SAS configurator.
- **Unique learning outcome:** Distinguish substantive owner review from Blob modification time and Search indexing lag; bind review to the exact Blob ETag. Show that a real agent citing an indexed source does not establish that its owner review or index synchronization is current.
- **Why a separate demo:** The indexer does not implement owner-review policy. This operationalizes a Knowledge Owner process QLT-001 leaves out of groundedness measurement without duplicating CHG-003.
- **Why deployment is justified:** A local walkthrough cannot demonstrate real Blob state, managed-identity Blob/Search access, actual indexer behavior, scheduled monitoring, or a live authenticated notification receiver. Teams is optional and license-gated.

## Smallest useful design

- **Primary governance decision:** Can this source be considered fresh for retrieval under owner-review policy, and is the current source modification visible in Search?
- **Authoritative human/system:** Data Owner records a substantive review through an Entra-authenticated action. Blob supplies source ETag/Last-Modified; Search supplies indexed metadata and indexer status; deterministic code decides.
- **Signal source:** One synthetic Blob, maximum review age, optional Blob `valid_until` metadata, ETag-bound attestation, one Blob Indexer, and a declared Search `metadata_storage_last_modified` field.
- **Decision surface:** One control-local deterministic evaluator called by an Azure Functions timer.
- **Evidence source:** Blob properties, review-attestation store, Search document/indexer state, and one minimized Function decision record. Power Automate run/message receipt verifies delivery when licensed; Application Insights is operational only.
- **ACS / AGT:** Not applicable; no agent behavior is governed.
- **Foundry/Azure services:** One Foundry prompt agent/model/project connection, Blob Storage, Free Azure AI Search, Azure Functions, managed identity, host Storage Account, and Application Insights. Reuse a suitable existing Foundry account/model only after verifying ownership, compatibility, and cost scope; keep the agent and connection control-owned. Add a Table only if attestation or deduplication needs it and its trust/cleanup role is justified.
- **Governance action:** Send `review_required` to the Data Owner and `sync_pending`/`cannot_evaluate` to the operator through the configured HTTPS sink. A Teams card is an optional presentation. No automatic content or index changes.
- **Evidence artifact:** Policy/control version, correlation, safe source reference, ETag digest, review actor/time, source/indexed timestamps, indexer outcome, state/reason, accountable role, and notification receipt. No content, review notes, or webhook URL.
- **Healthy:** Recent review binds to current ETag, optional `valid_until` is absent or in the future, and indexed timestamp matches Blob modification; overall `fresh`.
- **Triggering:** Review age expired, ETag changed, or `valid_until` passed gives `review_required`; valid document but stale indexed timestamp gives `sync_pending`.
- **Unavailable/ambiguous:** Missing/invalid review or policy, wrong reviewer, malformed/future time, malformed `valid_until`, Blob/Search failure, missing document/field, or indexer error gives `cannot_evaluate` for the affected state; never report overall fresh.

## Complexity budget

- **Why custom components are necessary:** Blob/Search expose state, not this owner-review/expiry decision; Functions schedules but does not decide; a notification receiver delivers but does not determine freshness.
- **Core artifacts:** Assessment/README, Function, Blob/Search adapters, policy/evidence and review action, tests, deployment/cleanup. Only use packages actually required. Configure Search objects via Entra Search Service Contributor, not admin keys. Keep the expiring SAS and notification credentials out of source control and logs.
- **Omitted:** Chainlit, a second explanatory agent, a custom retrieval engine, ACS inline enforcement, APIM, SharePoint, Graph, automatic source editing, and a database unless a small Table is proven necessary for attestation or deduplication.
- **Single authority:** Derive review from Blob state plus attestation; derive index state from actual indexed document plus indexer status. Record both in one decision result; Application Insights is not a shadow decision store.
- **Metadata/configuration cases:** Missing/empty/invalid/valid Blob path, policy, owner, attestation, Search index, or fields. Missing index metadata is `cannot_evaluate`. Test content and metadata ETag changes, Blob/Search failures, and SAS creation, expiry, failure, and renewal. The user-delegation SAS is read/list-only, container-scoped, expires within seven days, and must be renewed to keep indexing running.
- **Local Teams preview:** Static `teams-preview.html` with synthetic card scenarios for layout only. It sends no message, makes no decision, and is not delivery evidence.

## Community fit

- **Learning level:** Intermediate
- **Estimated time:** Allow 90-120 minutes for provisioning and scenarios; about 5 minutes for local checks. Service errors may extend this. The earlier 404 attempts used a different invocation route and do not establish a required propagation delay for the repaired probe.
- **Prerequisites:** Azure subscription/resource group; Search capacity and quota (validated with S1 in Sweden Central after West Europe had none); `gpt-4.1-mini` quota in Sweden Central; synthetic Blob; Data Owner Entra identity; role-assignment and app-registration access. The built-in Entra-protected inbox is the default notification endpoint. A licensed Teams/Power Automate tenant is needed only if Teams is selected.
- **Simplifications:** One synthetic Blob, one owner, one policy, one Search index. `valid_until` is explicit Blob metadata; absence means there is no declared expiry in this demo. Attestation records that the configured identity invoked review for an ETag, not that review was adequate or resistant to privileged administrators. Expiry triggers notification only: the document remains searchable, and the monitored Foundry agent has no retrieval-time expiry filter. Indexed timestamps do not prove exact text parity.
- **Further exploration:** Multiple source types/cadences, full-corpus monitoring, exact source/index content hashes, immutable evidence, and organization-wide escalation.

## Scope boundary

- **Included in the validated demo:** One Foundry knowledge agent consuming the monitored Search index, scheduled Blob review/expiry checks, ETag-bound attestation, Azure AI Search Blob Indexer, separate document-validity/index states, fail-closed evaluation, a configurable notification sink (Teams optional), local simulated card preview, minimized evidence, and control-scoped cleanup. A built-in authenticated inbox route is the default notification sink.
- **Excluded:** Legal/factual correctness, proof the owner read every passage, universal age values, byte-for-byte source/index equivalence, automatic content changes, and production-wide coverage.
- **What it proves:** Blob state, owner-review/expiry validity for the Blob ETag, Search's observed per-document modification metadata, and the deterministic combined result. A live sink response proves acceptance only; prove final delivery separately when the receiver exposes a receipt. The local preview proves only card presentation.
- **What it does not prove:** Review quality, content accuracy/completeness, inventory coverage, exact indexed text, automatic removal or blocking of expired documents, that a recipient read/responded, or legal compliance.
- **Agent non-claims:** A citation or confident answer does not prove freshness or factual correctness. Monitoring does not prevent the agent from retrieving a stale source. The agent cannot create its own owner attestation, override policy, modify source content, or mark its response as authoritative governance evidence.
- **Safe within boundary:** Yes if missing/ambiguous facts cannot return `fresh`, review breach and index lag remain distinct, and the preview is separate from delivery evidence.

## Decision

- **Classification:** `IMPLEMENT_GAP`
- **Demo format:** `DEPLOYABLE_DEMO`
- **Deployment:** Required for core Blob/Search monitoring; an authenticated notification endpoint is required to validate the governance action. A licensed Teams environment is optional.
- **Proceed / revise / reject:** Implemented. Live technical scenarios, review provenance, and verified control-owned cleanup are recorded in [VALIDATION.md](docs/VALIDATION.md); no personally performed owner review is claimed.
- **Rationale:** Blob and Search provide the Azure-native source/index path, but not the owner-review/expiry decision. Search supports managed-identity Entra RBAC for queries; the selected tier and data-source authentication must be validated before deployment. Use only a short-lived user-delegation SAS if required by the chosen indexer path. Teams cards are optional.
- **Review date:** 2026-11-08
- **Authoritative references:**
  - [Azure AI Search Blob Indexer](https://learn.microsoft.com/en-us/azure/search/search-how-to-index-azure-blob-storage)
  - [Azure AI Search limits and Free-tier indexer limits](https://learn.microsoft.com/en-us/azure/search/search-limits-quotas-capacity)
  - [Azure AI Search managed identity and tier requirements](https://learn.microsoft.com/en-us/azure/search/search-how-to-managed-identities)
  - [Azure AI Search RBAC](https://learn.microsoft.com/en-us/azure/search/search-security-rbac)
  - [Foundry agent Azure AI Search tool and official SDK sample](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/ai-search)
  - [User-delegation SAS using Azure CLI](https://learn.microsoft.com/en-us/azure/storage/blobs/storage-blob-user-delegation-sas-create-cli)
  - [Get Blob Properties](https://learn.microsoft.com/en-us/rest/api/storageservices/get-blob-properties)
  - [Azure Functions Timer Trigger](https://learn.microsoft.com/en-us/azure/azure-functions/functions-bindings-timer?tabs=python-v2)
  - [Power Automate OAuth authentication](https://learn.microsoft.com/en-us/power-automate/oauth-authentication?tabs=classic-designer)
  - [Microsoft Teams connector](https://learn.microsoft.com/en-us/connectors/teams/)
  - [QLT-001 remediation guidance](../../grounding_and_quality/QLT-001_hallucination_rate_high/docs/REMEDIATION-GUIDANCE.md)

## Integration gates before runtime implementation

1. Verify the review action binds to the current Blob ETag and derives the actor from the Entra token; document that the Data Owner and subscription administrators remain privileged.
2. Use the authorized temporary S1 in Sweden Central; West Europe lacked capacity. Validate the cross-region Blob ingestion and chosen identity/credential path. Verify SAS expiry and secret handling if SAS is used.
3. Deploy a disposable Blob/Search spike. Confirm the Blob indexer exposes `metadata_storage_last_modified`; test source content/property changes, lag, and indexer failures.
4. Confirm the Data Owner's review permissions, Function/Search/Blob roles, resource region, and cost envelope before provisioning additional runtime or model resources.
5. Prove the authenticated notification endpoint accepts the Function identity and routes each decision to its intended role. A 2xx response proves acceptance only. If Teams is selected, additionally verify the workflow run and message receipt in a licensed tenant.
6. Verify preview is offline-only, define alert deduplication, and verify cleanup removes only KNW-001 resources and grants.

The original foundation deployment was approved for the dedicated
`rg-knw001-demo` resource group in West Europe, using Free Search and LRS
Storage. That approval did not include a paid tier or Foundry model spend.
Teams is an optional receiver; the local Teams preview is not delivery evidence.

## Azure preflight history — 2026-11-06

The resource group currently contains only its tagged Storage account. The
subscription's Free Search quota is already consumed elsewhere. An S1 ARM
preflight succeeded, but provisioning failed with `ResourcesForSkuUnavailable`
in West Europe. No Search service was created, and no alternate region or tier
was selected. Search quota/capacity and a temporary S1 budget window remain
deployment blockers.

## Sweden Central deployment — 2026-11-08

The user authorized Sweden Central for the temporary S1 service. ARM validation
and deployment succeeded. Read-only inspection confirmed S1 (`standard`), one
replica, one partition, disabled local authentication, and KNW-001 ownership
tags. Storage and the resource group remain in West Europe. The Search-only
cleanup plan was exercised, but deletion was not performed. At that point
cross-region ingestion and the full runtime/Foundry path were not yet
validated; the runtime validation record below closes both.

## Progress and authorization record — 2026-10-27

- The pure evaluator and deployment guardrail tests pass locally. The preview
  is captured and checked at desktop/mobile sizes; it remains a presentation
  mock, not a notification or decision source.
- Subscription-level ARM validation initially returned
  `RequestDisallowedByPolicy`. The owner explicitly approved extending the
  strict allowlist for Search, Blob-service configuration, Function
  configuration, Application Insights, and Log Analytics. All existing
  entries and the active `Deny` rule were preserved; no exemption was created.
  This type allowance does not establish billing eligibility or a spending cap.
- The documented foundation deployment subsequently succeeded: Free Search
  and LRS Storage in the dedicated resource group. Account keys, Blob anonymous
  access, and Search API-key authentication are disabled. The empty containers
  reserve the source/review/evidence/deployment locations but provide no runtime
  capability by themselves. See [captured output](docs/VALIDATION.md).
- The selected Data Owner was resolved and single-tenant secretless Easy Auth
  setup was approved. No app registration, service principal, owner grant,
  Function, or authenticated review action has been created yet. Environment
  identities are intentionally excluded from tracked documentation.
- Indexer/SAS integration, authenticated attestations, scheduled monitoring,
  safe runtime evidence, and live notification outcome remain open gates. The cleanup
  plan was exercised; destructive cleanup still needs separate approval and
  real verification. These gates were closed by the 2026-11-08 runtime run below.

## Foundry agent addition assessment — 2026-10-27

The requested agent is a real knowledge consumer, not a narrator attached for
branding. Contribution classification remains `IMPLEMENT_GAP`: Foundry supplies
the agent/retrieval capability, while the review-age policy remains the small
custom gap. The demo remains `DEPLOYABLE_DEMO` with one authoritative freshness
evaluator. This revision supersedes the earlier decision to omit Foundry.

### Smallest agent path

1. Register one control-owned prompt agent using the official
   `PromptAgentDefinition` / `AzureAISearchTool` path documented by Microsoft.
   Connect it to the same index used by KNW-001 through an Entra-authenticated
   project connection. Prefer a simple keyword query for the one-document
   scenario; verify that configuration against the real tool and Free Search
   before claiming compatibility. Do not silently add embeddings, a paid
   Search SKU, a toolbox/MCP layer, or another retrieval service.
2. Ask the same synthetic question in controlled scenarios: current review and
   index; overdue review with a current index; changed source with a lagging
   index; unavailable evidence. Inspect real tool execution and citation
   annotations, not only generated answer text. An answer need not change when
   only review age changes; the governance decision should.
3. Keep the freshness check independent of the model. Compare source/index
   observations with the owner's ETag-bound attestation and policy; route the
   resulting governance action through the existing planned notification path.
   No stale-source blocking or model-granted approvals are introduced.

### Verification and permission gates

- Confirm the selected SDK/API/model support status, region, installed types,
  and real Search tool behavior before deployment. The local index schema
  declares a vector field/profile, but the indexer doesn't populate vectors;
  validate that the Foundry tool accepts this keyword-only composition before
  claiming it works.
- Identify exactly which Foundry managed identity performs the Search call.
  The current article requests Search Service Contributor and Search Index
  Data Contributor and uses account/project identity wording in different
  sections. Verify the actual principal and necessary permissions; do not
  describe this configuration as read-only or silently grant those roles.
  Preserve disabled API-key authentication; stop rather than enable keys.
- Verify the Responses API honors `store=false` for the selected Foundry
  endpoint and model. Keep the synthetic question/content boundary until
  service-side response retention is confirmed.
- Confirm a model-call spend allowance and separately approve any new role
  grants, Foundry resources/connections, or additional strict-policy allowlist
  changes. Earlier approval for Free Search/Storage/Functions is not blanket
  approval for model spend or Foundry permissions.
- Bound each scenario's observation window with UTC start/end times. Track
  every attempted request using a correlation identity and service-issued
  response/tool identifiers where available. Deduplicate observations by those
  identifiers; account for failed/missing runs rather than selecting only
  successful answers. Missing tool/citation/source-binding evidence makes the
  agent observation unverified, never a successful retrieval claim.
- Correlate cited source identity with independently queried index metadata;
  a URL citation alone does not identify a Blob ETag. Recheck source state
  around the observation and reject ambiguous revisions. Store only minimized
  identifiers/timestamps/digests, not full prompts, answers, tokens, or content.
- Extend cleanup to the exact control-owned agent/version, project connection,
  any new model deployment, and scoped grants. Never delete a reused Foundry
  account/project/model or remove another control's grants. Exercise cleanup
  only after separate destructive-action approval.

The Foundry path was deployed and exercised on 2026-11-08. See the runtime
validation record below.

## Initial runtime validation record — 2026-11-08

- **Status:** Implemented. The initial end-to-end run validated the foundation,
  runtime, Entra configuration, the documented decision scenarios,
  authority-boundary checks, a healthy-source Foundry probe, and cleanup.
  The follow-up run confirmed decision outcomes and cleanup, but the
  assistant submitted owner attestations through the signed-in owner's
  session, so it did not validate a human review. The expired-state Foundry
  probe initially returned HTTP 404; the later route repair completed that
  observation on the unchanged lowercase project endpoint. The control
  remains Implemented because review mechanics were tested through delegated
  automation. The documented control-owned cleanup was run and verified
  after that run.
  Results are in
  [VALIDATION.md](docs/VALIDATION.md).
- **Integration gates closed:**
  - the review action binds to the current ETag and returns `409` for a stale ETag;
  - cross-region ingestion and `sync_pending` were observed;
  - the Function identity's roles were exercised;
  - inbox acceptance was recorded per role;
  - cleanup removed only KNW-001 resources, the Entra app, and its grants.
- **Foundry role:** The agent is the monitored workload. It never decides
  freshness. The probe records which source it retrieved and cited,
  correlated with the evaluator's ETag. Citation annotations are
  nondeterministic: with the documented always-cite instruction, four of five
  runs matched the configured Blob during the initial healthy-source run.
  Those initial runs are not expired-source evidence. The later route-repair
  run recorded a matching citation in one of three completed probes of the
  expired guide, retaining the two no-citation outcomes as well.
- **Policy exception:** Three resource types were temporarily added to the
  subscription allowlist and then removed again, restoring the original 38.
- **Follow-up policy change:** With owner approval, the 2026-11-08 rerun added
  `Microsoft.Web/sites/config` and
  `Microsoft.CognitiveServices/accounts/projects/connections`. The owner asked
  to keep both types; the allowlist now contains 40 entries.
- **As built, compared with the design above:** validated with S1 Search in
  Sweden Central rather than Free; Application Insights is not part of the
  core path; there is no notification deduplication (unresolved notices are
  resent on each scheduled run); the Foundry project identity holds Search
  Index Data Reader rather than the Data Contributor role in Microsoft's
  guidance; that role was sufficient for both the initial healthy-source
  probe and the repaired expired-source probe.
- **Governance contract:** Added
  `schemas/governance-contract/v1alpha1/controls/KNW-001.schema.json`. It
  mirrors the `freshness_decision` evidence: policy version, source, hashed
  ETag, the three states, review record, notified roles, timestamp,
  correlation ID, and accountable role. It rejects inconsistent combinations,
  for example `fresh` with a lagging index or without a review record. The
  schema is referenced from the central schema and tested in
  `tests/test_knw_001_governance_contract.py`. A passing validation proves
  structural consistency only.