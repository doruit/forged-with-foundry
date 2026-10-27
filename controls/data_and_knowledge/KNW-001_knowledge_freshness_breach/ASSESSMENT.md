# KNW-001 - Knowledge freshness breach assessment

## Candidate

- **Control ID:** KNW-001
- **Name:** Knowledge freshness breach
- **Lifecycle phase:** Live
- **Accountable role:** Knowledge Owner, represented by a configured Data Owner for the synthetic Blob source.

## Governance problem

- **Risk:** A source may remain searchable after its owner stops reviewing it, or the Search index may lag behind the source.
- **Control objective:** Detect overdue owner review of a current source revision and separately report whether Azure AI Search indexes the latest observed Blob modification.
- **Authoritative signals:** Blob properties provide source ETag and `Last-Modified`. A Data Owner review attestation records the ETag and policy version reviewed, with authenticated actor and server-created time. Azure AI Search provides indexed `metadata_storage_last_modified` and indexer execution status. Blob ETag can also change after property/metadata edits; `Last-Modified` is not proof of review.
- **Required decision:** One per-source report with `review_state` (`fresh`, `review_required`, or `cannot_evaluate`) and `index_state` (`current`, `sync_pending`, or `cannot_evaluate`). Index lag is not a content-review breach.
- **Required governance action:** Send a content-minimized Teams adaptive card to the Data Owner for `review_required`; route `sync_pending` and `cannot_evaluate` to the operator. Neither notification authorizes modifying content or index configuration.
- **Required evidence:** Control/policy version, correlation ID, safe Blob reference, ETag digest, attestation reference/actor/time, review age, Blob and indexed timestamps, indexer result, separate review/index states and reasons, accountable role, and notification attempt/receipt. Exclude document content, review notes, workflow URLs, and access tokens.

## Enforcement classification

- **Deterministic policy:** Yes. Compare configured Blob identity/current ETag, latest eligible review record, actor and recorded time, maximum review age, and the Search index's per-document indexed modification time against Blob `Last-Modified`.
- **Model-assisted evaluation:** No. A model cannot establish owner review or index synchronization.
- **Human approval:** The Data Owner explicitly records a review. This is not approval for an agent action.
- **Configuration assessment:** Yes. Blob scope, owner identity, maximum review age, Search index/indexer, attestation storage, and schedule are explicit. Missing, empty, invalid, or ambiguous values cannot produce a healthy result.
- **Monitoring/detection:** A Python Azure Functions Timer Trigger reads Blob/review state and Search index state on a documented schedule.
- **Required fail-closed behavior:** Missing/invalid policy, ETag, attestation, actor, timestamp, Search document/field, permission, or service response cannot produce `fresh`. Use `cannot_evaluate` for unavailable/malformed facts, `review_required` for confirmed review breach, and `sync_pending` for confirmed index lag.
- **Model/Foundry role:** **Not used - not applicable to the core path.** Blob/Search state and human review are authoritative. No ACS intervention point applies.

## Existing capability review

| Capability | Applicable? | What it already provides | Role in the core demo or reason not used |
|---|---:|---|---|
| Microsoft Agent Governance Toolkit | No | Governance capabilities for agent behavior | This is not agent behavior. |
| Agent Control Specification | No | Runtime intervention points and tool-call governance | No model/agent action is governed. |
| Microsoft Foundry | No | Agent/model hosting and evaluation | Not needed for source state, owner review, or indexing. |
| Foundry Control Plane | No | Foundry control-plane management | No Foundry resource/configuration is managed. |
| Azure API Management AI Gateway | No | Gateway controls for model traffic | No model traffic exists. |
| Microsoft Purview | No for primary decision | Labels and data-governance capabilities | Labels do not establish that an owner reviewed the current Blob version. |
| Microsoft Defender | No | Security posture and threat detections | No threat signal is part of this decision. |
| Microsoft Entra | Yes | Managed identity and Azure RBAC | Planned Function uses Blob roles and Search Index Data Reader. Free-tier Search cannot use its own managed identity to read the Blob indexer source; planned ingestion uses a short-lived container user-delegation SAS. The deployed setup user has resource-scoped Storage Blob Data Contributor (including delegation-key generation), Search Service Contributor, and Search Index Data Reader. Future owner writes go through an authenticated review action, not direct review-container access. |
| Azure AI Content Safety / Language | No | Content and language analysis | The control does not inspect or judge content. |
| Azure Monitor / Application Insights / OTel | Yes, operationally | Function logs, failures, latency, and correlation diagnostics | Sanitized operational telemetry only, not a second decision/evidence authority. |
| Azure Blob Storage | Yes | Synthetic source, ETag, Last-Modified, Entra-protected data access | Authoritative source state. Bind review records to ETag; metadata/property changes conservatively invalidate review. |
| Azure AI Search | Yes | Free-tier Blob indexer, incremental change detection, searchable metadata, and run status/history | Planned retrieval index; only the service is deployed today. Free tier has strict service, object, storage, and indexer-runtime limits; check the linked quota documentation before deployment. Compare indexed `metadata_storage_last_modified` with Blob `Last-Modified`; a successful run alone is not per-document proof. Search-to-Blob managed identity requires Basic+, so use only a read/list user-delegation SAS for the synthetic container on Free. |
| Azure Functions | Yes | Python timer-triggered execution | Scheduled monitor; requires host storage. Reads and evaluates state, then sends notifications. |
| Power Automate / Teams Workflows | Yes, license-gated | Authenticated HTTP trigger and Teams adaptive-card actions | Real notification path. Restrict trigger to the Function service-principal object ID; verify OAuth claims/audience, recipient, licensing, and receipt. HTTP 2xx alone is not delivery proof. |
| Microsoft Graph / SharePoint | No | SharePoint/OneDrive APIs | This alternative uses Blob and does not depend on SharePoint licensing. |
| Power Automate Approvals | No | Approval tasks and response workflows | This action is a review request, not approval for a consequential action. |

The connected tenant currently has no Microsoft 365 license. Teams card delivery
remains required for the deployed path but is blocked until a licensed Teams /
Power Automate tenant is available. Do not silently replace it with email or
claim real delivery from the local preview.

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
| [Power Automate OAuth HTTP triggers](https://learn.microsoft.com/en-us/power-automate/oauth-authentication?tabs=classic-designer) | Authenticated HTTP trigger and required claims. | Licensed, verified Function identity and Teams recipient/delivery path. |
| [Microsoft Teams connector](https://learn.microsoft.com/en-us/connectors/teams/) | Adaptive cards in chat or channel. | KNW-001 payload, routing, privacy filtering, and live receipt verification. |
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
- **Capabilities reused:** Blob Storage source; Free Azure AI Search Blob Indexer; Entra RBAC for Function queries; Azure Functions Timer Trigger; Application Insights; Power Automate Teams Workflows / Teams connector once licensed.
- **Visible roles:** Inspect Blob ETag/Last-Modified, the review attestation, Search indexed metadata, indexer last result, Function decision, and (after licensing) workflow run and Teams card.
- **Minimum custom work:** Pure policy, Blob/Search metadata adapter, owner review-attestation action/store, scheduled orchestration, minimized evidence, notification deduplication only if necessary, scoped deployment/cleanup, and a deployment-time short-lived SAS configurator.
- **Unique learning outcome:** Distinguish substantive owner review from Blob modification time and Search indexing lag; bind review to the exact Blob ETag.
- **Why a separate demo:** The indexer does not implement owner-review policy. This operationalizes a Knowledge Owner process QLT-001 leaves out of groundedness measurement without duplicating CHG-003.
- **Why deployment is justified:** A local walkthrough cannot demonstrate real Blob state, managed-identity Blob/Search access, actual indexer behavior, scheduled monitoring, or Teams delivery. Teams remains license-gated.

## Smallest useful design

- **Primary governance decision:** Can this source be considered fresh for retrieval under owner-review policy, and is the current source modification visible in Search?
- **Authoritative human/system:** Data Owner records a substantive review through an Entra-authenticated action. Blob supplies source ETag/Last-Modified; Search supplies indexed metadata and indexer status; deterministic code decides.
- **Signal source:** One synthetic Blob, maximum review age, ETag-bound attestation, one Blob Indexer, and a declared Search `metadata_storage_last_modified` field.
- **Decision surface:** One control-local deterministic evaluator called by an Azure Functions timer.
- **Evidence source:** Blob properties, review-attestation store, Search document/indexer state, and one minimized Function decision record. Power Automate run/message receipt verifies delivery when licensed; Application Insights is operational only.
- **ACS / AGT:** Not applicable; no agent behavior is governed.
- **Foundry/Azure services:** Blob Storage, Free Azure AI Search, Azure Functions, managed identity, host Storage Account, and Application Insights. Add a Table only if attestation or deduplication needs it and its trust/cleanup role is justified.
- **Governance action:** `review_required` sends a Teams card to Data Owner; `sync_pending` and `cannot_evaluate` route to operator. No automatic content or index changes.
- **Evidence artifact:** Policy/control version, correlation, safe source reference, ETag digest, review actor/time, source/indexed timestamps, indexer outcome, state/reason, accountable role, and notification receipt. No content, review notes, or webhook URL.
- **Healthy:** Recent review binds to current ETag and indexed timestamp matches Blob modification; overall `fresh`.
- **Triggering:** Review expired or ETag changed gives `review_required`; valid review but stale indexed timestamp gives `sync_pending`.
- **Unavailable/ambiguous:** Missing/invalid review or policy, wrong reviewer, malformed/future time, Blob/Search failure, missing document/field, or indexer error gives `cannot_evaluate` for the affected state; never report overall fresh.

## Complexity budget

- **Why custom components are necessary:** Blob/Search expose state, not this owner-review-age decision; Functions schedules but does not decide; Teams delivers but does not determine freshness.
- **Core artifacts:** Assessment/README, Function, Blob/Search adapters, policy/evidence and review action, tests, deployment/cleanup. Only use packages actually required. Configure Search objects via Entra Search Service Contributor, not admin keys. Keep the expiring SAS and Teams workflow URL out of source control and logs.
- **Omitted:** Chainlit, Foundry agent/model, ACS, APIM, SharePoint, Graph, automatic source editing, and a database unless a small Table is proven necessary for attestation or deduplication.
- **Single authority:** Derive review from Blob state plus attestation; derive index state from actual indexed document plus indexer status. Record both in one decision result; Application Insights is not a shadow decision store.
- **Metadata/configuration cases:** Missing/empty/invalid/valid Blob path, policy, owner, attestation, Search index, or fields. Missing index metadata is `cannot_evaluate`. Test content and metadata ETag changes, Blob/Search failures, and SAS creation, expiry, failure, and renewal. The user-delegation SAS is read/list-only, container-scoped, expires within seven days, and must be renewed to keep indexing running.
- **Local Teams preview:** Static `teams-preview.html` with synthetic card scenarios for layout only. It sends no message, makes no decision, and is not delivery evidence.

## Community fit

- **Learning level:** Intermediate
- **Estimated time:** 60-90 minutes after Azure prerequisites; Search SKU/region, deployment, SAS renewal, and licensed Teams setup can extend this.
- **Prerequisites:** Azure subscription/resource group; Free Search capacity in West Europe; synthetic Blob; Data Owner Entra identity; role-assignment access; licensed Teams/Power Automate tenant for real card delivery. The connected tenant lacks M365 licensing, so live notification validation is blocked.
- **Simplifications:** One synthetic Blob, one owner, one policy, one Search index. Attestation records that the configured identity invoked review for an ETag, not that review was adequate or resistant to privileged administrators. Indexed timestamps do not prove exact text parity.
- **Further exploration:** Multiple source types/cadences, full-corpus monitoring, exact source/index content hashes, immutable evidence, and organization-wide escalation.

## Scope boundary

- **Included:** Scheduled Blob review-age checks, ETag-bound attestation, Free-tier Azure AI Search Blob Indexer, separate review/index states, fail-closed outcomes, Teams notifications after licensing, local simulated card preview, minimized evidence, and control-scoped cleanup.
- **Excluded:** Legal/factual correctness, proof the owner read every passage, universal age values, byte-for-byte source/index equivalence, automatic content changes, and production-wide coverage.
- **What it proves:** Blob state, owner-review validity for the Blob ETag, Search's observed per-document modification metadata, and the deterministic combined result. Real Teams delivery is proven only by a licensed live run and message receipt. The local preview proves only card presentation.
- **What it does not prove:** Review quality, content accuracy/completeness, inventory coverage, exact indexed text, that a Teams recipient read/responded, or legal compliance.
- **Safe within boundary:** Yes if missing/ambiguous facts cannot return `fresh`, review breach and index lag remain distinct, and the preview is separate from delivery evidence.

## Decision

- **Classification:** `IMPLEMENT_GAP`
- **Demo format:** `DEPLOYABLE_DEMO`
- **Deployment:** Required for core Blob/Search monitoring; licensed Teams environment required for end-to-end notification validation.
- **Proceed / revise / reject:** Proceed with integration validation before runtime code/infrastructure.
- **Rationale:** Blob and Free Search provide the Azure-native source/index path, but not the owner-review-age decision. Search Free supports managed-identity Entra RBAC for queries but not Search managed identity to Blob; use only a short-lived user-delegation SAS for indexer ingestion. Teams cards remain required; no email substitution is authorized.
- **Review date:** 2026-10-27
- **Authoritative references:**
  - [Azure AI Search Blob Indexer](https://learn.microsoft.com/en-us/azure/search/search-how-to-index-azure-blob-storage)
  - [Azure AI Search limits and Free-tier indexer limits](https://learn.microsoft.com/en-us/azure/search/search-limits-quotas-capacity)
  - [Azure AI Search managed identity and tier requirements](https://learn.microsoft.com/en-us/azure/search/search-how-to-managed-identities)
  - [Azure AI Search RBAC](https://learn.microsoft.com/en-us/azure/search/search-security-rbac)
  - [User-delegation SAS using Azure CLI](https://learn.microsoft.com/en-us/azure/storage/blobs/storage-blob-user-delegation-sas-create-cli)
  - [Get Blob Properties](https://learn.microsoft.com/en-us/rest/api/storageservices/get-blob-properties)
  - [Azure Functions Timer Trigger](https://learn.microsoft.com/en-us/azure/azure-functions/functions-bindings-timer?tabs=python-v2)
  - [Power Automate OAuth authentication](https://learn.microsoft.com/en-us/power-automate/oauth-authentication?tabs=classic-designer)
  - [Microsoft Teams connector](https://learn.microsoft.com/en-us/connectors/teams/)
  - [QLT-001 remediation guidance](../../grounding_and_quality/QLT-001_hallucination_rate_high/docs/REMEDIATION-GUIDANCE.md)

## Integration gates before runtime implementation

1. Verify the review action binds to the current Blob ETag and derives the actor from the Entra token; document that the Data Owner and subscription administrators remain privileged.
2. Confirm Free Search capacity in West Europe. Configure Entra RBAC for Search queries and a read/list-only user-delegation SAS for the indexer; verify the SAS expiry is at most seven days, stays out of logs, and can be renewed without a paid Search tier.
3. Deploy a disposable Blob/Search spike. Confirm the Blob indexer exposes `metadata_storage_last_modified`; test source content/property changes, lag, and indexer failures.
4. Confirm the Data Owner's review permissions, Function/Search/Blob roles, resource region, and cost envelope. Stop if Free Search is unavailable; do not create Basic.
5. Prove the authenticated Teams trigger accepts only the Function identity and posts a card. Current tenant has no M365 license; keep real Teams delivery blocked until a licensed tenant is available. Do not substitute email.
6. Verify preview is offline-only, define alert deduplication, and verify cleanup removes only KNW-001 resources and grants.

Azure deployment is approved for the dedicated `rg-knw001-demo` resource group
in West Europe, using Azure AI Search Free, Flex Consumption Functions, and
LRS storage. Stop rather than create a paid Search tier if Free cannot be
provisioned. The local Teams preview is not delivery evidence; real Teams
validation remains blocked until a licensed tenant is available.

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
  safe runtime evidence, and live Teams receipt remain open gates. The cleanup
  plan was exercised; destructive cleanup still needs separate approval and
  real verification. KNW-001 remains Planned, so no governance-contract schema
  or root community-demo entry is added yet.