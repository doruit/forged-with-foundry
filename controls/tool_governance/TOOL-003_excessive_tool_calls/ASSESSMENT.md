# TOOL-003 — control assessment

Part of the **runaway agent kill switch** bundle: TOOL-003 (per-task tool-call
budget) → [RUN-006](../../runtime_and_operations/RUN-006_agent_loop_or_retry_storm/ASSESSMENT.md)
(loop or retry-storm stop) → [AUT-004](../../autonomy_and_human_oversight/AUT-004_emergency_stop_not_enforced/ASSESSMENT.md)
(human emergency stop). Each control remains independently runnable.

## Candidate

- **Control ID:** TOOL-003
- **Name:** Excessive tool calls
- **Lifecycle phase:** Live
- **Accountable role:** AI Ops Lead

## Governance problem

- **Risk:** An agent completes, or keeps attempting, a task with far more tool
  calls than the workflow was approved for. Each extra call adds cost, load on
  downstream systems and more chances for a wrong state change. Nobody notices
  because every individual call looks legitimate.
- **Control objective:** Enforce the approved tool-call budget for a task type
  at the tool boundary, before the call that would exceed it runs, and route
  the overrun to the AI Ops Lead as a workflow-optimization finding.
- **Authoritative signal:** The number of `pre_tool_call` evaluations already
  admitted by ACS in the current run, compared with the approved budget for
  the run's declared task type. The host supplies this history to ACS as
  `$snap.prior_decisions`, taken from the run journal described under
  *Smallest useful design*.
- **Required decision:** Allow the next tool call only while admitted calls in
  this run are below the approved budget for the declared task type. Deny the
  call that would exceed the budget.
- **Required governance action:** Deny the over-budget call before execution,
  end the run with a safe handoff message, and record a workflow-optimization
  finding in the evidence for the AI Ops Lead to review (no notification is
  sent in this demo).
- **Required evidence:** Control ID and policy version, task type, approved
  budget and its source (governance contract version), admitted call count,
  denied tool name (no arguments), decision and reason, run correlation ID,
  timestamp and accountable role.

## Enforcement classification

- **Deterministic policy:** Yes. Count compared with an approved integer budget.
- **Model-assisted evaluation:** No. The model proposes calls; it never decides
  or sees the budget.
- **Human approval:** No inline approval. The budget itself is a human-approved
  declaration in the governance contract.
- **Configuration assessment:** Yes, at startup: the declared task type and its
  budget must exist and be a positive integer, or the run does not start.
- **Monitoring/detection:** No. The finding is produced by the enforcement path
  itself. Trend monitoring across runs is optional further exploration.
- **Required fail-closed behavior:** Missing, empty, zero, negative,
  non-integer or unknown task-type budgets deny at `agent_startup`. A missing or
  malformed `prior_decisions` snapshot denies at `pre_tool_call` (ACS missing
  required path). Policy errors deny.
- **Model/Foundry role:** `Active — governed subject`. A registered Foundry
  prompt agent emits real function calls; every call passes through ACS
  `pre_tool_call` before the synthetic tool runs. Tool-governance signals are
  inline agent behavior, so Active is the required posture.

## Existing capability review

Review date: 2026-11-13.

| Capability | Applicable? | What it already provides | Role in the core demo or reason not used |
|---|---:|---|---|
| Microsoft Agent Governance Toolkit | Partly | Per the AGT repository source tree reviewed 2026-11-13 (not executed): `agentmesh/governance/budget.py` enforces token and USD budgets over a rolling window before each LLM call; `agent-sre` provides circuit breakers. | Not used for the count: it budgets tokens and cost, not tool calls per task. Using it would add a second budget engine beside ACS. Recorded as further exploration for a token budget. |
| Agent Control Specification | Yes | Stateless, fail-closed `agent_startup` and `pre_tool_call` evaluation; host-supplied `$snap.prior_decisions`; OTel decision counters. | **Primary enforcement surface.** The budget policy is the ACS policy dispatcher. ACS explicitly leaves counters and quotas to the host, so the host passes the run's prior ACS decisions in the snapshot rather than keeping a separate counter. |
| Microsoft Foundry | Yes | Registered prompt agents and Responses function calling. `max_tool_calls` is described in the preview `Azure.AI.AgentServer.Contracts` reference as limiting **built-in** tools only. | Supplies the governed agent. Re-checked 2026-11-14: the Foundry REST reference lists `max_tool_calls` without defining its scope. With function tools, each host round trip is a new response, so a per-response cap cannot bound a whole run. The host-side ACS gate is still required. |
| Foundry Control Plane | No | Agent inventory, stop/start for published or hosted agents, block for custom agents. | Whole-agent lifecycle, not a per-task budget. Covered as the agent-level layer in AUT-004. |
| Azure API Management AI Gateway | No | `llm-token-limit` (429/403) per counter key on model traffic. | Counts model tokens, not tool calls. A token brake belongs to FIN-001/FIN-003/FIN-004. |
| Microsoft Purview | No | Data governance. | Not applicable to call volume. |
| Microsoft Defender | No | Threat detection. | Overuse here is a workflow defect, not an attack; SEC-006 owns abnormal usage. |
| Microsoft Entra | No | Identity. | The local runner uses the operator's credential for Foundry only; no authority decision depends on identity. |
| Azure AI Content Safety / Language | No | Content analysis. | Not applicable. |
| Azure Monitor / Application Insights / OTel | Optional | ACS ships an OTel decision counter. | Not deployed in the core; RUN-006 owns the Monitor alert. The evidence record is produced directly by the enforcement path. |
| Governance contract (this repo) | Yes | `.fwf/agents/<agent-id>/governance.yaml` validated by `scripts/validate_governance_contract.py`. | **Source of the approved budget** per task type. The runtime reads the same validated contract; no second budget file. |

## Existing samples and implementations

| Repository, documentation, or sample | Overlap | What is still missing |
|---|---|---|
| AUT-002 (this repo) | ACS `run_tool` around a real Foundry function call; Foundry adapter; evidence minimization. | AUT-002 governs one irreversible action; it has no per-run budget. TOOL-003 reuses the adapter pattern and adds a count-based policy over `prior_decisions`. |
| ACS `stateless-runtime.md` | Defines `$snap.prior_decisions` as a recommended ambient field. | No sample enforcing a per-task call budget with it. |
| AGT `agentmesh/governance/budget.py` | Pre-call budget allow/deny. | Token/cost only; no tool-call count, no task-type declaration. |

## Repository overlap

- **Related controls:** RUN-006 stops a run whose calls *repeat without
  progress*; TOOL-003 limits the *number* of calls regardless of pattern.
  TOOL-001 (unauthorized tool) checks *which* tool, not how many. FIN-004
  measures the *cost* of failed retry runs after the fact. TOOL-PRE-002 (tool
  risk tier) is planned and does not declare budgets.
- **Distinguishing scenario matrix (shared with RUN-006):**

  | Run behavior | TOOL-003 | RUN-006 |
  |---|---|---|
  | 4 varied calls, budget 8 | allow | allow |
  | 11 varied, legitimate calls, budget 8 | **deny call 9** | allow (no repetition) |
  | Same failing call repeated 3×, budget 8 | allow | **stop run** |

- **Existing components that can be reused:** AUT-002 Foundry function-call
  adapter and ACS `run_tool` shape (copied and reduced, not imported across
  controls), evidence minimization conventions, shared Foundry account.
- **Risk of duplicating an existing demo:** Low. No implemented control
  enforces a declared call budget.

## Proposed contribution

- **Classification:** `ADAPT` — a small policy dispatcher and snapshot adapter
  around ACS and a real Foundry agent.
- **Demo format:** `DEPLOYABLE_DEMO` (runner executes locally against deployed
  Foundry resources).
- **Deployment:** Required for the core learning outcome (a real agent must
  produce the calls).
- **Existing capabilities reused:** ACS, Foundry prompt agent and Responses
  function calling, the governance contract and its validator.
- **How their role is made visible:** The transcript shows each ACS
  `pre_tool_call` verdict with the running count, and the denial of call N+1
  before the synthetic tool runs; evidence cites the contract version.
- **Minimum custom implementation:** One ACS manifest, one policy dispatcher,
  one snapshot builder that passes prior ACS decisions, three
  synthetic tools, a Foundry adapter, an evidence writer, deploy and cleanup
  scripts, tests.
- **Unique learning outcome:** A budget in the prompt is a suggestion; a budget
  at the tool boundary is a control. ACS is stateless by design, so the
  application must hand it the run's history — and the budget must come from
  an approved declaration, not from code.
- **Why deployment is justified:** Only a real model shows that the agent
  itself chose the extra calls; a scripted list would prove nothing about the
  agent. A credential-free scripted replay stays as the regression path.
- **Why App Service is not used:** No authority decision depends on a hosted
  identity here. A local runner keeps the demo cheaper and simpler.

## Smallest useful design

- **Primary governance decision:** May this tool call run, given how many calls
  this run has already been admitted and the approved budget for its task type?
- **Authoritative human role or system:** ACS is the enforcement system; the
  AI Ops Lead owns the approved budget in the governance contract.
- **Signal source:** Count of admitted `pre_tool_call` decisions in the run.
- **Authoritative decision or enforcement surface:** ACS `agent_startup`
  (budget declared and valid) and `pre_tool_call` (count < budget).
- **Authoritative evidence source:** The ACS verdict returned to the runner,
  written once per run by the evidence writer.
- **Run journal (host-owned state):** ACS is stateless and does not maintain
  or validate history, so the host keeps one ordered, append-only journal per
  run. Each entry records an ACS evaluation (`seq`, intervention point,
  decision, tool name, action identity) and is appended **before** the tool
  executes. Tool calls within a run are evaluated and admitted one at a time;
  parallel tool calls in one model response are processed sequentially. The
  journal is the only input to `prior_decisions`; it is not a second policy
  engine. Its integrity is trusted host state, not something ACS guarantees,
  and the README says so. Tests cover empty, truncated, duplicated and
  cross-run journal entries.
- **Counting boundary:** With budget *B*, calls 1…*B* are admitted and call
  *B*+1 is denied. Denied calls do not consume budget.
- **AGT capability:** ACS via `AgentControl.run_tool`.
- **Foundry/Azure services:** Shared Foundry account; control-owned project,
  model deployment and prompt agent `support-refunds-agent` (synthetic Contoso
  support scenario: `lookup_order`, `issue_refund`, `reply_to_ticket`).
- **Governance action:** Deny call N+1, return a safe handoff message, record a
  workflow-optimization finding for the AI Ops Lead.
- **Evidence artifact:** Minimized JSON per run under the control's
  `evidence/` folder (git-ignored).
- **Healthy scenario:** A normal refund question completes within budget.
- **Policy-triggering scenario:** A multi-order request that legitimately needs
  more calls than approved is denied at call N+1.
- **Unavailable or ambiguous scenario:** The contract has no budget, an invalid
  budget, or an unknown task type: the run is denied at `agent_startup` before
  any model call.

## Complexity budget

- **Why each custom component is necessary:** The dispatcher holds the only
  control-specific rule; the snapshot builder is required because ACS keeps no
  state; the Foundry adapter joins function calls to ACS; deploy/cleanup track
  owned resources.
- **Interfaces, agents, stores or resources omitted:** No web app, Chainlit,
  database, Monitor resource, APIM or second agent.
- **How shadow evidence is avoided:** The count is derived from the run
  journal of ACS's own admitted decisions, not from an independent counter;
  the evidence writer records the ACS verdict and never re-decides.
- **Metadata edge cases:** Test missing, empty, zero, negative, non-integer and
  valid budgets; unknown task type; missing `prior_decisions`.

## Community fit

- **Learning level:** Intermediate
- **Estimated completion time:** Establish after the first end-to-end run.
- **Minimum prerequisites:** Azure CLI, Python 3.12, shared `infra/` deployed,
  Foundry model quota.
- **Why accessible:** One agent, one budget, one denial, one local command.
- **Intentional simplifications:** The budget counts all tool calls equally;
  per-tool weights are out of scope. Run history is per process and lost on
  restart (a restarted run starts a new budget — documented limitation).
- **Further exploration:** AGT token budget alongside the call budget;
  App Insights trend of overruns per task type; per-tool weighting.

## Scope boundary

- **Included:** One task-type budget from the contract, enforced at ACS
  `pre_tool_call` for one real agent.
- **Explicitly excluded:** Token or cost budgets, cross-run or per-user quotas,
  built-in Foundry tools (which never reach the host).
- **What the demo proves:** ACS can deny the over-budget call before it
  executes when the host supplies run history, and a missing budget prevents
  the run from starting.
- **What the demo does not prove:** That the budget is the right number, that
  tools outside the ACS path are counted, protection across process restarts,
  or integrity of the host-supplied journal (ACS evaluates what it is given).
- **Is the core control correct and safe within this boundary?** Yes, provided
  every function call goes through `run_tool` and invalid budgets fail closed.

## Decision

- **Proceed / revise / reject:** Proceed.
- **Rationale:** No supported capability counts host-executed function calls
  per task; ACS is the documented enforcement surface and explicitly delegates
  counters to the host. The control is distinct from RUN-006 by the scenario
  matrix above.
- **Review date:** 2026-11-13
- **Quality bar (agreed 2026-11-14):** Target `Validated`, not `Implemented`: a real Azure end-to-end run in the documented order, captured screenshots or transcripts for every scenario, verified control-owned cleanup, an independent code review per control, and a control-demo-roast before any announcement. The assessment was revised after an independent design review on 2026-11-14.
- **Authoritative references:**
  - [ACS stateless runtime guide](https://github.com/microsoft/agent-governance-toolkit/blob/main/policy-engine/docs/stateless-runtime.md)
  - [Agent Governance Toolkit](https://github.com/microsoft/agent-governance-toolkit)
  - [`max_tool_calls` in the preview AgentServer contract (built-in tools only)](https://learn.microsoft.com/en-us/dotnet/api/azure.ai.agentserver.contracts.generated.responses.createresponserequest.maxtoolcalls?view=azure-dotnet-preview)
  - [Foundry function calling](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/function-calling)
  - [FwF governance contract](../../../docs/governance-contract.md)
