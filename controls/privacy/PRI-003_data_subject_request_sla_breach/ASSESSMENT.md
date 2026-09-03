# PRI-003 — control assessment

## Candidate

- **Control ID:** PRI-003
- **Name:** Data subject request SLA breach
- **Lifecycle phase:** Live
- **Accountable role:** DPO

## Governance problem

- **Risk:** A data subject request (access, rectification, or erasure) passes
  its regulatory response deadline without anyone noticing, because SLA
  tracking lives only in a spreadsheet or a person's memory.
- **Control objective:** Independently detect requests that are approaching or
  have passed their SLA deadline and force a DPO escalation, regardless of
  what the intake or case-management tool reports.
- **Authoritative signal:** DSR request type, received date, status, and any
  granted extension.
- **Required decision:** On track, at risk (approaching deadline), breached,
  or blocked (unknown/invalid metadata).
- **Required governance action:** Escalate unresolved at-risk or breached
  requests to the DPO; optionally grant one guarded SLA extension for eligible
  unresolved request types. Closed requests remain audit-only.
- **Required evidence:** Decision, request type, due date, days until due,
  resolved flag, and whether an extension was granted — no requester name,
  email, or request content.

## Enforcement classification

- **Deterministic policy:** Yes — SLA due-date math and the at-risk/breached
  threshold are pure, timezone-aware functions with no model involvement.
- **Model-assisted evaluation:** No decision authority; Microsoft Foundry only
  explains already-computed, metadata-safe results to the DPO.
- **Human approval:** Required before any due-date extension is applied,
  bound to the exact decision and record version (ETag).
- **Configuration assessment:** N/A for the core demo.
- **Monitoring/detection:** On-demand scan of a synthetic DSR register in this
  demo; production use would run on a schedule or event trigger.
- **Required fail-closed behavior:** Unknown or missing request type blocks
  automatic SLA computation and is not silently treated as compliant.

## Existing capability review

| Capability | Applicable? | What it already provides | Reuse decision |
|---|---:|---|---|
| Microsoft Agent Governance Toolkit | Partial | Action-bound approval protocol could replace the local extension-approval registry | Link as further exploration; not used in the core demo |
| Agent Control Specification | Partial | `pre_tool_call` intervention point if extension-granting becomes an agent tool | Link as further exploration; not used in the core demo |
| Microsoft Foundry | Yes | Agent Framework hosts a non-authoritative explanation agent | Reused for explanation only |
| Foundry Control Plane | No | Not applicable to this control's scope | Not used |
| Azure API Management AI Gateway | No | Not applicable; no inbound model traffic to mediate | Not used |
| Microsoft Purview | No | Purview retention labels govern Microsoft 365 content, not a DSR case queue | Not used |
| Microsoft Defender | No | Not applicable | Not used |
| Microsoft Entra | Yes | Entra ID authenticates the local demo identity to Table Storage and Foundry | Reused |
| Azure AI Content Safety / Language | No | Not applicable; no unstructured PII text is processed by this control | Not used |
| Azure Monitor / Application Insights / OTel | Partial | Can host durable evidence and alerting in a fuller deployment | Linked as further exploration |
| Other supported Microsoft capability | Yes | **Microsoft Priva Subject Rights Requests** (Graph API) is the authoritative, tenant-wide DSR intake and SLA-tracking capability | Not used in the core demo — requires M365 E5/Priva licensing and tenant-wide setup, too heavy a prerequisite for a bite-sized demo; linked as the primary further-exploration path |

## Existing samples and implementations

| Repository, documentation, or sample | Overlap | What is still missing |
|---|---|---|
| Microsoft Priva Subject Rights Requests (Graph API, beta) | Full DSR intake, case management, and SLA countdown for a real M365 tenant | A lightweight, dependency-free way to teach the SLA-breach decision and guarded extension pattern without provisioning Priva |
| PRI-002 retention violation (this repository) | Deterministic scanner + non-authoritative Foundry agent + guarded, ETag-conditional state change + local evidence | A due-date/SLA domain model instead of a retention-age domain model; no destructive action, only an extension grant |

Use authoritative Microsoft sources first. Record current URLs and the review
date. Do not rely on an old sample to infer current support.

## Repository overlap

- **Related Forged with Foundry controls:** PRI-002 (retention violation) is
  the closest structural sibling — deterministic scan, non-authoritative
  Foundry explanation, guarded ETag-conditional state change, local evidence.
  PRI-001 (PII exposure) is a real-time chat-turn boundary and a weaker fit.
- **Existing components that can be reused:** The PRI-002 code shape
  (models/policy/approval/evidence/storage/agent/chat separation) is reused as
  a structural pattern; no code is imported across controls per the
  bite-sized-scope rule.
- **Risk of duplicating an existing demo:** Low — no other control tracks a
  case-queue SLA deadline against a due date with a guarded extension.

## Proposed contribution

- **Classification:** `COMPOSE`
- **Demo format:** `DEPLOYABLE_DEMO`
- **Deployment:** Required for the core learning outcome
- **Existing capabilities reused:** Azure Table Storage (Entra ID-only,
  ETag optimistic concurrency) for persistence; Microsoft Foundry Agent
  Framework for non-authoritative explanation; Microsoft Entra ID for
  authentication.
- **Minimum custom implementation or artifacts:** The SLA due-date policy (per-request-type SLA,
  at-risk/breached/blocked classification), the extension-eligibility guard
  (erasure requests may not be extended; only one extension per request), the
  one-time ETag-bound extension-approval registry, and metadata-only evidence.
- **Unique learning outcome:** Show that SLA-breach detection and a due-date
  extension are two different governance decisions — detecting a missed
  deadline never implies permission to move it, and only a specific request
  type may ever be extended, and only once.
- **Why an existing official sample is insufficient:** No public sample
  demonstrates a deterministic, non-Priva SLA-breach detector paired with a
  guarded, ETag-conditional extension grant and a non-authoritative Foundry
  explanation agent.
- **Why this deserves a separate bite-sized demo:** It teaches a distinct
  privacy signal (missed regulatory deadline) and a distinct guarded action
  (extend a deadline) that PRI-001 (redact) and PRI-002 (delete) do not cover.

## Smallest useful design

- **Primary governance decision:** On track, at risk, breached, or blocked
  for each DSR record; separately, whether a due-date extension may be
  granted.
- **Signal source:** A synthetic DSR register in a dedicated Azure Table
  Storage table, scoped to a single demo partition key.
- **ACS intervention point, if applicable:** `pre_tool_call`, if extension
  granting is later exposed as an agent tool (not in the core demo).
- **AGT capability, if applicable:** Action-bound approval protocol, as a
  production replacement for the local one-time extension-approval registry.
- **Foundry/Azure services:** Microsoft Foundry Agent Framework (explanation
  only), Azure Table Storage, Microsoft Entra ID.
- **Governance action:** Escalate to the DPO (log-only); optionally grant one
  guarded, ETag-conditional SLA extension for eligible unresolved request
  types. Closed requests remain audit-only.
- **Evidence artifact:** Metadata-only record: decision id, request type, due
  date, days until due, resolved flag, escalated flag, extension-granted
  flag, accountable role.
- **Safe scenario:** A request still within its SLA window (`ON_TRACK`).
- **Policy-triggering scenario:** A request within the warning window
  (`AT_RISK`) and a request past its deadline (`BREACHED`), including one
  closed after its deadline for audit purposes.
- **Control/dependency-failure scenario:** A request with a missing or
  unknown request type (`BLOCKED`), and an extension attempt on a request
  type or record state that does not permit one (deterministically refused).

## Community fit

- **Learning level:** Foundation / Intermediate
- **Estimated completion time:** 30–45 minutes after Azure access is
  available.
- **Minimum prerequisites:** Python 3.10–3.13, `az login`, shared Foundry
  infrastructure, PRI-003 Table Storage infrastructure.
- **Why the core demo remains accessible:** No Priva/M365 E5 tenant is
  required; a dedicated Table Storage account and a Chainlit UI mirror the
  PRI-002 experience with a smaller Azure footprint (no Blob lifecycle policy,
  no soft delete configuration).
- **Intentional simplifications:** Synthetic register instead of Priva;
  in-memory, single-process extension approvals; local, metadata-only
  evidence; public endpoint; on-demand scanning instead of a schedule.
- **Further exploration to document rather than implement:** Microsoft
  Priva Subject Rights Requests integration, AGT action-bound approval, ACS
  `pre_tool_call` mediation, durable evidence, private networking.
- **Optional community exploration paths:** Add a scheduled trigger (Azure
  Functions timer) instead of on-demand scanning; add a second evidence sink.

## Scope boundary

- **Included:** Seed a synthetic DSR register, scan and classify every
  record, let a Foundry agent explain the metadata-safe result, escalate
  unresolved requests to the DPO, optionally grant one guarded SLA extension,
  and keep closed requests audit-only.
- **Explicitly excluded:** Real DSR intake, identity verification of the data
  subject, case-management workflow, and any destructive action.
- **What the demo proves:** SLA due-date computation, the at-risk/breached
  threshold, and the extension guard are deterministic and independent of the
  model; closed requests cannot be escalated or extended through the
  demonstrated path; a mismatched or stale record version blocks the extension.
- **What the demo does not prove:** Regulatory compliance, complete DSR
  process coverage, durable audit retention, or production identity design.
- **Is the core control correct and safe within this boundary?** Yes — no
  requester content is processed, and the only state-changing action is a
  guarded, single-use, ETag-conditional due-date extension.

## Decision

- **Proceed / revise / reject:** Proceed with the boundary above.
- **Rationale:** The control teaches a distinct SLA-monitoring and
  guarded-extension pattern that is not covered by PRI-001 or PRI-002, reuses
  Entra ID and Foundry rather than reimplementing them, and documents the
  authoritative Priva capability as further exploration instead of
  reimplementing DSR case management.
- **Review date:** 2026-09-03
- **Authoritative references:**
  - [Microsoft Priva Subject Rights Requests overview](https://learn.microsoft.com/en-us/purview/privacy-priva-subject-rights-requests) — verify current URL during implementation.
  - [Azure Table Storage overview](https://learn.microsoft.com/en-us/azure/storage/tables/table-storage-overview)
  - [Authorize access to tables with Microsoft Entra ID](https://learn.microsoft.com/en-us/azure/storage/tables/authorize-access-azure-active-directory)
  - [Manage concurrency in Table Storage](https://learn.microsoft.com/en-us/rest/api/storageservices/managing-concurrency-in-microsoft-azure-storage)
  - [AGT action-bound approval protocol](https://github.com/microsoft/agent-governance-toolkit/blob/main/docs/adr/0030-action-bound-approval-protocol.md)
  - [Agent Control Specification](https://github.com/microsoft/agent-governance-toolkit/tree/main/policy-engine)
