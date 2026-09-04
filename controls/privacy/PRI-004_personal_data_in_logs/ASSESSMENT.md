# PRI-004 — control assessment

## Candidate

- **Control ID:** PRI-004
- **Name:** Personal data in logs
- **Lifecycle phase:** Live
- **Accountable role:** Privacy Officer

## Governance problem

- **Risk:** Application code accidentally writes personal data (an email
  address, phone number, or free-text customer message) into diagnostic logs,
  where it sits readable by every engineer or support agent with log access —
  far beyond the audience the data subject ever agreed to.
- **Control objective:** Independently detect personal data that reached a
  log store, prove it can be safely masked for review, remove the offending
  record through an authoritative deletion mechanism, and fix the logging
  configuration so the same field stops leaking going forward.
- **Authoritative signal:** Azure AI Language Text PII findings over the log
  message content, read from Azure Monitor Logs.
- **Required decision:** Clean, PII detected, or blocked (detection
  unavailable).
- **Required governance action:** Mask (safe preview only) / delete (real
  Azure Monitor Data Purge request) / update logging (suppress the field for
  future ingestion).
- **Required evidence:** Decision, field name, PII categories (no values),
  purge operation id, resolved/pending status — never the raw log message.

## Enforcement classification

- **Deterministic policy:** Yes — clean/detected/blocked classification and
  the purge/field-policy guards are pure, timezone-aware functions with no
  model involvement.
- **Model-assisted evaluation:** No decision authority; Microsoft Foundry
  only explains already-computed, metadata-safe results to the Privacy
  Officer.
- **Human approval:** Required before the real Data Purge request and before
  a field-suppression policy change. Both are real Agent Control
  Specification `pre_tool_call`/`post_tool_call` gates bound to the exact
  decision and a content-hash guard via ACS's `action_identity`.
- **Configuration assessment:** N/A for the core demo.
- **Monitoring/detection:** On-demand scan of a dedicated Log Analytics
  custom table in this demo; production use would run on a schedule.
- **Required fail-closed behavior:** A record whose PII detection could not
  complete safely is blocked from automatic clearance, never treated as
  clean by default.

**Model/Foundry role: Active — governed subject.** Both guarded actions are
real ACS `pre_tool_call`/`post_tool_call` intervention-point pairs
(`src/pri_004/acs_gate.py`), not bespoke in-memory approval registries. ACS's
policy dispatcher escalates every guarded action; the Chainlit approval click
resolves that escalation through `approval_resolver`, and ACS's
`action_identity` binds the approval to the exact tool_call args it
evaluated. A native Python `PolicyDispatcher` is used (no OPA/Rego bundle),
consistent with PRI-001/002/003.

## Existing capability review

| Capability | Applicable? | What it already provides | Reuse decision |
|---|---:|---|---|
| Microsoft Agent Governance Toolkit | Yes | Agent Control Specification's `pre_tool_call`/`post_tool_call` intervention points and `approval_resolver` escalation | Reused as the real approval/enforcement mechanism for both guarded actions |
| Agent Control Specification | Yes | `pre_tool_call`/`post_tool_call` gate around the guarded purge and field-policy change, with a native Python policy dispatcher | Reused as the primary enforcement mechanism, replacing the local `PurgeApprovalRegistry`/`FieldPolicyApprovalRegistry` |
| Microsoft Foundry | Yes | Agent Framework hosts a non-authoritative explanation agent | Reused for explanation only |
| Foundry Control Plane | No | Not applicable to this control's scope | Not used |
| Azure API Management AI Gateway | No | Not applicable; no inbound model traffic to mediate | Not used |
| Microsoft Purview | No | Purview retention/sensitivity labels govern Microsoft 365 content, not custom Log Analytics tables | Not used |
| Microsoft Defender | No | Not applicable | Not used |
| Microsoft Entra | Yes | Entra ID authenticates the local demo identity for ingestion, query, and purge | Reused |
| Azure AI Content Safety / Language | Yes | Azure AI Language Text PII detects and redacts personal data in the log message (same capability PRI-001 reuses, applied to logs instead of chat/documents) | Reused |
| Azure Monitor / Application Insights / OTel | Yes | Logs Ingestion API, Log Analytics Query API, and the Azure Monitor **Data Purge API** are the authoritative, purpose-built mechanisms for sending, finding, and deleting personal data in logs | Reused as the primary platform capability |
| Other supported Microsoft capability | No | — | — |

## Existing samples and implementations

| Repository, documentation, or sample | Overlap | What is still missing |
|---|---|---|
| [Manage personal data in Azure Monitor Logs](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/personal-data-mgmt) | Documents the strategy, the Purge API, and required roles for exactly this scenario | A runnable, deterministic detection-and-guarded-purge demo; the doc is guidance, not code |
| PRI-001 (this repository) | Reuses Azure AI Language Text PII for detection/redaction | A logs-specific data source, and a purge-based deletion mechanism instead of Blob redaction |
| PRI-002 / PRI-003 (this repository) | Deterministic scanner + non-authoritative Foundry agent + guarded, re-verified destructive action + local evidence | A due-date/retention-age domain model instead of a log-content domain model; a real, asynchronous, rate-limited platform deletion API instead of an immediate Blob/Table delete |

Use authoritative Microsoft sources first. Record current URLs and the review
date. Do not rely on an old sample to infer current support.

## Repository overlap

- **Related Forged with Foundry controls:** PRI-001 (Text PII reuse pattern)
  and PRI-002/PRI-003 (deterministic scanner + guarded destructive action +
  non-authoritative Foundry explanation) are both structural templates;
  PRI-004 composes elements of each around a new data source.
- **Existing components that can be reused:** The PRI-00x code shape
  (models/policy/approval/evidence/storage/agent/chat separation) is reused
  as a structural pattern only; no code is imported across controls per the
  bite-sized-scope rule.
- **Risk of duplicating an existing demo:** Low — no other control ingests,
  queries, or purges Azure Monitor Logs data.

## Proposed contribution

- **Classification:** `COMPOSE`
- **Existing capabilities reused:** Azure Monitor Logs Ingestion API, Log
  Analytics Query API, Azure Monitor Data Purge API, Azure AI Language Text
  PII, Microsoft Foundry Agent Framework, Microsoft Entra ID.
- **Minimum custom code:** The clean/detected/blocked classification policy,
  the content-hash guard that substitutes for Log Analytics' lack of native
  optimistic concurrency, the purge-eligibility guard, the in-memory
  field-suppression policy (the "update logging" governance action), and
  metadata-only evidence.
- **Unique learning outcome:** Show that finding personal data in logs,
  safely previewing a redacted version, actually deleting it from the
  platform, and fixing the logging configuration going forward are four
  separate governance decisions — and that the platform's own deletion
  mechanism (Data Purge) is deliberately slow, rate-limited, and
  compliance-gated, which the demo must respect rather than paper over.
- **Why an existing official sample is insufficient:** Microsoft's
  personal-data-management guidance documents the mechanism but does not
  ship a deterministic detection-plus-guarded-purge demo with an
  explanation agent and a field-suppression remediation loop.
- **Why this deserves a separate bite-sized demo:** It teaches a distinct
  privacy signal (data captured by logging, not by chat or document
  workflows) and a distinct guarded action (a real, asynchronous compliance
  deletion API) that PRI-001–PRI-003 do not cover.

## Smallest useful design

- **Primary governance decision:** Clean, PII detected, or blocked for each
  scanned log record; separately, whether a purge request or field-policy
  change may proceed.
- **Signal source:** A dedicated Log Analytics workspace and custom table
  (`PRI004AppLogs_CL`), populated via the Logs Ingestion API with synthetic
  records only.
- **ACS intervention point:** `pre_tool_call`/`post_tool_call`, around the
  guarded purge (`submit_data_purge`) and field-policy change
  (`apply_field_policy`) tools.
- **AGT capability:** Agent Control Specification's `approval_resolver` and
  `action_identity` binding, replacing the local approval registries.
- **Foundry/Azure services:** Microsoft Foundry Agent Framework (explanation
  only), Azure Monitor Logs (ingestion, query, purge), Azure AI Language
  Text PII, Microsoft Entra ID.
- **Governance action:** Mask (non-destructive redacted preview), delete
  (guarded, content-hash-reverified Data Purge request), update logging
  (guarded field-suppression toggle for future ingestion).
- **Evidence artifact:** Metadata-only record: decision id, field name, PII
  category list (no values), purge operation id, resolved/pending status,
  accountable role.
- **Safe scenario:** A log record with no PII (`CLEAN`).
- **Policy-triggering scenario:** A log record containing synthetic PII
  (`PII_DETECTED`), remediated via mask-preview, guarded purge, and a
  field-suppression policy change demonstrated on a follow-up seed.
- **Control/dependency-failure scenario:** A record with a simulated
  detector-unavailable marker (`BLOCKED`), and a purge attempt whose content
  hash no longer matches the evaluated decision (deterministically refused).

## Community fit

- **Learning level:** Intermediate
- **Estimated completion time:** 45–60 minutes after Azure access is
  available (heavier than PRI-002/003 due to Log Analytics ingestion
  latency and the async purge API).
- **Minimum prerequisites:** Python 3.10–3.13, `az login`, shared Foundry
  infrastructure, PRI-004 Log Analytics infrastructure.
- **Why the core demo remains accessible:** No manual KQL authoring is
  required from the user; the demo issues the queries. The Bicep uses a
  `kind: 'Direct'` DCR, which needs no separate Data Collection Endpoint.
- **Intentional simplifications:** Synthetic records only; a native Python
  ACS policy dispatcher instead of an OPA/Rego bundle; content-hash guard
  instead of a native ETag; local, metadata-only evidence; public endpoint.
- **Production extensions to document rather than implement:** An OPA/Rego
  ACS policy bundle, durable evidence, scheduled scanning, private
  networking.
- **Optional community exploration paths:** Add a data collection
  transformation that redacts known-risky fields at ingestion time instead
  of detecting them after the fact (Microsoft's own top recommendation in
  the personal-data-management guidance).

## Scope boundary

- **Included:** Seed synthetic log records (including one simulated
  detector-unavailable record), scan and classify them, let a Foundry agent
  explain the metadata-safe result, preview a redacted mask, request a real
  guarded purge, check purge status, and toggle a field-suppression policy
  that changes future seeded records.
- **Explicitly excluded:** Real application log integration, scheduled
  scanning, in-place mutation of already-ingested Log Analytics rows
  (not supported by the platform), and any destructive action beyond the
  documented Purge API.
- **What the demo proves:** Detection, the content-hash guard, and the
  purge/field-policy eligibility rules are deterministic and independent of
  the model; a changed or already-clean record is not purged; a purge
  request is correctly submitted to the real Azure Monitor Data Purge API
  and its rate limit and async SLA are respected and disclosed.
- **What the demo does not prove:** That the purge has completed (Microsoft
  states up to 30 days), regulatory compliance, complete PII recall, or that
  every logging path in a real application is covered.
- **Is the core control correct and safe within this boundary?** Yes — no
  real personal data is processed, and the only irreversible action (purge)
  is guarded by explicit approval and a content-hash re-verification
  immediately before the call.

## Decision

- **Proceed / revise / reject:** Proceed with the boundary above.
- **Rationale:** The control teaches a distinct signal (logs) and reuses the
  real, purpose-built Azure Monitor Data Purge capability instead of
  reimplementing deletion, while being explicit about that capability's
  genuine limitations (async, rate-limited, GDPR-scoped) rather than hiding
  them.
- **Review date:** 2026-09-04
- **Authoritative references:**
  - [Manage personal data in Azure Monitor Logs](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/personal-data-mgmt)
  - [Workspace Purge API](https://learn.microsoft.com/en-us/rest/api/loganalytics/workspace-purge/purge)
  - [Logs Ingestion API overview](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/logs-ingestion-api-overview)
  - [Create a custom table](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/create-custom-table)
  - [Azure built-in roles — Monitor category](https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles/monitor) (Data Purger, Log Analytics Data Reader, Monitoring Metrics Publisher)
  - [Azure AI Language Text PII overview](https://learn.microsoft.com/azure/ai-services/language-service/personally-identifiable-information/overview)
  - [Microsoft.OperationalInsights/workspaces template reference](https://learn.microsoft.com/en-us/azure/templates/microsoft.operationalinsights/workspaces) (API version `2025-07-01`)
  - [Microsoft.Insights/dataCollectionRules template reference](https://learn.microsoft.com/en-us/azure/templates/microsoft.insights/datacollectionrules) (API version `2024-03-11`)
  - [Agent Control Specification](https://github.com/microsoft/agent-governance-toolkit/tree/main/policy-engine)
