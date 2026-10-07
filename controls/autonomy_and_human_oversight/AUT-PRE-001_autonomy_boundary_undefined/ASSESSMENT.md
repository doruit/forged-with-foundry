# AUT-PRE-001 - control assessment

## Candidate

- **Control ID:** AUT-PRE-001
- **Name:** Autonomy boundary undefined
- **Lifecycle phase:** Pre-Live
- **Accountable role:** AI Governance

## Governance problem

- **Risk:** A technically available tool is mistaken for authority to act.
- **Control objective:** Require an explicit mandate and target scope for every
  tool in the actual release candidate, with unknown actions denied by default.
- **Authoritative signal:** The reviewed mandate attachment and the tool
  definitions built from the candidate's actual Foundry definition.
- **Required decision:** Block release if the mandate, scope or tool coverage
  is incomplete or inconsistent with that candidate.
- **Required governance action:** Return a reason-coded AUT-PRE-001 finding;
  do not publish code or an agent version after a failed gate.
- **Required evidence:** Control/policy version, mandate and candidate hashes,
  decision/reason, blocked or permitted release action, verification, timestamp,
  correlation and accountable role. Hashes are not authenticated signatures.

## Enforcement classification

- **Deterministic policy:** Existing Conftest/Rego evaluates the declaration
  against the built tool candidate; JSON Schema owns structural validity.
- **Model-assisted evaluation:** Not used; a model cannot certify its mandate.
- **Human approval:** Review metadata records the declared review; a protected
  GitHub release environment supplies a separate authenticated release event.
- **Configuration assessment:** Primary decision surface.
- **Monitoring/detection:** Not a monitoring control.
- **Required fail-closed behavior:** Missing/empty/invalid source, unsafe path,
  unknown/duplicate tools, conflicting scope, hash mismatch or gate failure
  prevents release. Prohibited actions cannot become allowed through approval.
- **Model/Foundry role:** Not used - not applicable to the release decision.
  Foundry is the real deployment target; AUT-002 governs its later tool calls
  through ACS. No explanatory agent is added.

## Existing capability review

| Capability | Applicable? | Existing capability | Composition decision |
|---|---|---|---|
| Microsoft Agent Governance Toolkit | Yes, downstream | ACS governance capability family | Reuse AUT-002 rather than create another runtime. |
| Agent Control Specification | Yes, downstream | Tool-boundary enforcement and action identity | Compile checked declaration into the existing ACS dispatcher configuration. |
| Microsoft Foundry | Yes | Registered prompt-agent definitions and function tools | Build and deploy the actual definition; do not validate a disconnected inventory. |
| Foundry Control Plane | No | Platform governance features | Does not validate this repository-owned declaration or discover governance.yaml. |
| Azure API Management AI Gateway | No | API admission policies | No extra gateway is needed for a release declaration. |
| Microsoft Purview | No | Data governance | Not the mandate authority for this synthetic scope. |
| Microsoft Defender | No | Security detection | No new security telemetry learning outcome. |
| Microsoft Entra | Yes, cloud path | Managed identity and OIDC federation | Separate bootstrap, release and runtime authority. |
| Azure AI Content Safety / Language | No | Content evaluation | Does not determine delegated authority. |
| Azure Monitor / Application Insights / OTel | No new resource | Telemetry | Minimized existing gate evidence is sufficient. |
| Other supported Microsoft capability | Yes | Azure Policy ARM deny | Demonstrate scoped missing-status denial independently; it does not inspect the mandate or agent data-plane calls. |

## Existing samples and implementations

| Source | Reuse | Remaining gap |
|---|---|---|
| Shared governance-contract validator and deployment gate | Discovery, schema validity, required-control coverage and evidence | Safe attachment resolution and candidate-tool comparison. |
| VAL-PRE-002 candidate/OIDC workflow | Credential-free gate before protected release | Deploy the AUT-002 candidate rather than a standalone teaching resource. |
| AUT-002 and QLT-001 Foundry function definitions | Supported SDK serialization and real tool execution shape | Bind the checked mandate to the published package and agent definition. |

## Repository overlap

- **Related controls:** AUT-PRE-002 checks human gates, not mandate coverage.
  TOOL-PRE-001/002 remain planned inventory/risk inputs, not prerequisite code.
- **Reuse:** Existing JSON Schema, duplicate-safe parser, Rego, gate evidence,
  AUT-002 webapp/agent/identity and ownership-checked cleanup.
- **Duplication risk:** Avoid two action matrices, review screens or validators.

## Proposed contribution

- **Classification:** COMPOSE
- **Demo format:** HYBRID_DEMO
- **Deployment:** Local feedback needs no Azure. The real Azure/Foundry release
  is required for completion of the paired cloud learning outcome.
- **Capabilities reused:** Shared FwF gate, Conftest/Rego, Foundry SDK, ACS,
  Entra OIDC and Azure Policy.
- **Visible role:** Missing mandate blocks the actual candidate; a passing
  candidate is released and its runtime consumes the same checked declaration.
- **Minimum custom artifacts:** One declaration attachment resolver, bounded
  candidate/configuration adapter, schemas, fixtures and release wrapper.
- **Unique learning outcome:** Access is not authority; the candidate's entire
  tool surface needs an explicit mandate before publication.
- **Distinct learning beyond samples:** Link reviewed configuration to real
  released tool definitions, not merely an approved-status tag.
- **Separate control justification:** A complete inventory or approval list
  cannot establish the agent's business scope.
- **Deployment justification:** Cloud publication and identity cannot be
  proven by local fixtures alone; reuse the existing AUT-002 resources.

## Smallest useful design

- **Primary decision:** Is the candidate covered by a reviewed default-deny mandate?
- **Authority:** AI Governance for mandate review; shared Rego gate for release.
- **Signal:** One versioned source, read and hashed once, plus the built tool definition.
- **Enforcement:** Existing deployment gate before ARM, SDK and ZIP publication.
- **Evidence source:** Existing gate artifact and later verified runtime metadata.
- **ACS point:** AUT-002 pre_tool_call/post_tool_call consume the checked scope.
- **AGT capability:** Existing ACS dispatcher, not a parallel policy engine.
- **Azure services:** Existing Foundry project/model/agent and App Service;
  add only scoped Policy/federation configuration needed for release proof.
- **Action:** Block release and identify missing mandate/coverage.
- **Artifact:** Metadata-only gate evidence with exact source/candidate hashes.
- **Healthy:** One mandate covers allowed, prohibited and conditional synthetic actions.
- **Trigger:** Missing scope or an undeclared exposed tool.
- **Ambiguous:** Missing attachment, unsafe reference, unsupported scope or changed hash.

## Complexity budget

- **Custom necessity:** Resolve a bounded local attachment and join the real SDK
  definition to standard schema/Rego checks. No custom expression language.
- **Invoked artifacts:** One combined candidate under this control, fixtures,
  schemas and tests; AUT-PRE-002 references it rather than copying it.
- **Omitted:** New agent, database, review application and duplicate approval store.
- **No shadow evidence:** Gate uses exact checked bytes; release publishes those bytes.
- **Edge cases:** Missing, empty, malformed, duplicate, path-escaping and valid
  declarations; independent control entries and profiles remain supported.

## Community fit

- **Level:** Intermediate
- **Time:** Establish after running both local and cloud procedures.
- **Prerequisites:** Python 3.12, pinned Conftest; Azure/Entra/GitHub permissions
  only for the cloud path. User authorization required for external publication.
- **Accessibility:** One mandate review, two findings, existing cloud workload.
- **Simplifications:** Synthetic bounded scope, declared review metadata rather
  than signed business attestation, existing project role limitations.
- **Further exploration:** Rich scope operators, durable attestations and other pipelines.
- **Optional path:** Credential-free local candidate assessment.

## Scope boundary

- **Included:** Mandate completeness, actual-tool coverage, source binding and gated release.
- **Excluded:** General policy DSL, universal tool interception, legal compliance
  and authenticated truth of manually declared review evidence.
- **Proof required:** Negative candidate causes no workload mutation; positive
  exact candidate releases to Azure/Foundry and exposes the checked version.
- **Non-claims:** Azure tags do not prove the gate ran; hashes are not signatures;
  ARM Policy does not govern Foundry data-plane publication or ZIP uploads.
- **Safety:** Correct only within the bounded declared tool surface and trusted
  release wrapper; unsupported values fail closed.

## Decision

- **Proceed:** Yes, assessment complete; implementation not yet validated.
- **Rationale:** Compose existing release and runtime capabilities into one
  mandate workflow, preserving two distinct control decisions.
- **Review date:** 2026-10-07
- **Sources:** [FwF architecture](../../../docs/governance-contract.md),
  [Foundry function calling](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/function-calling),
  [Entra GitHub OIDC](https://learn.microsoft.com/en-us/azure/developer/github/connect-from-azure-openid-connect),
  [Azure Policy rules](https://learn.microsoft.com/en-us/azure/governance/policy/concepts/definition-structure-policy-rule),
  [ACS](https://github.com/microsoft/agent-governance-toolkit/tree/main/policy-engine).
  Retain the repository's pinned ACS beta dependency; do not claim GA from its availability.