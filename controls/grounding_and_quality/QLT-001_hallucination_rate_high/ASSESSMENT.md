# `QLT-001` — control assessment

Complete this assessment before creating exercise artifacts, implementation
code, or infrastructure.

> **Revision note (2026-09-23, same-day cross-check):** The first pass of
> this assessment proposed a bespoke runner script that batch-called
> `GroundednessEvaluator` directly against a synthetic fixture. A follow-up
> cross-check against current Microsoft Foundry documentation found that
> Foundry Observability's **Continuous Evaluation** (GA, March 2026) already
> scores sampled live agent traffic for groundedness and writes the scores
> next to traces in Application Insights — the exact "detect it, keep
> detecting it" capability this control needs, already reused by the
> repository's own `VAL-001` monitored-workload pattern. Reusing that
> capability instead of re-implementing an evaluator call removes the
> largest custom component from the original design and better satisfies the
> one-authoritative-path rule. This revision reflects that correction
> throughout.

> **Revision note 2 (2026-09-23, SDK verification against the installed
> package):** Inspecting the actually-installed `azure-ai-projects` 2.3.0
> source directly (not blog summaries) confirmed continuous evaluation is
> fully controllable end to end: `client.evaluation_rules.create_or_update()`
> creates the rule (`EvaluationRule` + `ContinuousEvaluationRuleAction`,
> confirmed REST path `PUT /evaluationrules/{id}`), and the underlying "Eval"
> definition that groups the groundedness evaluator is created through the
> OpenAI-compatible Evals API exposed via `client.get_openai_client().evals`
> (real, installed `openai` 2.54.0 package: `evals.create/list/retrieve` and
> `evals.runs.create/list/retrieve`). This also surfaced a genuine, sourced
> caveat: `evaluation_rules.create_or_update()` requires
> `AIProjectClient(..., allow_preview=True)`, which sends a
> `Foundry-Features: Evaluations=V1Preview` header covering the whole
> Evaluations v1 surface, and the client's own docstring states "Do not use
> preview features in production code, as they are subject to change or
> removal without notice." Continuous Evaluation as a product capability is
> marketed GA (March 2026), but this SDK version's programmatic configuration
> path for it is not — those are two different claims and only the first is
> currently backed by a GA statement. The design below treats the Foundry
> portal's "Set up continuous evaluation" flow as the primary, disclosed
> core-path step (an actionable UI procedure, consistent with this
> repository's own rule for external configuration that cannot be
> automated), and the SDK route as an explicitly labeled, optional preview
> automation extension — not the documented core path — until the SDK
> surface's own GA status can be confirmed against a live project.

> **Revision note 3 (2026-09-23, real live deployment): Continuous
> Evaluation does not support hosted agents — confirmed, not preview lag.**
> A real Foundry project, hosted agent (`it-helpdesk-kb-assistant`), and
> model deployment were deployed for real (an internal Capgemini Azure
> subscription; no client, tenant, or subscription identifier is recorded
> here — see the repository's confidentiality conventions) to validate
> revision note 2's design. `client.evaluation_rules.create_or_update()`
> rejected the rule
> with `400 UserError: The agent 'it-helpdesk-kb-assistant' is of kind
> 'hosted', which is not supported for evaluation rules. Hosted and
> external agents are not supported.` — reproduced identically on both the
> repository-pinned `azure-ai-projects` 2.3.0 and the newest available
> 2.7.0, ruling out an SDK-version explanation. Microsoft has already
> publicly acknowledged this: "tracing and evaluations in Foundry reached
> general availability with hosted agents coming soon" (found via search
> across Microsoft Foundry Blog "What's New" posts; a specific single
> source page was not independently fetched and should be re-confirmed
> before citing further — see `docs/UPSTREAM-FEEDBACK.md` for the full,
> reframed writeup and a status-check draft for Microsoft).
>
> What **was** proven to work end to end against the same real hosted
> agent: `azd ai agent eval generate` / `eval run` (Microsoft's own
> documented "Evaluate your hosted agent" quickstart path) completed for
> real (`eval_7d6f92ce50814f748db14dead058af6e`,
> `evalrun_1d7086540dc14409a59afc63abd8da8e`, 15/15 passed), and per-item
> `passed`/`score`/`reason` results are readable via
> `openai_client.evals.runs.output_items.list(eval_id, run_id)` (also
> requires `allow_preview=True` — same disclosed preview dependency as
> revision note 2, now unavoidable since it is the only working mechanism).
>
> **Design pivot:** QLT-001's authoritative signal source changes from
> Continuous Evaluation to **periodic batch evaluation** triggered per
> measurement window (`azd ai agent eval run` + `output_items.list()`),
> until hosted-agent support for Continuous Evaluation ships. This keeps the
> same Monitored-workload posture, the same underlying groundedness
> evaluator technology, and the same deterministic rate/critical-item/
> fail-closed policy in `evaluator.py` — only the trigger changes from
> automatic/continuous to explicitly triggered per window. See `README.md`
> for the updated Implementation/Demo sections and `docs/IMPLEMENTATION.md`
> for the corrected technical detail.

> **Revision note 4 (2026-09-23, second live pass — a genuine breach and a
> documentation-quality pass):** A second, deliberately adversarial batch
> evaluation run (regenerated dataset targeting the degraded-knowledge-base
> windows specifically) reproduced a real breach live: 19 items, 8 passed,
> 11 failed on the `groundedness` criterion, with 2 items erroring rather
> than scoring (excluded from the window and disclosed, per the fail-closed
> design). Building a window from the 17 successfully scored items and
> running the control's own policy and notification path produced a real
> `quality_review_required` decision and a real, accepted (`HTTP 202`) Teams
> card — see README.md "Demo". This run also surfaced that
> `builtin.groundedness` uses a materially different numeric score range
> than this control's own generated rubric evaluator (roughly 1-4 rather
> than 0.0-1.0 for the same named criterion), which changed the
> critical-item rule in `evaluator.py` from an absolute floor to a
> threshold-relative comparison (`score <= threshold * 0.5`) so it stays
> correct regardless of which evaluator scale is configured. A subsequent
> documentation-quality pass found that most sections below this note still
> described the pre-revision-note-3 Continuous Evaluation design as current;
> they have been corrected in place rather than left as a stale historical
> record, since (unlike the "Existing samples" and "Existing capability
> review" tables above, which are kept as an intentional record of what was
> researched) these sections describe the design going forward, not a
> point-in-time finding.

## Candidate

- **Control ID:** QLT-001
- **Name:** Hallucination rate high
- **Lifecycle phase:** Live
- **Accountable role:** Product Owner

## Governance problem

- **Risk:** A production agent keeps answering fluently even when its context
  (retrieved documents, tool output, conversation history) does not actually
  support the claim it makes. Nobody notices until a customer or auditor acts
  on a fabricated answer, because no one is counting how often this happens.
- **Control objective:** Continuously measure the share of agent responses
  that are *not* grounded in the context supplied to the agent, across a
  sampled window of real interactions, and force a quality review the moment
  that rate crosses an agreed threshold or a single critical hallucination is
  confirmed — regardless of how confident or fluent the response reads.
- **Authoritative signal:** Per-item groundedness `passed`/`score`/`threshold`
  results from a batch evaluation run (`azd ai agent eval run`, using the
  `builtin.groundedness` testing criterion) triggered against the hosted
  agent, aggregated into a rate over a defined, non-overlapping measurement
  window.
- **Required decision:** Is the aggregated hallucination rate for the window
  at or below the agreed threshold, and did the window contain a
  human-confirmed critical hallucination?
- **Required governance action:** `Quality review` — route the window's
  evidence and flagged item identifiers to the Product Owner; do not
  silently continue counting into the next window while a breach is open.
- **Required evidence:** Window identifier, sample size and completeness
  check against the batch evaluation run's own item count, per-item score
  and threshold band, aggregated rate, decision, and reviewer assignment —
  without raw prompts, full responses, or retrieved document content beyond
  what is needed to explain a flagged item.

## Enforcement classification

- **Deterministic policy:** Yes — the rate-vs-threshold comparison and the
  "any critical hallucination forces review" rule are deterministic code, not
  a model judgment. The batch evaluation run supplies the per-item score; the
  policy layer supplies the aggregation and gate rule.
- **Model-assisted evaluation:** Yes, and this is the control's core capability
  reuse — the `builtin.groundedness` testing criterion runs the same
  `GroundednessEvaluator`-family LLM-as-judge technology used by the offline
  Evaluation SDK, triggered explicitly per measurement window rather than
  sampled continuously (see revision note 3 for why: Continuous Evaluation
  does not support hosted agents). Its score is treated as untrusted
  measurement input to the deterministic policy, never as the governance
  decision itself.
- **Human approval:** The Product Owner's quality review clears the breach;
  the demo represents this as an explicit review record, not an automatic
  agent action.
- **Configuration assessment:** Not applicable to the primary path.
- **Monitoring/detection:** Yes — this is the primary classification. The
  control observes already-produced agent output; it does not intervene
  inline in the turn that produced it.
- **Required fail-closed behavior:** If the batch evaluation run has not
  scored an item, or reports an error for it (confirmed live: 2 of 19 items
  errored in a real adversarial run), the window must be reported as
  `evaluation incomplete` and excluded from a healthy-rate claim — never
  silently dropped from the denominator or counted as grounded.
- **Model/Foundry role:** `Monitored workload`. A real hosted Foundry agent
  produces the conversation traces being measured. The authoritative decision
  is computed asynchronously, after the fact, over a defined window, using a
  separate deterministic threshold policy — not an inline ACS intervention
  point gating the turn as it happens. This matches the template's
  Monitored-workload definition exactly, and mirrors the posture already
  approved for `VAL-001` in this repository: verifiable outcomes, an explicit
  measurement window, a completeness/deduplication check, and a separate
  deterministic monitoring decision. Model text (the judge's rationale) is
  never treated as proof by itself — only the structured score field is.

## Existing capability review

> Updated for revision note 3. The version of this table before the pivot
> away from Continuous Evaluation described Application Insights/KQL and the
> Foundry portal's continuous-evaluation flow as the core path; neither is
> part of the current implementation. This table reflects the real,
> live-verified batch-evaluation design.

| Capability | Applicable? | What it already provides | Role in the core demo or reason not used |
|---|---:|---|---|
| Microsoft Agent Governance Toolkit | No | Governance-plane wiring for contracts/policies across controls | Does not itself compute a groundedness verdict; this control still gets wired into the governance contract per `fwf-governance-contract.instructions.md`, but that is bookkeeping, not the core capability |
| Agent Control Specification | No | Eight inline intervention points (`agent_startup` … `agent_shutdown`) for gating a turn as it happens | Not applicable — this control's authoritative decision fires after a batch of turns has already completed, not inline on a single turn. Using an ACS intervention point here would misrepresent an asynchronous monitoring control as inline enforcement |
| Microsoft Foundry | Yes | Hosts the real hosted agent whose traffic is the monitored workload, and its batch/cloud evaluation (`azd ai agent eval`, confirmed live against a real `kind: hosted` agent) | Core: batch evaluation **is** the authoritative signal source for the core demo — see Proposed contribution. Continuous Evaluation was the original design but rejects hosted agents outright (confirmed live on two SDK versions; see `docs/UPSTREAM-FEEDBACK.md`) |
| Foundry Control Plane | No | Agent/model lifecycle and deployment governance | Batch evaluation configuration lives under Foundry Observability/Agent Service, not the Control Plane surface; not the signal source itself |
| Azure AI Evaluations v1 API (`azure-ai-projects`'s `evaluation_rules` and the OpenAI-compatible `evals`/`evals.runs`/`evals.runs.output_items` resources via `get_openai_client()`) | Yes | Confirmed-live, callable methods: `evaluation_rules.create_or_update()` for Continuous Evaluation rules (confirmed rejected for hosted agents), and `evals.runs.output_items.list()` for reading batch-evaluation per-item results (confirmed working, this control's actual retrieval mechanism) | Core for retrieval: `output_items.list()` is how `demo.py`/`evaluator.py` read real `passed`/`score`/`threshold` results. This still requires `allow_preview=True` (`Foundry-Features: Evaluations=V1Preview`) — a disclosed, currently-unavoidable preview dependency, since no non-preview alternative reads these results today |
| Azure API Management AI Gateway | No | Inline request/response mediation for API traffic | This control reads already-scored batch-evaluation results; it does not sit in the request path |
| Microsoft Purview | No | Data governance, sensitivity labeling | Not applicable to a groundedness rate signal |
| Microsoft Defender | No | Threat protection | Not applicable |
| Microsoft Entra | Yes | Managed identity for the hosted agent and `AzureCliCredential` for the evaluation API calls and Teams bearer token, matching repository convention (same role as in `VAL-001`) | Reused: no credential embedded in the demo |
| Azure AI Content Safety / Language | No (for this control) | Powers the separate real-time **Groundedness Detection Filter** on Azure OpenAI/Foundry content filtering (binary "Non-Reasoning" mode for low latency, or "Reasoning" mode with explanation) | This is the correct capability for the *inline* sibling control `RUN-001`, not for QLT-001's aggregate rate. Keeping them on different Microsoft capabilities (Content Filter vs. batch evaluation) keeps the two controls genuinely non-duplicative rather than both wrapping the same evaluator call |
| Azure Monitor / Application Insights / OTel | No (for the current core path) | An `infra/main.bicep` resource is deployable but not read by the current implementation; batch-evaluation results are read directly via `output_items.list()`, not via KQL | Not part of the core path; retained undeployed-by-default as a documented placeholder for if/when Continuous Evaluation adds hosted-agent support (see README.md's Continuous Evaluation note) |
| Other supported Microsoft capability | Yes | `builtin.groundedness` (an alias for `azure-ai-evaluation`'s `GroundednessEvaluator` family) as a testing criterion inside this control's `azd ai agent eval` configuration, confirmed to run and return real per-item results | This is the evaluator technology actually invoked, directly, by this control's own `eval.yaml` — not narrated through a separate platform capability |

## Existing samples and implementations

> The first three rows below describe capability research from before
> revision note 3's pivot away from Continuous Evaluation; they remain
> accurate as a record of what was researched and why it did not end up as
> the core path, but "this control's KQL query" and "Continuous Evaluation"
> in the "What is still missing" column no longer describe the current
> implementation — see revision note 3 and `docs/IMPLEMENTATION.md` for the
> batch-evaluation design that replaced them.

| Repository, documentation, or sample | Overlap | What is still missing |
|---|---|---|
| [Generally Available: Evaluations, Monitoring, and Tracing in Microsoft Foundry — Microsoft Community Hub](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/generally-available-evaluations-monitoring-and-tracing-in-microsoft-foundry/4502760) | Confirms Continuous Evaluation scores sampled live traffic for groundedness (among other dimensions) and links results to Application Insights traces | Not applicable to a hosted agent (see revision note 3); this capability is not part of the current implementation |
| [Observability in Generative AI — Microsoft Foundry — Microsoft Learn](https://learn.microsoft.com/en-us/azure/foundry/concepts/observability) | Describes the evaluation/monitoring/tracing architecture Continuous Evaluation was originally going to read from | Superseded; the current implementation reads batch-evaluation output items instead (see revision note 3) |
| [Local Evaluation with the Azure AI Evaluation SDK — Microsoft Learn](https://learn.microsoft.com/en-us/azure/foundry-classic/how-to/develop/evaluate-sdk) | Shows calling `GroundednessEvaluator` directly over a dataset | Superseded as the primary path; kept only as background on what the underlying evaluator measures |
| [Groundedness Detection Filter — Microsoft Foundry — Microsoft Learn](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/content-filter-groundedness) | Real-time, inline detection — the capability for `RUN-001`, not QLT-001 | Not this control's gap; documented to keep the RUN-001/QLT-001 boundary explicit |
| [Quickstart: Evaluate your hosted agent — Microsoft Learn](https://learn.microsoft.com/en-us/azure/foundry/observability/quickstarts/quickstart-evaluate-hosted-agent) | The official, documented `azd ai agent eval` batch-evaluation path this control's current implementation actually uses, confirmed working live against a real hosted agent (revision note 3) | No control contract: no rate-vs-threshold policy, no critical-item override, no fail-closed behavior on incomplete/errored items, no Quality-review gate action or accountable-role evidence record |
| `controls/value_adoption_and_finops/VAL-001_kpi_underperformance/ASSESSMENT.md` (this repository) | Established, already-approved Monitored-workload pattern: hosted Foundry agent → deterministic Python evaluator → decision + evidence + notification | QLT-001 reuses the same architectural pattern with a different metric (groundedness rate vs. deflection rate), a different evidence source (batch-evaluation output items, not Application Insights/KQL), and a different evidence detail (critical-item override) |

Reviewed 2026-09-23 against current Microsoft Learn and Microsoft Community
Hub pages for Microsoft Foundry Observability/Continuous Evaluation (GA,
March 2026) and Azure OpenAI's Groundedness Detection Filter. Re-check before
relying on this at implementation time, since these are recently-GA
capabilities and configuration details may still evolve.

## Repository overlap

- **Related Forged with Foundry controls:**
  - `RUN-001` (`runtime_and_operations`) — *low confidence or grounding score*.
    Inline, per-turn signal (`<70%` or below policy band) that triggers
    immediate human review, accountable to the **Agent Owner**. This is the
    synchronous sibling of QLT-001, and the cross-check strengthened the
    boundary between them: RUN-001's natural capability is the real-time
    **Groundedness Detection Filter** on the model call itself; QLT-001's is
    Foundry's **batch/cloud evaluation** (`azd ai agent eval`), triggered per
    measurement window rather than inline on every turn. They map to two
    distinct Microsoft capabilities, not one evaluator call read two ways,
    which removes any risk of the two controls quietly becoming the same
    gate under different names.
  - `QLT-002` (*answer accuracy low*) — measures correctness against a
    validation/gold-answer set; a response can be accurate but ungrounded
    (lucky guess) or grounded but still wrong relative to a gold answer.
    Different evidence source (validation-set scoring vs. context-grounding
    scoring).
  - `QLT-005` (*citation support failure*) — narrower: whether an individual
    citation actually supports the specific claim it is attached to. QLT-001
    is the broader "is this response supported by its context at all" signal
    and does not require the response to carry citations.
  - `QLT-006` (`change_release_and_evaluation`, *production evaluation
    regression*) — compares evaluation metrics release-over-release; QLT-001
    is a standing runtime-rate monitor, not a regression-gate on deployment.
  - `VAL-001` (`value_adoption_and_finops`) — not a grounding control, but the
    architectural precedent this assessment follows for the
    Monitored-workload posture: hosted agent, deterministic evaluator,
    explicit `cannot_evaluate` handling. VAL-001's evidence source is
    Application Insights/KQL; QLT-001's is batch-evaluation output items
    (see revision note 3) — a deliberate divergence, not an oversight, since
    Continuous Evaluation (the capability that would have made KQL relevant
    for QLT-001 too) does not support hosted agents. QLT-001 reuses the
    pattern, not the code (different category, different metric, different
    evidence mechanism).
  - No category `ARCHITECTURE.md` exists yet for `grounding_and_quality`; this
    assessment is the first one for the category, so none was available to
    check for recorded shared-stream conflicts. Consider creating one once
    this control is implemented, mirroring
    `controls/value_adoption_and_finops/ARCHITECTURE.md`, so QLT-002/005/006
    do not later redefine the same batch-evaluation approach.
- **Existing components that can be reused:** The general shape of `VAL-001`'s
  evaluator (target/threshold reader, `cannot_evaluate` handling, evidence
  writer) as a structural reference; no code is shared directly since it
  lives in a different category, reads a different metric, and (per revision
  note 3) reads it through a different Microsoft capability.
- **Risk of duplicating an existing demo:** Low, provided the RUN-001
  boundary above (inline Content Filter vs. aggregate batch evaluation) is
  preserved if RUN-001 is implemented later; the two must not converge onto
  the same Microsoft capability.

## Proposed contribution

- **Classification:** `ADAPT`
- **Demo format:** `HYBRID_DEMO`
- **Deployment:** Required for the core learning outcome (a real hosted
  Foundry agent and its batch evaluation are needed; without them there is
  no authoritative score, only a reimplemented judge)
- **Existing capabilities reused:** Microsoft Foundry hosted agent runtime,
  and Foundry's batch/cloud evaluation (`azd ai agent eval`, confirmed live
  against a real `kind: hosted` agent) with the `builtin.groundedness`
  testing criterion — the same Monitored-workload posture `VAL-001` already
  established in this repository, applied to a different signal source.
- **How their role is made visible in the core demo:** The walkthrough shows
  the real `azd ai agent eval generate`/`eval run` output (Eval id, run id,
  real pass/fail counts, a `report_url` a learner can open in the Foundry
  portal) *before* any control-specific code runs, then shows the
  deterministic policy reading exactly those per-item results — so a learner
  sees precisely where the Microsoft-supplied signal ends and the
  repository's control logic begins.
- **Minimum custom implementation or artifacts:** A synthetic knowledge-base
  scenario for the hosted agent that can produce both grounded and
  deliberately under-supported answers (to exercise both scenarios), the
  `output_items.list()` retrieval call, a deterministic aggregation and
  threshold policy (rate + critical-item override, scale-relative to each
  item's own threshold since different evaluators use different numeric
  scales — confirmed live), and an evidence record writer for the
  Quality-review gate.
- **Unique learning outcome:** How to turn a real Microsoft groundedness
  evaluator's batch-run output into an accountable, auditable monitoring
  control — with an explicit window, a documented non-claim about what a
  groundedness score does and does not guarantee, and a fail-closed path for
  incomplete or errored items — rather than treating the raw score as the
  governance decision itself.
- **Distinct governance learning beyond an existing official sample:** The
  cited "Evaluate your hosted agent" quickstart stops at "run an eval and
  read a score." This demo adds everything a control needs beyond that: the
  rate policy, the window and completeness semantics, the critical-item
  override, fail-closed behavior on incomplete/errored items, and the
  accountable-role evidence record.
- **Why this deserves a separate bite-sized demo:** It is the first
  implemented control in `grounding_and_quality`, exercises the
  Monitored-workload posture already validated once in this repository
  (`VAL-001`) but applied to a genuinely different signal and category, and
  gives the community a concrete, reproducible answer to "how do I actually
  govern hallucination rate," which the user identified as directly relevant
  to trustworthy-AI concerns. It also surfaced a real, disclosed product gap
  (Continuous Evaluation rejecting hosted agents — see
  `docs/UPSTREAM-FEEDBACK.md`) that would not have been found without
  attempting the original design against a live deployment.
- **Why deployment is or is not justified:** A local stub score would let a
  learner run the demo without Azure, but it would not demonstrate a real
  evaluator's behavior (its actual pass/fail texture, latency, and failure
  modes — including the 2-of-19 item errors observed live) and would violate
  the instruction that evidence must come from the documented core path, not
  a locally invented judge. Deployment here is one hosted Foundry agent —
  the same footprint `VAL-001` already requires.

## Smallest useful design

- **Primary governance decision:** Does this measurement window's aggregated
  hallucination rate (plus any critical hallucination) require a Quality
  review before the next window is trusted?
- **Authoritative human role or system:** Product Owner (reviews and clears
  the breach); the batch evaluation's `builtin.groundedness` criterion is
  the authoritative per-item signal source, not a decision-maker.
- **Signal source:** Per-item `passed`/`score`/`threshold` results from a
  triggered `azd ai agent eval run`, read via
  `openai_client.evals.runs.output_items.list()`.
- **Authoritative decision or enforcement surface:** A deterministic policy
  function: read the window's results, aggregate against the `>5%`
  threshold, and force `Quality review` if breached or if any item's score
  is at or below half its own evaluator's pass threshold (critical).
- **Authoritative evidence source:** The batch-evaluation run's own stored
  results, read through `output_items.list()`, plus the policy's window
  record (sample size, completeness, rate, decision, reviewer assignment) —
  both produced by the documented core path, not reconstructed afterward.
- **ACS intervention point, if applicable:** None — this is an asynchronous
  monitoring control, not an inline intervention; documented above as not
  applicable.
- **AGT capability, if applicable:** None for the evaluation path; the
  implemented control still registers in the governance contract per
  `docs/governance-contract.md`.
- **Foundry/Azure services:** One hosted Foundry agent, an Eval definition
  with the `builtin.groundedness` testing criterion, and the OpenAI-
  compatible Evals API (`allow_preview=True`, a disclosed dependency — see
  revision note 3); Entra managed identity for auth.
- **Governance action:** `Quality review` opened against the Product Owner,
  referencing the breached window's evidence record.
- **Evidence artifact:** A window evidence record (JSON) containing window
  id, sample size, completeness check, per-item ungrounded/critical item
  ids (no raw prompt/response text), aggregated rate, threshold, decision,
  and reviewer.
- **Healthy/complete scenario:** All sampled items scored within the window;
  rate at or below `5%`; no critical item; decision = allow, window closed.
  Confirmed live: 15/15 passed on a first, less adversarial run.
- **Policy-triggering scenario:** Rate above `5%`, or a single item confirmed
  as a critical hallucination even if the aggregate rate is below threshold;
  decision = `Quality review`, evidence references the flagged item
  identifiers. Confirmed live: a targeted adversarial run reproduced a real
  47% rate and 2 critical items, and the resulting real Teams notification
  reached the Product Owner's channel.
- **Unavailable, incomplete, or ambiguous scenario:** One or more sampled
  items not yet scored or reporting an evaluator error; window is reported
  `evaluation incomplete`, excluded from a "healthy" claim, and fails closed
  (treated as requiring review) rather than silently shrinking the
  denominator. Confirmed live: 2 of 19 items errored on the `groundedness`
  criterion in the adversarial run; a window scoped to all 19 would
  correctly have reported this outcome (see README.md "Known limitations").

## Complexity budget

- **Why each custom component is necessary:** The batch evaluation run
  provides only a per-item verdict; nothing in `azd ai agent eval` defines a
  measurement window, a rate policy, a critical-item override, fail-closed
  handling for incomplete/errored items, or an accountable-role evidence
  record — all required by the control contract and absent from the cited
  official sample.
- **Files and dependencies used by the core, validation, or optional path:**
  Synthetic knowledge-base fixture for the hosted agent, the eval
  trigger/retrieval code in `demo.py`, the policy module in `evaluator.py`,
  an evidence writer, and their tests; no UI beyond what the hosted-agent
  pattern already requires, no additional database (evidence is a file
  artifact), no second agent.
- **Interfaces, agents, stores, or resources deliberately omitted:** No
  Chainlit or other UI, no persistent database (evidence is a file
  artifact), no Groundedness Detection Filter/Content Safety resource (that
  is RUN-001's territory, not duplicated here), no Continuous Evaluation
  rule (confirmed rejected for hosted agents — not a choice, a hard
  constraint), Application Insights/Log Analytics deployable but not read by
  the core path (retained only for a future Continuous Evaluation switch).
- **How disconnected or shadow evidence is avoided:** The evidence record is
  written only from a real `output_items.list()` call against a real,
  triggered evaluation run; there is no pre-baked "example" evidence file,
  and the README's captured transcripts, decision JSON, and Teams card
  screenshot were generated by actually running the documented core path
  (and, for the breach specifically, a purpose-built adversarial variant of
  it — disclosed as such) before being added, per the
  screenshot/transcript-capture rule.
- **Metadata/configuration edge cases, if applicable:** An item missing a
  score or reporting an evaluator error (fails closed as incomplete, not
  silently treated as grounded — confirmed live); invalid/missing threshold
  on an item (control refuses to run rather than defaulting silently).

## Community fit

- **Learning level:** Intermediate
- **Estimated completion time:** 30–45 minutes (assumes an existing hosted
  Foundry agent, following the `VAL-001` pattern; add time if that must be
  created first — a real deployment in this assessment took roughly 15
  minutes including two `azd auth` re-logins and one bicep fix)
- **Minimum prerequisites:** A hosted Foundry agent reachable via Entra
  managed identity; Python environment per repository conventions.
- **Why the core demo remains accessible:** One triggered eval run, one
  deterministic policy, one evidence file — no new UI, database, or agent
  framework to learn beyond what `VAL-001` already demonstrates in this
  repository.
- **Intentional simplifications:** Fixed, small synthetic knowledge-base
  scenario rather than genuine production retrieval content; a single
  measurement window per demo run rather than a scheduled recurring job;
  the batch-evaluation dataset is LLM-generated from a natural-language
  description of the agent and its windows, not a hand-authored, literal
  per-window dataset — see README.md "Further exploration".
- **Further exploration to document rather than implement:** Scheduled/
  recurring window execution (e.g., a pipeline trigger); wiring RUN-001's
  inline sibling control (Groundedness Detection Filter) once it is
  assessed; switching to Continuous Evaluation once hosted-agent support
  ships (see `docs/UPSTREAM-FEEDBACK.md`); a category `ARCHITECTURE.md` for
  `grounding_and_quality` recording this control's use of `azd ai agent
  eval` so QLT-002/005/006 reconcile with it instead of redefining it;
  concrete remediation guidance for the Product Owner once a breach is
  confirmed (see README.md "After a Quality review").
- **Optional community exploration paths:** Author a literal, hand-written
  dataset per window for exact 1:1 correlation with `demo.py run`'s real
  conversations; compare `builtin.groundedness`'s results against a manual
  offline `GroundednessEvaluator` SDK run on the same items.

## Scope boundary

- **Included:** Triggering a real batch evaluation run per window; reading
  its real per-item `passed`/`score`/`threshold` results via
  `output_items.list()`; window/completeness handling; rate-vs-critical-item
  policy (scale-relative to each item's own threshold); fail-closed behavior
  on incomplete or errored items; Quality-review evidence record.
- **Explicitly excluded:** Inline/real-time blocking of a single turn (that
  is RUN-001's territory, using the Groundedness Detection Filter, not this
  control's); Continuous Evaluation (confirmed unavailable for hosted
  agents, not a design choice); automatic remediation of the underlying
  agent or knowledge base (see README.md "After a Quality review" for where
  that guidance lives instead).
- **What the demo proves:** That a real, Microsoft-supplied groundedness
  evaluator's batch-run output can be turned into an accountable, auditable
  rate-based governance control with explicit fail-closed behavior and a
  documented human review action — demonstrated live in both directions
  (a healthy run and a genuine, notified breach).
- **What the demo does not prove:** That the underlying LLM-judge evaluator
  is free of false positives/negatives, that `5%` is the correct threshold
  for any given production system, that this constitutes regulatory
  compliance evidence, or that hallucination is fully eliminated once the
  control is in place.
- **Is the core control correct and safe within this boundary?** Yes —
  the fail-closed rule on incomplete/errored evaluation and the "no raw
  prompt/response beyond a flagged item id" evidence-minimization rule are
  both implemented and covered by the repository's own tests; confirmed live
  against a real deployment, including the 2-errored-item edge case.

## Decision

- **Proceed / revise / reject:** Proceed, with the design corrected twice —
  once from a bespoke evaluator script to Continuous Evaluation (revision
  note 1), and again from Continuous Evaluation to batch evaluation after a
  real deployment showed the former rejects hosted agents (revision note 3).
- **Rationale:** A real, GA-adjacent Microsoft capability (batch/cloud
  evaluation via `azd ai agent eval`, using `builtin.groundedness`) supplies
  the authoritative per-item groundedness signal, confirmed working live
  against a real hosted agent, including a real reproduced breach and a
  real delivered Teams notification. The genuine, non-duplicative gap is the
  rate/window/fail-closed policy and evidence layer around it, following the
  same Monitored-workload architecture this repository already validated in
  `VAL-001`. The control occupies a distinct, clearly-bounded niche next to
  RUN-001 (mapped to a different Microsoft capability entirely), QLT-002,
  and QLT-005, and directly serves the human-oversight/groundedness
  trustworthy-AI theme the user asked for.
- **Review date:** 2026-09-23 (assessed, cross-checked, and then verified
  against a real deployment, all in the same day)
- **Authoritative references:**
  - [Quickstart: Evaluate your hosted agent — Microsoft Learn](https://learn.microsoft.com/en-us/azure/foundry/observability/quickstarts/quickstart-evaluate-hosted-agent) (the documented, confirmed-working core path)
  - [Generally Available: Evaluations, Monitoring, and Tracing in Microsoft Foundry — Microsoft Community Hub](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/generally-available-evaluations-monitoring-and-tracing-in-microsoft-foundry/4502760) (background on Continuous Evaluation, superseded as the core path — see revision note 3)
  - [Observability in Generative AI — Microsoft Foundry — Microsoft Learn](https://learn.microsoft.com/en-us/azure/foundry/concepts/observability)
  - [Groundedness Detection Filter — Microsoft Foundry — Microsoft Learn](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/content-filter-groundedness)
  - [Local Evaluation with the Azure AI Evaluation SDK — Microsoft Learn](https://learn.microsoft.com/en-us/azure/foundry-classic/how-to/develop/evaluate-sdk) (background on the underlying evaluator only)
  - `azure-ai-projects` 2.3.0 and 2.7.0 installed package source (this repository's `.venv`, and a temporary upgrade during live testing): `azure/ai/projects/_patch.py`, `operations/_patch_evaluation_rules.py`, `models/_models.py` (`EvaluationRule`, `ContinuousEvaluationRuleAction`, `EvaluationRuleFilter`), `models/_enums.py` (`_FoundryFeaturesOptInKeys.EVALUATIONS_V1_PREVIEW`) — read directly to confirm the SDK surface and its preview gating, reviewed 2026-09-23
  - `openai` 2.54.0 installed package source: `openai/resources/evals/` (`evals.create/list/retrieve`, `evals/runs`, `evals/runs/output_items`) — confirmed present and, for `output_items.list()`, confirmed working live, reviewed 2026-09-23
  - A real Foundry project, hosted agent (`it-helpdesk-kb-assistant`), and two real `azd ai agent eval` runs, executed live 2026-09-23 (see README.md "Demo" and "Validation")
  - `controls/value_adoption_and_finops/VAL-001_kpi_underperformance/ASSESSMENT.md` (architectural precedent, this repository)
  - Source catalog: [Governance Signals Repo.pdf](../../../docs/Governance%20Signals%20Repo.pdf)
