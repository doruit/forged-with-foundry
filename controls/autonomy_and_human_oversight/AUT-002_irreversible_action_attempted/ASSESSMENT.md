# AUT-002 - control assessment

## Decision

- **Classification:** `COMPOSE`
- **Proceed / revise / reject:** Proceed as a small complete teaching demo
- **Review date:** 2026-09-28
- **Learning level:** Foundation / Intermediate

## Candidate

- **Control ID:** AUT-002
- **Name:** Irreversible action attempted
- **Lifecycle phase:** Live
- **Accountable role:** Ops Manager

## Governance problem

- **Risk:** An agent may attempt a destructive or otherwise irreversible action without a human approval boundary, or an approval may be reused for a different action.
- **Control objective:** Prevent an unauthorized irreversible action from reaching its tool implementation and bind any approval to the exact action that was evaluated.
- **Authoritative signal:** The deterministic classification of a guarded tool call at ACS `pre_tool_call`, followed by the verified tool result at `post_tool_call`.
- **Required decision:** Allow only when the guarded action has an explicit, current human approval bound to the exact ACS action identity. Otherwise deny or escalate without executing the tool.
- **Required governance action:** Block the action and escalate to the Ops Manager when approval is missing, rejected, stale, mismatched, or unavailable.
- **Required evidence:** Control ID and policy version, intervention point, action identity, guarded tool name, redacted action metadata, decision, approval identity and timestamp when applicable, execution status, post-action verification, correlation identity, and accountable role.

## Enforcement classification

- **Deterministic policy:** Yes. The protected tool and its approval requirement are deterministic. Every invocation of the guarded irreversible-action tool escalates through ACS.
- **Model-assisted evaluation:** No. The model may propose an action, but it does not decide whether the action is safe or approved.
- **Human approval:** Yes. The operator's approval resolves the ACS escalation for the exact action identity. Approval is not inferred from model text or from the existence of a UI request.
- **Configuration assessment:** No for the core live decision. A future pre-live action matrix may declare which tools are material, but this control demonstrates runtime enforcement of one declared guarded action.
- **Monitoring/detection:** Post-action verification records whether the guarded operation produced the expected safe outcome. It does not replace the pre-action block.
- **Required fail-closed behavior:** Missing resolver, missing approval, rejected approval, expired approval, changed action arguments, policy evaluation failure, or unavailable enforcement must prevent tool execution. An unknown post-action result must not be reported as success.
- **Model/Foundry role:** `Active - governed subject`. The agent or model proposes the guarded tool call, and a real ACS `pre_tool_call`/`post_tool_call` intervention-point pair enforces the deterministic policy around that action. Foundry narration is not authoritative and is not required for the core path.

## Existing capability review

| Capability | Applicable? | What it already provides | Role in the core demo or reason not used |
|---|---:|---|---|
| Microsoft Agent Governance Toolkit | Yes | AGT's Agent Control Specification provides the supported policy and intervention-point model for agent and tool governance. | Reused as the governing capability family; its runtime package supplies the real enforcement path. |
| Agent Control Specification | Yes | `pre_tool_call` and `post_tool_call`, deterministic policy dispatch, `Decision.ESCALATE`, `run_tool`, approval resolution, and exact action identity binding. | Primary enforcement mechanism. The demo makes the escalation, block, approval, action identity, and post-action result observable. |
| Microsoft Foundry | Optional | Can host or provide the governed model or agent workload. | Not required for the core local proof. Adding Foundry hosting would add deployment complexity without changing the protected-action decision. The governed subject remains an agent/model event at the ACS boundary. |
| Foundry Control Plane | No | Platform control-plane features do not provide the action-bound runtime approval decision demonstrated here. | Not used because the decision is an inline tool-call enforcement concern. |
| Azure API Management AI Gateway | No | Gateway policies can govern API traffic and model access. | Not used because the core risk occurs at the agent tool boundary, not at an API admission boundary. |
| Microsoft Purview | No | Data classification, sensitivity, and compliance capabilities. | Not used because the control concerns action authorization, not data classification or retention. |
| Microsoft Defender | No | Security monitoring and threat detection. | Not used for the primary block. It could be a future monitoring extension, but it would not be the authoritative action gate. |
| Microsoft Entra | Optional | Identity and role-based access for a deployed approver or agent. | Not required for the local core demo. A future deployed variant may use Entra identity for authenticated approvers. |
| Azure AI Content Safety / Language | No | Content and language safety evaluation. | Not applicable to whether a destructive tool call has human approval. |
| Azure Monitor / Application Insights / OTel | Optional | Durable telemetry and correlation for a deployed workload. | Not required for the core proof. Local minimized evidence is sufficient; Azure telemetry is a future extension. |
| Other supported Microsoft capability | No | No additional service is required to establish this decision. | Deliberately omitted to keep one authoritative runtime path. |

## Existing samples and implementations

| Repository, documentation, or sample | Overlap | What is still missing |
|---|---|---|
| `controls/privacy/PRI-002_retention_violation/` | Uses ACS `pre_tool_call`/`post_tool_call` around a guarded delete and binds approval to action identity. | AUT-002 removes the privacy-retention domain logic and teaches the general irreversible-action governance decision with a minimal synthetic action. |
| `controls/data_and_knowledge/DAT-PRE-002_data_classification_missing/` | Uses ACS around a guarded state-changing tool with approval and post-action verification. | AUT-002 focuses on autonomy and irreversibility, not classification or sensitivity labels. |
| Agent Control Specification policy-engine documentation | Provides the supported intervention-point and approval semantics. | The repository still needs a bite-sized scenario showing why an irreversible action must be blocked before execution and how exact action binding prevents approval reuse. |

## Repository overlap

- **Related Forged with Foundry controls:** PRI-002 demonstrates a privacy-specific guarded delete; DAT-PRE-002 demonstrates a guarded classification update; AUT-PRE-002 owns the Pre-Live protected-action matrix that declares which tools need a human gate, and this control enforces one entry from it (no new control ID is needed for that list); AUT-001 will detect a bypass after a gate is required; AUT-004 will add emergency containment.
- **Existing components that can be reused:** ACS manifest shape, native Python policy dispatcher, `AgentControl.from_native`, `run_tool`, approval resolver, action identity, focused ACS tests, and evidence minimization conventions from PRI-002 and DAT-PRE-002.
- **Risk of duplicating an existing demo:** Medium if AUT-002 becomes another generic delete approval demo. Keep the action synthetic and make the distinct learning outcome the autonomy boundary: irreversible actions are always blocked unless approval is bound to the exact evaluated action. Do not reuse privacy retention policy, Blob lifecycle behavior, or a second approval registry.

## Proposed contribution

- **Classification:** `COMPOSE`
- **Demo format:** `HYBRID_DEMO`
- **Deployment:** Optional; not required for the core learning outcome
- **Existing capabilities reused:** Agent Control Specification and the proven repository ACS integration pattern.
- **How their role is made visible in the core demo:** The run shows an ACS escalation before execution, a fail-closed blocked path without approval, an allowed path with matching action identity, and a post-tool verification result.
- **Minimum custom implementation or artifacts:** One ACS manifest, one native Python policy dispatcher, one synthetic guarded irreversible-action implementation, a minimized evidence record, focused tests, and a short runnable walkthrough.
- **Unique learning outcome:** An agent's decision to attempt an irreversible action is not authorization. The enforcement point must be outside model reasoning and must bind approval to the exact action before execution.
- **Distinct governance learning beyond an existing official sample:** The demo combines ACS enforcement with an explicit governance evidence contract and a negative scenario showing that changed arguments cannot reuse approval.
- **Why this deserves a separate bite-sized demo:** AUT-002 is the category's reusable runtime example for protected autonomy. The domain-neutral action decision is different from privacy retention or data-classification policy.
- **Why deployment is or is not justified:** Local execution proves the ACS decision and execution boundary without cloud credentials or billable resources. Deployment may be added later to demonstrate Entra-authenticated approvers or durable telemetry, but neither is necessary for the primary learning outcome.

## Smallest useful design

- **Primary governance decision:** May this irreversible tool call execute with the current approval and exact action identity?
- **Authoritative human role or system:** Authorized human operator, represented by the explicit approval resolver; ACS is the authoritative enforcement system.
- **Signal source:** The guarded ACS tool-call input and the deterministic action classification.
- **Authoritative decision or enforcement surface:** ACS `pre_tool_call` escalation and enforcement, followed by ACS `post_tool_call` enforcement and result handling.
- **ACS intervention point, if applicable:** `pre_tool_call` and `post_tool_call`.
- **AGT capability, if applicable:** Agent Control Specification `AgentControl.run_tool` with a custom policy dispatcher and approval resolver.
- **Foundry/Azure services:** None required for the core path. A real Foundry model may be an optional governed workload, but it must not make the approval decision.
- **Governance action:** Block the action and escalate to the Ops Manager, or allow the exact approved action and record verified completion.
- **Evidence artifact:** A control-local JSON evidence record containing control ID, policy version, decision, action identity, redacted tool metadata, approval state, execution outcome, verification state, timestamp, correlation ID, and accountable role.
- **Healthy/complete scenario:** A read-only action or an irreversible action with current approval for the exact arguments is evaluated and produces verified evidence.
- **Policy-triggering scenario:** An irreversible action without an approval resolver, with a rejected or stale approval, or with changed arguments is blocked before the execute function runs.
- **Unavailable, incomplete, or ambiguous scenario:** ACS policy evaluation or the action verification result is unavailable. The action is denied or reported as unknown, never treated as successful.

## Complexity budget

- **Why each custom component is necessary:** The native ACS dispatcher must identify the control-specific protected action; the synthetic action makes execution and non-execution observable; the evidence adapter records only the minimum fields needed to prove the decision and outcome.
- **Files and dependencies used by the core, validation, or optional path:** The control-local ACS manifest, Python package, tests, README, and evidence helper are all directly invoked by the demo or its validation. `pyyaml` is used to load the manifest, matching existing controls.
- **Interfaces, agents, stores, or resources deliberately omitted:** No Chainlit UI, cloud resource, database, durable approval service, second agent, OPA bundle, or Azure Policy assignment is required for the core path.
- **How disconnected or shadow evidence is avoided:** ACS remains the decision source. The evidence record reports the ACS result and verified execute result; it does not independently approve, re-evaluate, or claim success.
- **Metadata/configuration edge cases, if applicable:** Test missing, empty, malformed, and valid guarded-action metadata. Missing or invalid mandatory metadata must not silently downgrade the action to allow.

## Community fit

- **Learning level:** Foundation / Intermediate
- **Estimated completion time:** 30-45 minutes
- **Minimum prerequisites:** Python environment, familiarity with the repository control layout, and basic understanding of tool calls and human approval.
- **Why the core demo remains accessible:** It uses an in-memory synthetic action and no Azure account, secrets, or deployment setup.
- **Intentional simplifications:** One synthetic irreversible action, native Python dispatcher, local evidence, local approval resolver, and no durable identity or approval store.
- **Further exploration to document rather than implement:** Entra-authenticated approvers, durable approval records, App Insights correlation, multiple action classes, and deployed Foundry hosting.
- **Optional community exploration paths:** Add a second irreversible action, authenticated role checks, or a deployed integration while preserving ACS as the single enforcement boundary.

## Scope boundary

- **Included:** One runtime protected-action decision, exact action-bound approval, fail-closed behavior, post-action verification, minimized evidence, and synthetic cleanup.
- **Explicitly excluded:** Universal agent shutdown, cancellation of already-completed work, legal compliance, production approval workflow, physical safety, and enforcement of unguarded tools outside this demo.
- **What the demo proves:** ACS can prevent the guarded tool from executing without the required approval and can bind an approval to the exact action identity evaluated at the enforcement point.
- **What the demo does not prove:** That every action in an arbitrary agent is guarded, that an external identity provider authenticated the approver, or that a completed irreversible action can be undone.
- **Is the core control correct and safe within this boundary?** Yes, provided every protected action reaches the ACS `run_tool` boundary and unavailable or ambiguous decisions fail closed.

## Decision

- **Proceed / revise / reject:** Proceed.
- **Rationale:** AUT-002 adds a distinct governance learning outcome while reusing a supported ACS enforcement capability and proven repository implementation pattern. The smallest safe demo requires no cloud infrastructure and avoids competing approval or policy systems.
- **Review date:** 2026-09-28
- **Authoritative references:**
  - [Agent Control Specification](https://github.com/microsoft/agent-governance-toolkit/tree/main/policy-engine)
  - [Agent Governance Toolkit](https://github.com/microsoft/agent-governance-toolkit)
  - [FwF governance contract](../../../docs/governance-contract.md)