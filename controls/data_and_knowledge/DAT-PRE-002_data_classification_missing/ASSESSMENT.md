# DAT-PRE-002 — control assessment

Complete this assessment before creating exercise artifacts, implementation
code, or infrastructure.

## Candidate

- **Control ID:** DAT-PRE-002
- **Name:** Data classification missing
- **Lifecycle phase:** Pre-Live
- **Accountable role:** Data Owner

## Governance problem

- **Risk:** A file that feeds an AI system's knowledge source, prompt
  context, or training data has never been evaluated for sensitivity. No
  sensitivity label means no downstream Data Loss Prevention, access
  control, retention, or Foundry Data Security policy can distinguish
  public content from confidential or regulated content — the gap is
  usually only discovered after an oversharing incident.
- **Control objective:** Independently read the real, platform-authoritative
  classification state of a file (never assert it from application code or
  a model), compare it against the sensitivity the file's content actually
  requires, and force a guarded classification action before the file may
  be used by any AI system, rather than trusting an unverified label.
- **Authoritative signal:** The sensitivity label currently assigned to a
  file, read directly from Microsoft Purview Information Protection through
  Microsoft Graph (`driveItem: extractSensitivityLabels`) — never inferred
  or guessed.
- **Required decision:** Compliant, flagged (missing or mismatched
  classification), or blocked (extraction failed) for each file.
- **Required governance action:** Classify before use — assign the correct
  Purview sensitivity label through Microsoft Graph
  (`driveItem: assignSensitivityLabel`).
- **Required evidence:** Decision id, file id, synthetic content category,
  label id assigned, Graph long-running-operation id, resolved/pending
  status — never file content.

## Enforcement classification

- **Deterministic policy:** Yes — the "which label this content requires"
  and "does the current label satisfy it" checks are pure functions over a
  synthetic content-category marker and the extracted label id; no model
  involvement.
- **Model-assisted evaluation:** No decision authority; Microsoft Foundry
  only explains the already-computed, metadata-safe result to the Data
  Owner, and is optional in the core demo.
- **Human approval:** Required before the real `assignSensitivityLabel`
  call. A real Agent Control Specification `pre_tool_call`/`post_tool_call`
  gate escalates every guarded classify and binds the approval to the exact
  item id and required label via ACS's `action_identity`.
- **Configuration assessment:** Yes — the check is fundamentally a review
  of each file's declared platform configuration (its sensitivity label)
  against the policy for its content category.
- **Monitoring/detection:** On-demand scan of a dedicated demo OneDrive
  folder in this demo; a production system would scan on a schedule or at
  ingestion/ETL time before content reaches a knowledge source.
- **Required fail-closed behavior:** A file whose label cannot be safely
  extracted (locked, unsupported, or double-key-encrypted) is blocked from
  automatic clearance, never treated as compliant by default.

**Model/Foundry role: Active — governed subject.** The guarded classify
action is a real ACS `pre_tool_call`/`post_tool_call` intervention-point pair
(`src/dat_pre_002/acs_gate.py`), not an unmediated direct Graph call. ACS's
policy dispatcher escalates every guarded classify; the Chainlit "Classify
before use" click resolves that escalation through `approval_resolver`. A
native Python `PolicyDispatcher` is used (no OPA/Rego bundle), consistent
with the other Forged with Foundry privacy controls. The optional Foundry
explanation agent remains Explanatory only for its own narration role.

## Existing capability review

| Capability | Applicable? | What it already provides | Role in the core demo or reason not used |
|---|---:|---|---|
| Microsoft Agent Governance Toolkit | Yes | Agent Control Specification's `pre_tool_call`/`post_tool_call` intervention points and `approval_resolver` escalation | Reused as the real approval/enforcement mechanism for the guarded classify action |
| Agent Control Specification | Yes | `pre_tool_call`/`post_tool_call` gate around the guarded `assignSensitivityLabel` call, with a native Python policy dispatcher | Reused as the primary enforcement mechanism |
| Microsoft Foundry | Yes | Agent Framework hosts a non-authoritative explanation agent | Reused for explanation only; optional in the core demo |
| Foundry Control Plane | No | Not applicable; this control does not govern a Foundry agent/model interaction | Not used |
| Azure API Management AI Gateway | No | Not applicable; no inbound model traffic to mediate | Not used |
| Microsoft Purview | Yes | **Information Protection sensitivity labels**, read and assigned through Microsoft Graph (`driveItem.extractSensitivityLabels` / `assignSensitivityLabel`), are the authoritative, purpose-built mechanism for classifying files at rest — exactly the capability this repository's own planned catalog names for this control ("Evidence/source: Classification labels, Purview/DLP") | Reused as the primary enforcement and evidence capability |
| Microsoft Defender | No | Not applicable to file classification | Not used |
| Microsoft Entra | Yes | Delegated, least-privilege authentication (device code, public client) for the signed-in demo user's own OneDrive | Reused |
| Azure AI Content Safety / Language | No | Not applicable; no free-text PII scanning in this control | Not used |
| Azure Monitor / Application Insights / OTel | No | Not the primary enforcement or evidence mechanism for this control | Not used |
| Other supported Microsoft capability | Yes | **Microsoft Priva Privacy Risk Management** (data overexposure/data transfer policies) addresses a related but distinct oversharing signal; it has no public Graph API for policy authoring or alert retrieval (portal-only), which would make this control non-reproducible in code | Documented as further exploration, not used in the core demo |

## Existing samples and implementations

| Repository, documentation, or sample | Overlap | What is still missing |
|---|---|---|
| [driveItem: extractSensitivityLabels](https://learn.microsoft.com/graph/api/driveitem-extractsensitivitylabels?view=graph-rest-1.0) | Documents the read-side API used here | A runnable demo pairing extraction with a deterministic required-label policy; the doc is a raw API reference, not a control demo |
| [driveItem: assignSensitivityLabel](https://learn.microsoft.com/graph/api/driveitem-assignsensitivitylabel?view=graph-rest-1.0) | Documents the guarded, asynchronous write-side API used here, including its metered-API and long-running-operation behavior | A demo that gates the call behind explicit Data Owner approval and re-verifies the outcome instead of assuming the `202 Accepted` response means the label is already applied |
| PRI-004 (this repository) | Deterministic scanner + guarded, asynchronous platform action + non-authoritative Foundry explanation + metadata-only evidence | A Microsoft 365/Graph-native domain model (file classification) instead of an Azure Monitor Logs domain model; the first control whose primary/authoritative capability is Microsoft Purview via Graph rather than an Azure resource |

Use authoritative Microsoft sources first. Record current URLs and the review
date. Do not rely on an old sample to infer current support.

## Repository overlap

- **Related Forged with Foundry controls:** PRI-004 (deterministic scanner +
  guarded asynchronous platform action + non-authoritative Foundry
  explanation + metadata-only evidence) is the closest structural
  template. It is not a duplicate: PRI-004 governs Azure Monitor Logs
  content with Azure AI Language Text PII; DAT-PRE-002 governs Microsoft
  365 file classification state with Microsoft Purview Information
  Protection, and is the first control in the repository whose
  authoritative signal and enforcement mechanism are Microsoft
  Graph/Purview rather than an Azure resource.
- **Existing components that can be reused:** The PRI-00x code shape
  (models/policy/evidence/agent/chat separation) is reused as a structural
  pattern only; no code is imported across controls per the
  bite-sized-scope rule.
- **Risk of duplicating an existing demo:** Low — no other implemented or
  planned control in this category reads or assigns Purview sensitivity
  labels.

## Proposed contribution

- **Classification:** `COMPOSE`
- **Demo format:** `HYBRID_DEMO`
- **Deployment:** Optional — the core learning outcome (real, externally
  verifiable classification state) requires no Azure deployment; only a
  one-time Microsoft Entra app registration and pre-published tenant
  sensitivity labels. The optional Foundry explanation step reuses the
  already-existing shared root infrastructure; this control owns no Azure
  resources of its own.
- **Existing capabilities reused:** Microsoft Purview Information
  Protection sensitivity labels via Microsoft Graph
  (`extractSensitivityLabels`, `assignSensitivityLabel`, both v1.0),
  Microsoft Entra ID (delegated device-code authentication), Microsoft
  Foundry Agent Framework (optional explanation only).
- **How their role is made visible in the core demo:** Every classification
  decision is backed by a real Graph API response, not a local assertion;
  the guarded classify action is a real, asynchronous, metered Graph
  operation whose completion is polled and re-verified against a fresh
  `extractSensitivityLabels` call before the demo calls it resolved.
- **Minimum custom implementation or artifacts:** Seeding synthetic,
  unlabeled OneDrive files with content-category markers, the deterministic
  required-label policy, the extraction-to-decision mapping (compliant /
  flagged / blocked), the guarded classify-approval flow with async polling
  and re-verification, and metadata-only evidence.
- **Unique learning outcome:** Show that a file's classification status is
  a real, independently verifiable platform fact — never something an
  application or a model may assert — and that assigning a sensitivity
  label is an asynchronous, metered platform operation that must be
  re-verified after the fact rather than assumed complete from a `202
  Accepted` response.
- **Distinct governance learning beyond an existing official sample:**
  Microsoft's Graph API reference documents the calls in isolation; no
  sample pairs them with a deterministic policy, a guarded human-approved
  action, and an explanation agent that only ever sees metadata.
- **Why this deserves a separate bite-sized demo:** It is the first control
  in the repository whose primary, authoritative capability is Microsoft
  365/Microsoft Graph (Purview Information Protection) rather than an Azure
  resource — directly demonstrating this repository's own capability-first
  composition rule that Purview should be preferred when it is the better
  fit — and it is the first implemented Pre-Live, Data-category control.
- **Why deployment is or is not justified:** The core teaching point (a
  real, externally verifiable classification state) does not require any
  Azure deployment; it requires a registered Entra public-client app with
  delegated Graph permissions and tenant sensitivity labels that already
  exist in most Microsoft 365 organizations. A guided, code-driven exercise
  against a real tenant proves this more convincingly than a purely
  narrative guided exercise would, so a small executable hybrid demo is
  used instead of a pure `GUIDED_EXERCISE`.

## Smallest useful design

- **Primary governance decision:** Compliant, flagged (missing or
  mismatched classification), or blocked (extraction failed) for each file.
- **Authoritative human role or system:** The Data Owner approves
  classification; Microsoft Graph/Purview's own `extractSensitivityLabels`
  result after the classify call is the authoritative technical backstop,
  re-verified rather than assumed.
- **Signal source:** A dedicated demo folder
  (`/me/drive/root:/DAT-PRE-002-demo`) in the signed-in user's own OneDrive,
  containing synthetic files only.
- **ACS intervention point:** `pre_tool_call`/`post_tool_call`, around the
  guarded `classify_file` tool.
- **AGT capability:** Agent Control Specification's `approval_resolver` and
  `action_identity` binding, gating the classify action.
- **Foundry/Azure services:** Microsoft Foundry Agent Framework
  (explanation only, optional), Microsoft Graph / Microsoft Purview
  Information Protection, Microsoft Entra ID. No Azure resource is owned by
  this control.
- **Governance action:** Classify before use — a guarded,
  Data-Owner-approved `assignSensitivityLabel` call, polled to completion
  through the Graph long-running-operation `Location` header, then
  re-verified with a fresh `extractSensitivityLabels` call.
- **Evidence artifact:** Metadata-only record: decision id, synthetic file
  name, content category, decision, label id assigned, operation id,
  resolved/pending status, accountable role — never file content.
- **Healthy/complete scenario:** A file already carrying the correct label
  for its synthetic content category (`COMPLIANT`).
- **Policy-triggering scenario:** A file with a synthetic "confidential"
  content-category marker and no assigned label (`FLAGGED`), remediated by
  a guarded classify action and re-verified.
- **Unavailable, incomplete, or ambiguous scenario:** A file with a
  simulated extraction-failure marker (`BLOCKED`), which fails closed
  rather than defaulting to compliant.

## Community fit

- **Learning level:** Intermediate
- **Estimated completion time:** 45–60 minutes after prerequisites are
  ready; the one-time tenant setup (Entra app registration, confirming
  published sensitivity labels, enabling metered Graph APIs) can take
  longer on a first attempt and is documented separately from the runnable
  demo.
- **Minimum prerequisites:** Python 3.10–3.13, a Microsoft 365 tenant where
  the signed-in user has at least two published sensitivity labels
  available, a registered Microsoft Entra public-client app with delegated
  `Files.ReadWrite.All` and `User.Read` Graph permissions, metered Graph
  APIs enabled for the tenant, and (only for the optional Foundry
  explanation) shared Foundry infrastructure deployed.
- **Why the core demo remains accessible:** Sensitivity labels are broadly
  available on standard Microsoft 365 Business/Enterprise information
  protection licensing — unlike Priva Privacy Risk Management or Purview
  eDiscovery (Premium), no additional premium add-on is required. The Graph
  calls run against the signed-in user's own OneDrive with delegated,
  least-privilege scopes; no admin-consented application permission or
  tenant-wide DLP policy authoring is required.
- **Intentional simplifications:** The "required label" policy is inferred
  from a synthetic filename content-category marker, not real content
  inspection or trainable classifiers; label GUIDs are pre-configured
  through `.env` rather than looked up through Graph's `/security/
  informationProtection/sensitivityLabels` listing call, which remains in
  `/beta`; local, metadata-only evidence; a single demo user's OneDrive
  folder rather than a whole SharePoint site; on-demand scanning.
- **Further exploration to document rather than implement:** Trainable
  classifiers and auto-labeling policies to classify automatically instead
  of via a demo marker, AGT action-bound approval, ACS `pre_tool_call`
  mediation, scheduled scanning across a whole SharePoint site, durable
  evidence, and Microsoft Priva Privacy Risk Management data-overexposure
  policies for a related but distinct oversharing signal.
- **Optional community exploration paths:** Replace the synthetic
  content-category marker with a real Purview trainable-classifier
  evaluation call; add a second evidence sink.

## Scope boundary

- **Included:** Seed synthetic, unlabeled files into a dedicated demo
  OneDrive folder (including one simulated extraction-failure marker),
  extract each file's current label state through Graph, evaluate it
  against the deterministic required-label policy, optionally let a
  Foundry agent explain the metadata-safe result, classify a flagged file
  through a guarded, Data-Owner-approved, asynchronous Graph call, poll for
  completion, and re-verify.
- **Explicitly excluded:** Real tenant content, auto-labeling policies,
  trainable classifiers, DLP policy authoring, and any SharePoint
  site-wide crawl.
- **What the demo proves:** Classification status is read from real,
  externally verifiable Purview/Graph platform state, never asserted by
  the application or a model; a file is never treated as classified until
  Graph confirms it after the classify call; an extraction failure blocks
  automatic clearance instead of defaulting to compliant.
- **What the demo does not prove:** Regulatory compliance, complete
  tenant-wide classification coverage, real content-based auto-
  classification, or that every file storage location in an organization
  is covered.
- **Is the core control correct and safe within this boundary?** Yes — the
  only state-changing action is a guarded, explicitly approved label
  assignment on synthetic demo files in the signed-in user's own OneDrive,
  and the outcome is independently re-verified against the platform rather
  than assumed from the initial response.

## Decision

- **Proceed / revise / reject:** Proceed with the boundary above.
- **Rationale:** This control's own planned catalog entry already names
  Microsoft Purview/DLP as its evidence source. Implementing it with real
  Microsoft Graph sensitivity-label APIs — rather than an Azure-only
  substitute — directly follows this repository's capability-first
  composition rule, requires no Azure deployment for its core learning
  outcome, and teaches a distinct lesson (externally verifiable
  classification state, guarded asynchronous platform actions) not covered
  by any other implemented control.
- **Review date:** 2026-09-04
- **Authoritative references:**
  - [driveItem: extractSensitivityLabels](https://learn.microsoft.com/graph/api/driveitem-extractsensitivitylabels?view=graph-rest-1.0)
  - [driveItem: assignSensitivityLabel](https://learn.microsoft.com/graph/api/driveitem-assignsensitivitylabel?view=graph-rest-1.0)
  - [Enable metered APIs and services in Microsoft Graph](https://learn.microsoft.com/en-us/graph/metered-api-setup?tabs=azurecloudshell)
  - [Overview of metered Microsoft 365 APIs in Microsoft Graph](https://learn.microsoft.com/en-us/graph/metered-api-overview)
  - [Enable sensitivity labels for Office files in SharePoint and OneDrive](https://learn.microsoft.com/en-us/microsoft-365/compliance/sensitivity-labels-sharepoint-onedrive-files?view=o365-worldwide)
  - [Create and configure sensitivity labels and their policies](https://learn.microsoft.com/purview/create-sensitivity-labels)
  - [Learn about privacy risk management](https://learn.microsoft.com/privacy/priva/risk-management)
  - [Agent Control Specification](https://github.com/microsoft/agent-governance-toolkit/tree/main/policy-engine)
