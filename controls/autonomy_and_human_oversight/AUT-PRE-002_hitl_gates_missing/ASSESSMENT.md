# AUT-PRE-002 - control assessment

## Candidate

- **Control ID:** AUT-PRE-002
- **Name:** HITL gates missing
- **Lifecycle phase:** Pre-Live
- **Accountable role:** Business Owner

## Governance problem

- **Risk:** An allowed high-impact action ships without a defined human gate.
- **Objective:** Require role, expiry and evidence for permitted protected actions.
- **Authoritative signal:** The same reviewed mandate attachment used by
  AUT-PRE-001, checked against the actual release tool definitions.
- **Decision:** Block release if a permitted irreversible/high-impact action
  is ungated or has incomplete/unsupported approval requirements.
- **Action:** Return an AUT-PRE-002 finding without publishing the workload.
- **Evidence:** Policy/control version, source and candidate hashes,
  decision/reason, release action/verification, timestamp, correlation and role.

## Enforcement classification

- **Deterministic policy:** Structural conditions in JSON Schema; semantic
  release findings in the existing Conftest/Rego layer.
- **Model-assisted evaluation:** Not used. The agent cannot choose its approver.
- **Human approval:** Reviewed declaration plus separate protected release approval.
  AUT-002 still requires a real operator's approval for the exact runtime action.
- **Configuration assessment:** Primary responsibility.
- **Monitoring/detection:** Not the authoritative decision.
- **Fail closed:** Missing role/expiry, unsupported dual approval, unknown
  reversibility, ungated protected actions, missing source or drift deny release.
- **Model/Foundry role:** Not used - not applicable to the release decision.
  Foundry is the real target; the downstream runtime is Active through ACS.

## Existing capability review

| Capability | Applicable? | Existing capability | Composition decision |
|---|---|---|---|
| Microsoft Agent Governance Toolkit | Yes, downstream | ACS capability family | Reuse existing runtime enforcement. |
| Agent Control Specification | Yes | Escalation, exact identity, pre/post tool calls | Consume checked gate data with the current approval resolver. |
| Microsoft Foundry | Yes | Real prompt agents/function tools | Verify declared gates cover the deployed definition. |
| Foundry Control Plane | No | Platform governance | Does not enforce this repository-owned contract automatically. |
| Azure API Management AI Gateway | No | API policies | Not the human-sign-off declaration point. |
| Microsoft Purview | No | Data governance | No additional classification requirement here. |
| Microsoft Defender | No | Detection | Cannot replace the pre-action approval requirement. |
| Microsoft Entra | Yes | User roles, managed identity and OIDC | Existing OpsManager identity for runtime; separate release identity. |
| Azure AI Content Safety / Language | No | Content analysis | Does not supply action-bound human approval. |
| Azure Monitor / Application Insights / OTel | No new resource | Telemetry | Reuse minimized gate/runtime evidence. |
| Other supported Microsoft capability | Yes | Azure Policy deny | Demonstrate missing gate-status ARM denial, with tag and data-plane limitations. |

## Existing samples and implementations

| Source | Reuse | Gap |
|---|---|---|
| AUT-002 ACS resolver and cloud chat | Exact approval, expiry, replay rejection and verification | Load reviewed gate requirements instead of hardcoded requirements. |
| Shared governance-contract gate | Schema, required IDs, Rego and evidence | Attachment-backed protected-action findings. |
| VAL-PRE-002 OIDC workflow | Gate-before-release and independent Policy experiment | Real mandate-bound AUT-002 release. |

## Repository overlap

- **Related:** AUT-PRE-001 owns mandate/scope, not gate completeness;
  TOOL-PRE-001/002 stay planned supporting responsibilities.
- **Reuse:** The paired candidate and declaration owned under AUT-PRE-001,
  existing shared gate and AUT-002 deployment/runtime.
- **Duplication risk:** No copied matrix, second resolver or new approval service.

## Proposed contribution

- **Classification:** COMPOSE
- **Format:** HYBRID_DEMO
- **Deployment:** Local gate is credential-free. Cloud release and real ACS
  consumption are required for the paired learning outcome.
- **Reused capabilities:** JSON Schema, Rego, ACS, Foundry, Entra and Azure Policy.
- **Visibility:** A valid mandate with missing sign-off fails this control;
  a valid candidate configures the real runtime gate.
- **Minimum custom artifacts:** Independent evidence schema, negative fixtures,
  native Rego findings and a bounded adapter joining the same reviewed source
  to existing ACS. No disconnected sample success record.
- **Unique outcome:** Permission to expose a tool is not per-action approval.
- **Beyond samples:** Bind reviewed role/expiry/evidence to the actual cloud tool.
- **Separate-control justification:** A complete business mandate can still
  lack an actionable approval boundary.
- **Deployment justification:** Local shape validation cannot prove runtime
  identity, deployment failure propagation or actual action enforcement.

## Smallest useful design

- **Primary decision:** Are all permitted protected actions properly gated?
- **Authority:** Business Owner reviews requirements; shared Rego rejects release.
- **Signal:** Once-read mandate and real candidate tool definitions.
- **Enforcement:** Shared deployment gate and later ACS tool boundaries.
- **Evidence source:** Existing gate artifact and actual runtime records.
- **ACS points:** pre_tool_call and post_tool_call; no prompt-only approval.
- **AGT capability:** Existing ACS escalation and exact approval resolution.
- **Azure services:** Reused AUT-002 Foundry/App Service/identity, scoped native
  Policy configuration and pipeline federation only as needed.
- **Action:** Block release; identify incomplete sign-off requirement.
- **Artifact:** One combined gate record with a distinct AUT-PRE-002 finding.
- **Healthy:** Synthetic delete requires OpsManager, positive bounded expiry
  and action identity/execution/verification evidence.
- **Trigger:** Valid mandate but missing gate, role, expiry or evidence requirement.
- **Ambiguous:** Unsupported gate, unknown impact/reversibility or changed source.

## Complexity budget

- **Custom necessity:** Resolve shared local evidence once and transform only
  supported gate values into existing ACS configuration.
- **Invoked files:** Schemas, fixtures, paired candidate, existing gate and
  actual release/runtime adapter; every artifact has an exercised path.
- **Omitted:** Dedicated review UI, database, model evaluator, dual-approval
  protocol, duplicate cloud workload or shadow register.
- **No shadow evidence:** Both controls use the same source hash and release bytes.
- **Edge cases:** Missing/empty/invalid/valid gates, role mismatch, bad TTL,
  prohibited actions with attempted approval, standalone and combined contracts.

## Community fit

- **Level:** Intermediate
- **Time:** 60-90 minutes after prerequisites are ready; Azure permissions and build time vary.
- **Prerequisites:** Python/Conftest locally; authorized Azure/Entra/GitHub
  setup for cloud release and an actual operator for runtime sign-off.
- **Accessibility:** One mandate review, separate intelligible findings.
- **Simplifications:** Single-human approval, synthetic records, bounded
  scopes and declared review metadata, not authenticated business signatures.
- **Further exploration:** Durable audit, additional scope types and distinct approvers.
- **Optional path:** Standalone local assessment without another control entry.

## Scope boundary

- **Included:** Protected-action gate completeness, checked-source handoff,
  real cloud release and existing action-bound ACS execution.
- **Excluded:** Signed legal/business attestation, universal tool interception,
  dual approval and enterprise approval persistence.
- **Proof required:** Missing gate blocks real release; valid gate reaches
  the deployed ACS resolver; actual operator approval remains required.
- **Non-claims:** Review metadata does not authenticate a reviewer; status tags
  do not prove the gate ran; Azure Policy does not guard Foundry data-plane calls.
- **Safety:** Unsupported values fail closed; prohibited actions stay denied.

## Decision

- **Proceed:** Yes, assessment complete; implementation not yet validated.
- **Rationale:** Same mandate and supported enforcement as AUT-PRE-001, but
  a distinct protected-action approval requirement and accountable role.
- **Review date:** 2026-10-07
- **Sources:** [Paired assessment](../AUT-PRE-001_autonomy_boundary_undefined/ASSESSMENT.md),
  [FwF contract](../../../docs/governance-contract.md),
  [ACS](https://github.com/microsoft/agent-governance-toolkit/tree/main/policy-engine),
  [Foundry tools](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/function-calling),
  [GitHub OIDC](https://learn.microsoft.com/en-us/azure/developer/github/connect-from-azure-openid-connect),
  [Azure Policy](https://learn.microsoft.com/en-us/azure/governance/policy/concepts/definition-structure-policy-rule).
  Retain the existing ACS beta limitation; do not claim new capabilities without a probe.