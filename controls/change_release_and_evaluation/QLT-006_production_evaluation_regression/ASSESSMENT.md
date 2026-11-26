# QLT-006 — control assessment

Completed before any exercise artifact, implementation code or
infrastructure was created. Reviewed 26 November 2026, after Microsoft
Ignite 2026.

## Candidate

- **Control ID:** QLT-006
- **Name:** Production evaluation regression
- **Lifecycle phase:** Live
- **Accountable role:** QA Lead

## Governance problem

- **Risk:** An agent passed its release checks, but weeks later it scores
  worse on the same tests. Nothing in the agent's model was formally
  changed: its instructions were edited outside the model gate, a tool or
  backend changed, or the model deployment upgraded itself. Without a
  repeat measurement against the release baseline, the drop stays invisible
  until users complain.
- **Control objective:** Re-evaluate the live agent version against the
  approved release baseline, and open a change cycle when the pass rate
  drops by more than the contract threshold.
- **Authoritative signal:** Foundry Evaluations run (GA) of the *live* agent
  version on the release dataset, compared with the release baseline record
  produced by CHG-002.
- **Required decision:** Is the live agent within tolerance of its release
  baseline, regressed, or not measurable?
- **Required governance action:** Open (or update) a "change cycle required"
  GitHub issue owned by the QA Lead, and verify it exists.
- **Required evidence:** baseline reference (record path, SHA-256, agent
  version, dataset hash), live agent version, evaluation run ID, pass rate
  per evaluator, delta in percentage points, completeness counts, threshold,
  decision and reason, issue reference, timestamp, correlation ID,
  accountable role.

## Enforcement classification

- **Deterministic policy:** Yes: delta versus the contract's
  `regressionThresholdPp`, with minimum samples and completeness checks.
- **Model-assisted evaluation:** Yes, Foundry built-in evaluators score
  each response. They never decide.
- **Human approval:** Not required to open the change cycle. Closing it is
  the QA Lead's decision.
- **Configuration assessment:** No.
- **Monitoring/detection:** Yes: this is a monitoring control.
- **Required fail-closed behavior:** A missing or tampered baseline record,
  a live version or dataset that differs from the baseline, too few scored
  items, errored items or an invalid contract produce `measurement_failed`,
  never "healthy". A measurement failure is routed too.
- **Model/Foundry role:** `Monitored workload`. The real Foundry agent
  serves the evaluation queries; the decision evaluates accumulated results
  asynchronously. ACS is not the surface: no inline agent action is gated.

## Existing capability review

| Capability | Applicable? | What it already provides | Role in the core demo or reason not used |
|---|---:|---|---|
| Microsoft Agent Governance Toolkit | No | Runtime policy | No runtime action governed. |
| Agent Control Specification | No | Intervention points | Asynchronous, window-based decision. |
| Microsoft Foundry Evaluations (agent target) | Yes | Runs fixed queries against a named agent version and scores them with built-in evaluators (GA; `AzureAIAgentTargetParam` in `azure-ai-projects` 2.3.0) | Core: the authoritative signal. |
| Foundry scheduled dataset evaluation rule | Partly | Foundry-native timer for the same run (GA) | Further exploration: needs `azure-ai-projects>=2.11.0` (repository pins 2.3.0 for all controls) and a connected Application Insights resource ([how-to](https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/continuous-scheduled-evaluation)). The demo starts the identical run on demand. |
| Foundry continuous evaluation | Partly | Scores production responses as they complete (GA) | Not used: needs Application Insights and production traffic; QLT-001 already demonstrates it. |
| Foundry insights from production traces | Partly | Groups recurring failures (GA) | Further exploration: decision support only per Microsoft, needs SDK 2.11+ and App Insights ([how-to](https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/agent-insights)). |
| Multi-turn (conversation) evaluation | Partly | Scores whole conversations (GA) | Not used: the support agent answers single-turn requests; the decision must name failing items. |
| Agent Monitoring Dashboard | Yes | Shows evaluation results per agent in the portal (GA) | Inspect in Azure only. |
| Foundry Control Plane | No | Fleet view | One agent. |
| Azure API Management AI Gateway | No | Traffic | Not applicable. |
| Microsoft Purview / Defender | No | Data and threat protection | Not applicable. |
| Microsoft Entra | Yes | Keyless sign-in | Authentication only. |
| Azure AI Content Safety / Language | No | Filters | Not applicable. |
| Azure Monitor / Application Insights | No (core) | Alerting | Not needed: the decision is deterministic and routed directly. |
| GitHub Issues | Yes | Owned, auditable work item | Core governance action: "change cycle required". |

## Existing samples and implementations

| Repository, documentation, or sample | Overlap | What is still missing |
|---|---|---|
| [Continuous and scheduled evaluation](https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/continuous-scheduled-evaluation) | Scheduled dataset runs | Comparison with an approved release baseline and a routed decision |
| QLT-001 (this repository) | Evaluation results to a deterministic, routed decision | Baseline comparison; QLT-001 uses an absolute rate |
| CHG-002 (this repository) | Same agent, dataset and evaluators | QLT-006 runs after release, on the live version |

## Repository overlap

- **Related controls:** CHG-002 (produces the baseline), QLT-001 (absolute
  groundedness rate in production), CHG-001/003/004 (other change types this
  control can catch after the fact).
- **Reused components:** the release baseline record from CHG-002; the
  evaluation pattern is copied into this control's own folder (no shared
  code until more controls need it).
- **Duplication risk:** Low. QLT-001 measures an absolute quality rate;
  QLT-006 measures a change against a release baseline.

## Proposed contribution

- **Classification:** `COMPOSE`
- **Demo format:** `DEPLOYABLE_DEMO` (on top of the CHG-002 deployment)
- **Deployment:** Required: the live agent version must be evaluated.
- **Existing capabilities reused:** Foundry Evaluations with agent target,
  built-in evaluators, CHG-002 baseline record, GitHub Issues.
- **How their role is visible:** the evaluation run is visible in the
  Foundry portal; the issue is visible in GitHub; the decision prints the
  delta per evaluator.
- **Minimum custom implementation:** baseline loader with hash check, run
  launcher, deterministic policy, issue router with read-back verification,
  evidence writer.
- **Unique learning outcome:** "passed at release" is not "still good";
  regression is measured against the *approved* baseline, and changes that
  bypass the model gate are caught.
- **Why a separate demo:** different decision, owner and timing from
  CHG-002.
- **Why deployment is justified:** a real agent must answer the queries.

## Smallest useful design

- **Primary governance decision:** within tolerance, regressed, or not measurable.
- **Authoritative human role:** QA Lead.
- **Signal source:** Foundry Evaluations run on the live agent version.
- **Decision surface:** QLT-006 policy with the threshold from the governance contract.
- **Evidence source:** QLT-006 evidence file.
- **Governance action:** GitHub issue, verified by reading it back.
- **Healthy scenario:** live version equals the released version and is within tolerance.
- **Policy-triggering scenario:** a new agent version with degraded instructions
  (a prompt change, outside CHG-002's model-only scope) is published; QLT-006
  measures a drop above the threshold.
- **Unavailable/ambiguous scenarios:** baseline missing or hash mismatch,
  too few scored items, errored run: `measurement_failed`.

## Complexity budget

- **Custom components:** only decision logic and routing that Foundry does
  not provide.
- **Deliberately omitted:** App Insights, continuous evaluation, Foundry
  scheduler, alerts, Teams.
- **Shadow evidence avoided:** the baseline is the CHG-002 record, verified
  by SHA-256; no second baseline is computed.
- **Metadata edge cases:** missing, empty, invalid and valid values for
  `regressionThresholdPp`, `minSamples` and the baseline reference are tested.

## Community fit

- **Learning level:** Intermediate
- **Estimated time:** 20-30 minutes after CHG-002 (to be measured live)
- **Prerequisites:** CHG-002 deployed; GitHub CLI signed in to a repository
  where issues may be created.
- **Intentional simplifications:** on-demand run instead of a scheduler;
  synthetic single-turn queries; one agent.
- **Further exploration:** scheduled dataset rule, continuous evaluation,
  insights as investigation context, human annotation of traces (preview).

## Scope boundary

- **Included:** regression of the live agent version versus its release baseline.
- **Excluded:** absolute quality thresholds (QLT-001), root-cause analysis,
  automatic rollback.
- **Proves:** a drop above the contract threshold is detected and routed to
  an owned issue; incomplete measurement is never reported healthy.
- **Does not prove:** that the dataset represents real users, that the LLM
  judge is correct, or detection between runs.
- **Correct and safe within this boundary:** yes.

## Decision

- **Proceed.**
- **Rationale:** a distinct monitoring decision that completes CHG-002's
  story, using GA evaluation capabilities available in the pinned SDK.
- **Review date:** 26 November 2026
- **Authoritative references:** [Microsoft Ignite 2026 Book of News](https://news.microsoft.com/events/ignite/2026/book-of-news/),
  [continuous and scheduled evaluation](https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/continuous-scheduled-evaluation),
  [insights](https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/agent-insights),
  [evaluation overview](https://learn.microsoft.com/en-us/azure/foundry/concepts/evaluation-overview).
