# RUN-006 — control assessment

Part of the **runaway agent kill switch** bundle:
[TOOL-003](../../tool_governance/TOOL-003_excessive_tool_calls/ASSESSMENT.md)
(per-task tool-call budget) → RUN-006 (loop or retry-storm stop) →
[AUT-004](../../autonomy_and_human_oversight/AUT-004_emergency_stop_not_enforced/ASSESSMENT.md)
(human emergency stop). Each control remains independently runnable.

## Candidate

- **Control ID:** RUN-006
- **Name:** Agent loop or retry storm
- **Lifecycle phase:** Live
- **Accountable role:** AI Ops Lead

## Governance problem

- **Risk:** A downstream service returns an ambiguous failure and the agent
  keeps retrying the same action. Each retry costs a model call and a tool call,
  and some "failed" attempts may actually have succeeded. Nothing is malicious;
  the agent is doing what it was built to do.
- **Control objective:** Detect repetition without progress inside a run, stop
  the whole run (both further tool calls and further model calls), and notify
  the AI Ops Lead through a channel the agent does not control.
- **Authoritative signal:** Within one run, the number of admitted
  `pre_tool_call` decisions with the same tool name and the same argument
  fingerprint (SHA-256 of canonical arguments) since the last **verified
  progress** for that same action. The host supplies this history to ACS as
  `$snap.prior_decisions` from the run journal (see TOOL-003's assessment for
  the shared journal rules: one entry per evaluation, appended before
  execution, sequential admission).
- **Progress definition:** Progress for an action exists only when this
  attempt produced a new, verified change in the synthetic system of record:
  for `issue_refund`, a refund newly on the ledger; for `reply_to_ticket`, a
  reply not already on the ticket. A read (`lookup_order`) never counts as
  progress, and repeating an action that already succeeded does not either
  (revised 2026-11-14 after code review found that checking only the current
  ledger state let a repeated successful call loop forever). An ACS `allow`
  verdict is not progress, a successful call to a *different* tool does not
  reset the count, and a result of `status: unknown` is not progress.
- **Required decision:** With threshold *N* = 3 (from the governance
  contract), attempts 1 and 2 of the same action without verified progress are
  admitted and attempt 3 is denied, and the run stops. Tests cover both
  counting boundaries.
- **Required governance action:** Deny the repeated tool call; deny every later
  `pre_model_call` and `pre_tool_call` in that run; return a safe handoff
  message. Notification is optional (see the implementation finding under
  *Decision*): when deployed, the ACS deny decision reaches Application
  Insights, where a log search alert notifies the AI Ops Lead through an
  action group.
- **Required evidence:** Control ID and policy version, run correlation ID,
  tool name, argument fingerprint (never raw arguments), repeat count and
  threshold, decision and reason, intervention point, stop timestamp, alert
  rule name, and accountable role.

## Enforcement classification

- **Deterministic policy:** Yes. Equality of tool name and argument
  fingerprint, counted against a declared threshold.
- **Model-assisted evaluation:** No. The model is the governed subject; it does
  not judge whether it is looping.
- **Human approval:** No inline approval. A stopped run is not resumed; the
  user's request is handed to a human.
- **Configuration assessment:** Yes, at `agent_startup`: the threshold must be
  declared and valid.
- **Monitoring/detection:** Yes, for notification only. The Azure Monitor alert
  tells the AI Ops Lead; it is not the stop. The stop is inline.
- **Required fail-closed behavior:** Missing or invalid threshold denies at
  startup. Missing `prior_decisions`, an unparseable argument set, or a policy
  error denies. A tool result whose status is unknown is treated as **not**
  progress.
- **Model/Foundry role:** `Active — governed subject`. The repository rules
  name agent-loop signals as Active: a real Foundry agent's tool and model
  calls pass through ACS `pre_tool_call` and `pre_model_call`.

## Existing capability review

Review date: 2026-11-13.

| Capability | Applicable? | What it already provides | Role in the core demo or reason not used |
|---|---:|---|---|
| Microsoft Agent Governance Toolkit | Partly | Per the AGT repository source tree reviewed 2026-11-13 (not executed): `agent-sre` `CircuitBreaker` and `CascadeDetector` trip on error rates across calls; hypervisor `KillSwitch` with `rate_limit` reason. | Not used inline: they detect failure rates or terminate agent processes, not repetition of an identical action inside one run. The `-sre` and `-runtime` split-package publication could not be verified on 2026-11-13. Using them would add a second decision engine beside ACS. Documented as further exploration. |
| Agent Control Specification | Yes | `pre_tool_call`, `pre_model_call`, `post_tool_call`, host-supplied `prior_decisions`, OTel counters `acs_intervention_*_total`. ACS explicitly delegates retries, circuit breakers and rate limits to the host. | **Primary enforcement surface.** The loop rule is the ACS policy dispatcher; `pre_model_call` makes the stop cover model calls too. ACS's own OTel sink provides the telemetry. |
| Microsoft Foundry | Yes | Prompt agent, Responses function calling, `cancel` for background responses. | Supplies the governed agent. The loop is induced with a deliberately flawed instruction ("retry failed refunds until they succeed") against a synthetic tool that returns `status: unknown`. |
| Foundry Control Plane | No | Stop/start published agents; stopping "doesn't terminate existing runs"; unpublished prompt agents can only be deleted. | Wrong granularity for one stuck run; AUT-004 covers the agent-level layer. |
| Azure API Management AI Gateway | No | `llm-token-limit` per key returns 429/403 on token rate or quota. | Limits tokens, not repetition. A token brake for retry storms belongs to FIN-004. Adding APIM would also add the largest deployment cost in the bundle. |
| Microsoft Purview / Defender | No | Data governance / threat detection. | A retry storm is an operational defect, not a data or security event. |
| Microsoft Entra | No | Identity. | No authority decision depends on identity in this control. |
| Azure AI Content Safety / Language | No | Content analysis. | Not applicable. |
| Azure Monitor / Application Insights / OTel | Yes | Workspace-based Application Insights, scheduled log search alert rules, action groups. | **Notification path.** ACS OTel deny counters (reason `run_006_loop_detected`) land in Application Insights; one log search alert rule fires an email action group to the AI Ops Lead. Alert latency is minutes, which is why it notifies and never enforces. |

## Existing samples and implementations

| Repository, documentation, or sample | Overlap | What is still missing |
|---|---|---|
| AUT-002 (this repo) | ACS `run_tool` around real Foundry function calls. | No run-level stop or `pre_model_call` gate. |
| QLT-001 (this repo) | Application Insights deployment pattern. | Reused for Bicep shape only; no alert rule. |
| AGT `agent-sre` circuit breaker | Trips on failure rate. | Not repetition-of-identical-action, not inline per run. |
| ACS `security-model.md` | States ACS does not provide retries, circuit breakers or rate limits; the host must. | No sample showing a host feeding run history to a loop policy. |

## Repository overlap

- **Related controls:** TOOL-003 limits call *count* regardless of pattern (see
  the shared scenario matrix in its assessment). FIN-004 measures the *cost* of
  failed retry runs afterwards and does not stop anything inline. OPS-003
  tracks technical failure *rates* across runs. AUT-004 is the human stop.
- **Existing components that can be reused:** AUT-002 Foundry adapter and ACS
  shape (copied and reduced), QLT-001 Application Insights Bicep.
- **Risk of duplicating an existing demo:** Low; nothing implemented stops a
  run on repetition.

## Proposed contribution

- **Classification:** `COMPOSE` — ACS inline stop plus ACS OTel telemetry plus
  Azure Monitor alerting, with a small loop policy.
- **Demo format:** `DEPLOYABLE_DEMO` (local runner against deployed Foundry and
  Monitor resources).
- **Deployment:** Required for the core learning outcome.
- **How capability roles are made visible:** The transcript shows the third
  identical call denied, the next model call denied, and the run ending; the
  Azure Portal shows the alert firing and the email arriving.
- **Minimum custom implementation:** One ACS manifest, a loop policy dispatcher,
  argument fingerprinting, a snapshot builder, synthetic tools, a Foundry
  adapter, an OTel exporter setup (`azure-monitor-opentelemetry`), Bicep for
  App Insights, alert rule and action group, cleanup, tests.
- **Unique learning outcome:** Stop the run, not just the call: a loop brake
  must cover model calls too, and the human is told by monitoring the agent
  cannot silence.
- **Why deployment is justified:** A real agent must choose to retry, and the
  alert must actually fire in Azure Monitor. A credential-free scripted replay
  remains the regression path.

## Smallest useful design

- **Primary governance decision:** Has this run repeated the same action
  without progress often enough that it must stop?
- **Authoritative system:** ACS; the AI Ops Lead owns the threshold in the
  governance contract.
- **Signal source:** Prior ACS decisions in the run plus `post_tool_call`
  result status.
- **Authoritative enforcement surface:** ACS `pre_tool_call` and
  `pre_model_call`.
- **Model-call integration:** AUT-002's adapter calls `responses.create`
  directly, so it cannot enforce `pre_model_call` unchanged. RUN-006 routes
  every Responses request through ACS's shipped `guard_openai_client`
  (verified present in 0.3.1b1 for `responses.create`). Implementation showed
  that the guard accepts a per-call snapshot through the
  `agent_control_snapshot` keyword, so no re-wrapping is needed: each request
  carries fresh journal history. Once the loop denial is in the journal,
  every later `pre_model_call` in the run is denied; the handoff text is
  produced locally. A test asserts that no request leaves the process after
  the stop.
- **Authoritative evidence source:** The ACS verdict, recorded per run in local
  JSON with the run ID. Application Insights receives ACS's **aggregate**
  deny counter (dimensions `policy_id`, `reason_code`, `intervention_point`;
  ACS deliberately omits action identity and run ID from metrics). The alert is
  therefore an aggregate notification ("loop stops occurred"), and per-run
  detail comes from the local evidence. The runner flushes the exporter before
  exiting.
- **Foundry/Azure services:** Shared Foundry account; control-owned project,
  model deployment, prompt agent; workspace-based Application Insights; one
  scheduled query alert rule; one email action group.
- **Healthy scenario:** A refund succeeds on the first attempt.
- **Progress-reset scenario:** A refund returns `unknown`, then a lookup
  succeeds, then the same refund is retried. The count is not reset and the
  stop still triggers.
- **Policy-triggering scenario:** The refund tool returns `status: unknown`;
  the third identical attempt is denied, the next model call is denied, the
  alert fires.
- **Unavailable or ambiguous scenario:** Missing threshold denies at startup;
  telemetry export unavailable still stops the run inline and the evidence
  records `notification: not_confirmed`.

## Complexity budget

- **Why each component is necessary:** As listed above; Monitor resources exist
  only because notification is part of the gate effect.
- **Omitted:** Web app, Chainlit, APIM, database, second agent, Logic App.
- **How shadow evidence is avoided:** The alert queries ACS's own telemetry,
  not a separate log written by custom code.
- **Metadata edge cases:** Missing, empty, zero, negative, non-integer and
  valid thresholds; arguments with reordered keys must fingerprint equal.

## Community fit

- **Learning level:** Intermediate
- **Estimated completion time:** Establish after the first end-to-end run (alert
  delivery adds several minutes).
- **Prerequisites:** As TOOL-003, plus an email address for the action group.
- **Intentional simplifications:** Exact-argument equality only (a retry with a
  changed argument is not a loop here); per-process run history.
- **Further exploration:** AGT circuit breaker across runs, APIM token brake
  (FIN-004), Foundry `cancel` for background responses.

## Scope boundary

- **Included:** One run-level loop stop at two ACS points, plus a real alert.
- **Excluded:** Cross-run storms, semantic near-duplicate detection, cost
  attribution, undoing side effects of attempts that succeeded.
- **Proves:** ACS can stop a looping run before the next identical call and
  before the next model call, and the stop is reported through Azure Monitor.
- **Does not prove:** Detection of loops with varying arguments, coverage of
  tools outside the ACS path, alert delivery guarantees, per-run correlation
  in Application Insights (metrics are aggregate by ACS design), or integrity
  of the host-supplied journal.
- **Correct and safe within this boundary?** Yes, provided every call goes
  through ACS and unknown results never count as progress.

## Decision

- **Proceed / revise / reject:** Proceed.
- **Rationale:** No supported capability detects in-run repetition of an
  identical action; ACS is the documented surface and delegates this logic to
  the host. Monitor supplies a notification path the agent cannot suppress.
- **Review date:** 2026-11-13
- **Implementation finding (2026-11-14):** In the validation subscription, a
  subscription-scope Azure Policy assignment ("Deny resource types not
  explicitly approved", effect `Deny`) blocks `Microsoft.Insights/components`
  and `Microsoft.Insights/scheduledQueryRules`; a management-group policy also
  requires a Log Analytics daily cap ≤ 1 GB (now set). Changing that
  protection policy requires the owner's explicit approval, which was not
  given. The notification path is therefore a Bicep parameter
  (`enableAlerting`, default `true`). The inline ACS stop was validated live
  with `enableAlerting=false`; the alert path is implemented and unit-tested
  but **not validated end to end**, so the control remains `Implemented`
  until it is.
- **Update (2026-11-14):** With the policy owner's approval, the allow-list
  was extended to Application Insights and log alert rules. The alert path
  was then validated live: metric exported, dimensions present in
  `customMetrics`, alert fired about 7 minutes after the stop, cleanup
  verified. Email receipt was not confirmed. Status: `Validated`.
- **Quality bar (agreed 2026-11-14):** Target `Validated`, not `Implemented`: a real Azure end-to-end run in the documented order, captured screenshots or transcripts for every scenario, verified control-owned cleanup, an independent code review per control, and a control-demo-roast before any announcement. The assessment was revised after an independent design review on 2026-11-14.
- **Resolved 2026-11-14:** The installed ACS 0.3.1b1 OTel sink
  (`_telemetry.py`, `_otel_attributes`) attaches `intervention_point`,
  `decision`, `reason_code` and `policy_id` to `acs_intervention_deny_total`.
  The alert query filters on `policy_id` and `reason_code =
  run_006_loop_detected`. These dimensions were observed in Application
  Insights `customMetrics` during the end-to-end run.
- **Authoritative references:**
  - [ACS stateless runtime guide](https://github.com/microsoft/agent-governance-toolkit/blob/main/policy-engine/docs/stateless-runtime.md)
  - [ACS security model](https://github.com/microsoft/agent-governance-toolkit/blob/main/policy-engine/docs/security-model.md)
  - [Azure Monitor log search alerts](https://learn.microsoft.com/en-us/azure/azure-monitor/alerts/tutorial-log-alert)
  - [Foundry Control Plane lifecycle operations](https://learn.microsoft.com/en-us/azure/foundry/control-plane/how-to-manage-agents)
