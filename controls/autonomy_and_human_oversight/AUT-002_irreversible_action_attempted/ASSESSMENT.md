# AUT-002 - control assessment

## Current deployment assessment

- **Review date:** 2026-10-07
- **Classification:** `COMPOSE`
- **Demo format:** `DEPLOYABLE_DEMO`
- **Deployment:** Required for the cloud learning outcome.
- **Model/Foundry role:** Active - governed subject. A registered Foundry
  prompt agent requests the protected function; the Azure-hosted application
  executes it only through ACS `pre_tool_call` and `post_tool_call`.
- **Distinct learning outcome:** A real model-generated tool request is
  blocked until an Entra-authenticated user with the `OpsManager` app role
  approves the exact pending ACS action. Model text is never authorization.
- **Authoritative path:** Foundry function call, ACS enforcement, synthetic
  record deletion and verification, then minimized evidence. App Service
  authentication establishes identity; server-side role checking supplies
  authorization to ACS's existing approval resolver, not a second gate engine.
- **Resources:** Bootstrap the existing shared Foundry account, default
  project and model in the selected tenant/subscription. Add one control-owned
  project, a separately named account-scoped model deployment, one prompt
  agent, one Linux App Service plan/web app and one user-assigned identity.
  Configure one single-tenant Entra app, user app roles and managed-identity
  federation. Do not redeclare or delete the shared account.
- **Why custom code remains necessary:** A small function-call adapter joins
  the supported Foundry SDK to ACS; a claims adapter maps App Service's
  authenticated principal to the approval resolver; control-specific setup
  and cleanup track exact owned resources. Reuse the existing policy and
  evidence writer. Do not add an approval service, database or hosted-agent
  container.
- **Intentional limits:** The deletion target remains a synthetic in-memory
  record. Pending approvals are process-local and invalid after restart.
  Evidence files use the web app's persistent filesystem, not an immutable
  audit service. Public HTTPS endpoints are authenticated, not private-network
  isolated. App roles reflect the authenticated session, not instantaneous
  directory-role revocation. No claim of universal tool coverage or production
  readiness is made.
- **Validation required:** Real agent function call; ACS block before tool
  execution; authenticated exact approval; role-denied, expired, changed-action
  and replay scenarios; unavailable Foundry/identity failure; cloud evidence;
  ownership-checked cleanup preserving shared resources. Local mocks do not
  establish these live claims.
- **Current validation boundary:** The original local demonstration below is
  implemented. Shared and control infrastructure, Entra roles/federation and
  the webapp are deployed. A real registered prompt-agent function call, Azure
  startup and Entra redirect were observed; the SDK probe responses were
  deleted. Local tests and the ownership-checked cleanup preview pass.
  An authenticated-browser attempt also reached the real ACS block after
  correcting the project's runtime role to supported `Foundry User`. Its
  broader agent-management permissions are an explicit demo limitation; the
  narrower Responses/read-only composition returned HTTP 403 and was removed.
  Approved cloud execution, wrong-role browser denial and destructive cleanup
  remain unverified. Historical local screenshots are not cloud proof.
- **Capability sources:** [Foundry function calling](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/function-calling),
  [App Service Entra authentication](https://learn.microsoft.com/en-us/azure/app-service/configure-authentication-provider-aad),
  [platform user claims](https://learn.microsoft.com/en-us/azure/app-service/configure-authentication-user-identities),
  [Entra app roles](https://learn.microsoft.com/en-us/entra/identity-platform/howto-add-app-roles-in-apps).

The local CLI remains a regression path. The assessment below describes the
current cloud composition, which reuses its ACS policy and resolver.

## Decision

- **Classification:** `COMPOSE`
- **Proceed / revise / reject:** Proceed as a small complete teaching demo
- **Review date:** 2026-10-07
- **Learning level:** Intermediate

## Candidate

- **Control ID:** AUT-002
- **Name:** Irreversible action attempted
- **Lifecycle phase:** Live
- **Accountable role:** Ops Manager

## Governance problem

- **Risk:** An agent may attempt a destructive or otherwise irreversible action without a human approval boundary, or an approval may be reused for a different action.
- **Control objective:** Prevent an unauthorized irreversible action from reaching its tool implementation and bind any approval to the exact action that was evaluated.
- **Authoritative signal:** An invocation of the configured protected tool at ACS `pre_tool_call`, followed by the verified result at `post_tool_call`. Reversibility is a reviewed declaration, not a classification inferred by the model or this runtime gate.
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
- **Model/Foundry role:** `Active - governed subject`. A registered Foundry prompt agent proposes the guarded function call. The Azure webapp passes that call to ACS `pre_tool_call`/`post_tool_call`; model narration never authorizes execution or establishes verification.

## Existing capability review

| Capability | Applicable? | What it already provides | Role in the core demo or reason not used |
|---|---:|---|---|
| Microsoft Agent Governance Toolkit | Yes | AGT's Agent Control Specification provides the supported policy and intervention-point model for agent and tool governance. | Reused as the governing capability family; its runtime package supplies the real enforcement path. |
| Agent Control Specification | Yes | `pre_tool_call` and `post_tool_call`, deterministic policy dispatch, `Decision.ESCALATE`, `run_tool`, approval resolution, and exact action identity binding. | Primary enforcement mechanism. The demo makes the escalation, block, approval, action identity, and post-action result observable. |
| Microsoft Foundry | Yes | Registered prompt agents, deployed models and Responses API function calling. | Supplies the real governed function call; the application executes the function through ACS. |
| Foundry Control Plane | No | Platform control-plane features do not provide the action-bound runtime approval decision demonstrated here. | Not used because the decision is an inline tool-call enforcement concern. |
| Azure API Management AI Gateway | No | Gateway policies can govern API traffic and model access. | Not used because the core risk occurs at the agent tool boundary, not at an API admission boundary. |
| Microsoft Purview | No | Data classification, sensitivity, and compliance capabilities. | Not used because the control concerns action authorization, not data classification or retention. |
| Microsoft Defender | No | Security monitoring and threat detection. | Not used for the primary block. It could be a future monitoring extension, but it would not be the authoritative action gate. |
| Microsoft Entra | Yes | User authentication, app roles, managed identity and federation. | Authenticates operators; the server checks `OpsManager`. Managed identity accesses Foundry and supports secretless Easy Auth. |
| Azure AI Content Safety / Language | No | Content and language safety evaluation. | Not applicable to whether a destructive tool call has human approval. |
| Azure Monitor / Application Insights / OTel | Optional | Durable telemetry and correlation for a deployed workload. | No separate Monitor resource is deployed; minimized JSON evidence uses the webapp filesystem. App Service error diagnostics expose only stages, exception classes and HTTP status. |
| Azure App Service | Yes | Python hosting, HTTPS, platform authentication and managed identity. | Hosts the existing Chainlit interface, ACS and synthetic tool together; no separate approval service or container hosting is required. |

## Existing samples and implementations

| Repository, documentation, or sample | Overlap | What is still missing |
|---|---|---|
| `controls/privacy/PRI-002_retention_violation/` | Uses ACS `pre_tool_call`/`post_tool_call` around a guarded delete and binds approval to action identity. | AUT-002 removes the privacy-retention domain logic and teaches the general irreversible-action governance decision with a minimal synthetic action. |
| `controls/data_and_knowledge/DAT-PRE-002_data_classification_missing/` | Uses ACS around a guarded state-changing tool with approval and post-action verification. | AUT-002 focuses on autonomy and irreversibility, not classification or sensitivity labels. |
| Agent Control Specification policy-engine documentation | Provides the supported intervention-point and approval semantics. | The repository still needs a bite-sized scenario showing why an irreversible action must be blocked before execution and how exact action binding prevents approval reuse. |
| QLT-001 registered prompt-agent adapter | Uses the pinned Foundry SDK and a Responses function-call loop. | Reuse that supported integration shape, but place the protected AUT-002 function behind ACS rather than copying QLT-001 evaluation or telemetry. |

## Repository overlap

- **Related Forged with Foundry controls:** PRI-002 demonstrates a privacy-specific guarded delete; DAT-PRE-002 demonstrates a guarded classification update. The planned AUT-PRE-002 owns the protected-action declaration; AUT-002 manually configures one equivalent action, without consuming its matrix. AUT-001 and AUT-004 cover related planned bypass and containment concerns.
- **Existing components that can be reused:** ACS manifest shape, native Python policy dispatcher, `AgentControl.from_native`, `run_tool`, approval resolver, action identity, focused ACS tests, and evidence minimization conventions from PRI-002 and DAT-PRE-002.
- **Risk of duplicating an existing demo:** Medium if AUT-002 becomes another generic delete approval demo. Keep the action synthetic and make the distinct learning outcome the autonomy boundary: irreversible actions are always blocked unless approval is bound to the exact evaluated action. Do not reuse privacy retention policy, Blob lifecycle behavior, or a second approval registry.

### Pre-Live declaration boundary

[TOOL-PRE-001](../../tool_governance/TOOL-PRE-001_tool_inventory_incomplete/README.md)
owns inventory coverage;
[TOOL-PRE-002](../../tool_governance/TOOL-PRE-002_tool_risk_tier_not_approved/README.md)
owns high-impact tool-risk approval;
[AUT-PRE-001](../AUT-PRE-001_autonomy_boundary_undefined/README.md)
owns the allowed/prohibited autonomy boundary; and
[AUT-PRE-002](../AUT-PRE-002_hitl_gates_missing/README.md#protected-action-matrix)
owns the proposed reversibility and human-gate declaration. All four are
`Planned`. Their release-time review must precede runtime enforcement, but
AUT-002 has no implemented matrix loader, coverage validator or drift check.

The demo manually declares the synthetic delete as irreversible through its
tool configuration and policy, with Ops Manager approval and five-minute expiry.
It does not discover which tools are irreversible or establish that a workload's
declaration is complete. Future integration must consume the same reviewed,
versioned source for validation and ACS configuration rather than introducing
another policy engine or asking the model to classify its own action.

## Proposed contribution

- **Classification:** `COMPOSE`
- **Demo format:** `DEPLOYABLE_DEMO`
- **Deployment:** Required for the real Foundry, managed-identity and Entra learning outcome.
- **Existing capabilities reused:** ACS, the Foundry SDK function-call pattern, App Service authentication and Entra app roles/federation.
- **How their role is made visible in the core demo:** The run shows an ACS escalation before execution, a fail-closed blocked path without approval, an allowed path with matching action identity, and a post-tool verification result.
- **Minimum custom implementation or artifacts:** The existing ACS dispatcher/resolver, one synthetic action, small Foundry and claims adapters, minimized evidence, control-owned deployment/cleanup scripts and focused tests. No second policy engine, approval register or evidence service.
- **Unique learning outcome:** An agent's decision to attempt an irreversible action is not authorization. The enforcement point must be outside model reasoning and must bind approval to the exact action before execution.
- **Distinct governance learning beyond an existing official sample:** The demo combines ACS enforcement with an explicit governance evidence contract and a negative scenario showing that changed arguments cannot reuse approval.
- **Why this deserves a separate bite-sized demo:** AUT-002 is the category's reusable runtime example for protected autonomy. The domain-neutral action decision is different from privacy retention or data-classification policy.
- **Why deployment is justified:** A local scripted call cannot prove that a real registered Foundry agent reaches the gate using the webapp's managed identity, or that the browser's user identity comes from Entra. The local CLI remains useful for credential-free policy regression, not cloud proof.

## Smallest useful design

- **Primary governance decision:** May this irreversible tool call execute with the current approval and exact action identity?
- **Authoritative human role or system:** Entra-authenticated operator with the `OpsManager` user app role, checked server-side. ACS is the authoritative tool enforcement system.
- **Signal source:** The actual Foundry function call to the configured guarded tool. This demo fixes the irreversible-action classification before invocation; it does not assess reversibility dynamically.
- **Authoritative decision or enforcement surface:** ACS `pre_tool_call` escalation and enforcement, followed by ACS `post_tool_call` enforcement and result handling.
- **ACS intervention point, if applicable:** `pre_tool_call` and `post_tool_call`.
- **AGT capability, if applicable:** Agent Control Specification `AgentControl.run_tool` with a custom policy dispatcher and approval resolver.
- **Foundry/Azure services:** Shared Foundry account; own project, account-scoped GPT-5 deployment and prompt agent; one Linux webapp/plan and user-assigned identity. The model cannot make the approval decision.
- **Governance action:** Block the action and escalate to the Ops Manager, or allow the exact approved action and record verified completion.
- **Evidence artifact:** Minimized JSON under `/home/aut002/evidence`, including ACS outcome, Foundry response/call correlation and an opaque approver reference when applicable. The local CLI writes only control-local evidence.
- **Healthy/complete scenario:** The protected action has current exact approval from the authorized operator and produces verified evidence. There is no separate read-only tool in this demo.
- **Policy-triggering scenario:** An irreversible action without an approval resolver, with a rejected or stale approval, or with changed arguments is blocked before the execute function runs.
- **Unavailable, incomplete, or ambiguous scenario:** ACS policy evaluation or the action verification result is unavailable. The action is denied or reported as unknown, never treated as successful.

## Complexity budget

- **Why each custom component is necessary:** The dispatcher declares the protected action; the synthetic tool exposes execution; adapters join supported Foundry and App Service identity to ACS; the writer minimizes evidence; setup/cleanup scripts track exact owned resources. Every adapter has one bounded responsibility.
- **Files and dependencies used by the core, validation, or optional path:** The control-local ACS manifest, Python package, tests, README, and evidence helper are all directly invoked by the demo or its validation. `pyyaml` is used to load the manifest, matching existing controls.
- **Interfaces, agents, stores, or resources deliberately omitted:** Reuse the existing Chainlit interface in one webapp. Do not add a database, separate approval service, second agent, container registry, OPA bundle, Azure Policy gate or separate telemetry resource.
- **How disconnected or shadow evidence is avoided:** ACS remains the decision source. The evidence record reports the ACS result and verified execute result; it does not independently approve, re-evaluate, or claim success.
- **Metadata/configuration edge cases, if applicable:** Test missing, empty, malformed, and valid guarded-action metadata. Missing or invalid mandatory metadata must not silently downgrade the action to allow.

## Community fit

- **Learning level:** Intermediate
- **Estimated completion time:** 60-90 minutes; estimate depends on tenant permissions and cloud builds.
- **Minimum prerequisites:** Azure CLI, Python 3.12 through `uv`, Azure deployment/RBAC permissions, Entra application/assignment permissions, existing users and model quota.
- **Why the demo remains bounded:** One real agent, one protected function and one webapp; the record is synthetic, with no extra database or approval service.
- **Intentional simplifications:** In-memory session/record state, five-minute approval, filesystem evidence, public authenticated HTTPS and a project-scoped `Foundry User` role that also permits agent management. Restart invalidates pending approval; role revocation is not instantaneous.
- **Further exploration:** Durable approval/audit, separate requester/approver duties, multiple action classes and Monitor integration.
- **Optional local path:** Run the credential-free CLI regression without treating it as proof of cloud identity.

## Scope boundary

- **Included:** One runtime protected-action decision, exact action-bound approval, fail-closed behavior, post-action verification, minimized evidence, and synthetic cleanup.
- **Explicitly excluded:** Universal agent shutdown, cancellation of already-completed work, legal compliance, production approval workflow, physical safety, and enforcement of unguarded tools outside this demo.
- **What the demo proves:** ACS can prevent the guarded tool from executing without the required approval and can bind an approval to the exact action identity evaluated at the enforcement point.
- **What the demo does not prove:** Approved cloud execution, wrong-role browser denial and destructive cleanup remain unverified. There is no universal tool coverage, durable cross-restart approval, separation of duties or ability to undo deletion.
- **Is the core control correct and safe within this boundary?** Yes, provided every protected action reaches the ACS `run_tool` boundary and unavailable or ambiguous decisions fail closed.

## Decision

- **Proceed / revise / reject:** Proceed.
- **Rationale:** Compose a real registered Foundry agent, Entra operator identity and ACS's supported action binding in one small Azure runtime. Keep the historical CLI as a regression path and do not mark the cloud demo Validated before approved execution, negative browser scenarios and cleanup have run.
- **Review date:** 2026-10-07
- **Authoritative references:**
  - [Agent Control Specification](https://github.com/microsoft/agent-governance-toolkit/tree/main/policy-engine)
  - [Agent Governance Toolkit](https://github.com/microsoft/agent-governance-toolkit)
  - [FwF governance contract](../../../docs/governance-contract.md)
  - [AUT-PRE-002 declaration and lifecycle handoff](../AUT-PRE-002_hitl_gates_missing/README.md#pre-live-to-live-handoff)