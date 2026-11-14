# AUT-004 — control assessment

Part of the **runaway agent kill switch** bundle:
[TOOL-003](../../tool_governance/TOOL-003_excessive_tool_calls/ASSESSMENT.md)
(per-task tool-call budget) →
[RUN-006](../../runtime_and_operations/RUN-006_agent_loop_or_retry_storm/ASSESSMENT.md)
(loop or retry-storm stop) → AUT-004 (human emergency stop). TOOL-003 and
RUN-006 are automatic brakes; AUT-004 is the human red button for what they
cannot anticipate. Each control remains independently runnable.

## Candidate

- **Control ID:** AUT-004
- **Name:** Emergency stop not enforced
- **Lifecycle phase:** Live
- **Accountable role:** Ops Manager

## Governance problem

- **Risk:** An operator sees a support agent issuing wrong or duplicate refunds
  and "presses stop", but the refund service keeps accepting requests, the
  agent quietly re-enables itself, or nobody can say which refunds completed
  before the stop took effect.
- **Control objective:** Enforce an authorized stop for one agent and one
  action outside model reasoning, keep unaffected actions available, verify the
  stop took effect, account for work already in flight, and permit resumption
  only by an authorized principal.
- **Authoritative signal:** An App Configuration **Switch** feature flag per
  agent and action (`aut004-support-refunds-agent-issue_refund`). Enabled means
  the action is permitted; anything else means stopped.
- **Required decision:** Allow `issue_refund` only when the flag is read
  successfully and is explicitly enabled. Unaffected tools follow normal rules.
- **Required governance action:** Deny every new `issue_refund` before it
  executes; run a deliberate verification probe; list refunds admitted before
  the stop with their verified outcome; hold until an authorized principal
  re-enables the flag.
- **Required evidence:** Control ID and policy version, stop scope (agent,
  action), flag key, the three timestamps **requested** (flag change time),
  **enforced** (first denial) and **verified** (probe denial), in-flight refunds
  and their outcomes (`completed`, `failed`, `unknown`), recovery time, the
  actor reference for stop and recovery from App Configuration audit logs,
  run correlation IDs and accountable role.

## Enforcement classification

- **Deterministic policy:** Yes. Flag explicitly enabled → allow; disabled,
  missing, unreadable or malformed → deny.
- **Model-assisted evaluation:** No.
- **Human approval:** Yes. Pressing stop and lifting it are human actions gated
  by Entra RBAC on the App Configuration store.
- **Configuration assessment:** Yes, at `agent_startup`: the flag must exist
  for every protected action declared in the governance contract.
- **Monitoring/detection:** The verification probe and the in-flight report.
  App Configuration audit logs supply the actor for stop and recovery.
- **Required fail-closed behavior:** An App Configuration read error, timeout,
  throttling (429), missing flag or invalid flag payload denies the protected
  action and reports in-flight status as `unknown`, never as `completed`. The
  agent runtime identity cannot write the flag.
- **Model/Foundry role:** `Active — governed subject`. A registered Foundry
  prompt agent's real `issue_refund` function calls pass through ACS
  `pre_tool_call` and `post_tool_call`.

## Existing capability review

Review date: 2026-11-13.

| Capability | Applicable? | What it already provides | Role in the core demo or reason not used |
|---|---:|---|---|
| Microsoft Agent Governance Toolkit | Partly | Per the AGT repository source tree reviewed 2026-11-13 (not executed): hypervisor `KillSwitch` (`kill`, `kill_history`, reason `manual`) terminates a registered agent process and hands off saga steps. | Not used: it kills the whole agent rather than one action; publication of the `agent-governance-toolkit-runtime` split package could not be verified on 2026-11-13; and the stop state would live in process memory, which does not survive a restart. Documented as further exploration. |
| Agent Control Specification | Yes | `agent_startup`, `pre_tool_call`, `post_tool_call`; fail-closed on missing snapshot paths; ACS explicitly provides no async cancellation. | **Primary enforcement surface.** The host reads the flag and passes it as `$snap.metadata.stop_state` with its read status; the policy dispatcher decides. |
| Microsoft Foundry | Yes | Prompt agent; Responses function calling. | Supplies the governed agent. |
| Foundry Control Plane | Teaching point | Stop/start for **published** agents ("doesn't terminate existing runs"); unpublished prompt agents can only be deleted; block for custom agents. | Not the core stop: it acts on the whole agent rather than one action, is unavailable for this unpublished prompt agent, and does not end runs already in progress. The README explains this as the agent-level layer and why an action-scoped gate is still needed. |
| Azure API Management AI Gateway | No | Token limits on model traffic. | Blocks model calls rather than one tool action, so it cannot "stop the refund, not the business". |
| Microsoft Purview / Defender | No | Data governance / threat detection. | Not applicable to an operator stop. |
| Microsoft Entra | Yes | RBAC: **App Configuration Data Owner** (read/write) and **Data Reader** (read). | **Authority boundary.** The Ops Manager holds Data Owner on the store; the web app's managed identity holds Data Reader only, so the agent runtime cannot clear its own stop. A write attempt by the runtime identity is shown to fail. |
| Azure App Configuration | Yes | Switch feature flags documented as an "instant kill switch … without redeploying code"; **Audit** resource logs (`AACAudit`) record data-plane writes. | **Authoritative stop state and the red button.** The operator toggles the flag in Azure Portal → App Configuration → Feature manager. A diagnostic setting sends audit logs to Log Analytics for the actor and timestamp of stop and recovery. |
| Azure App Service | Yes | Hosting with a user-assigned managed identity. | Hosts the agent runtime with a read-only identity: that identity is the proof that the agent cannot lift its own stop. Reuses AUT-002's Chainlit host. |
| Azure Monitor / Log Analytics | Yes | Workspace for App Configuration audit logs. | Evidence of who pressed stop and who recovered. No alert rule (RUN-006 owns alerting). |
| Azure AI Content Safety / Language | No | Content analysis. | Not applicable. |

## Existing samples and implementations

| Repository, documentation, or sample | Overlap | What is still missing |
|---|---|---|
| AUT-002 (this repo) | Foundry agent, ACS `run_tool`, Chainlit on App Service, managed identity, deploy and cleanup scripts. | No external stop state, no in-flight report, no recovery authority. AUT-004 reuses the host and adapter, not the approval mandate. |
| App Configuration feature-flag kill switch docs | Switch flag as an instant kill switch. | Applied to an application feature, not an agent action with fail-closed and verification semantics. |
| Foundry Control Plane lifecycle docs | Agent-level stop/block. | No per-action scope, no in-flight termination. |

## Repository overlap

- **Related controls:** AUT-002 escalates *every* irreversible action for
  approval; AUT-004 stops an action that is otherwise *permitted* for as long as
  an operator says so. AUT-001 (HITL bypass) is planned. RET-005 (retired agent
  still accessible) concerns permanent retirement, not temporary containment.
  TOOL-003 and RUN-006 are the automatic brakes in this bundle.
- **Scenario decision:** The bundle uses `issue_refund` for the protected
  action instead of the earlier "delete customer files" proposal, so it does
  not overlap with AUT-002's deletion and so duplicate refunds can illustrate
  work in flight. The README's Overview and Implementation sections are
  updated to match.
- **Risk of duplicating an existing demo:** Low.

## Proposed contribution

- **Classification:** `COMPOSE` — App Configuration feature flag + Entra RBAC +
  ACS + Foundry agent + App Configuration audit logs, joined by a small
  adapter.
- **Demo format:** `DEPLOYABLE_DEMO`.
- **Deployment:** Required for the core learning outcome: the stop must live
  outside the agent process and the runtime identity must lack write access.
- **How capability roles are made visible:** The operator toggles the flag in
  Azure Portal; the chat shows refunds denied while lookups continue; the
  runtime identity's write attempt returns 403; Log Analytics shows who
  stopped and who recovered.
- **Minimum custom implementation:** ACS manifest and stop policy dispatcher;
  a flag reader returning `enabled | disabled | missing | invalid |
  unavailable` with no caching; a verification probe; an in-flight report from
  ACS `post_tool_call` results; reuse of AUT-002's Foundry adapter and Chainlit
  host; Bicep for App Configuration (the lowest-cost SKU that supports
  Entra data-plane RBAC and Audit resource logs; confirm current SKU options
  before deployment), diagnostic setting, Log Analytics, App Service,
  managed identity and role assignments; deploy and cleanup scripts; tests.
- **Unique learning outcome:** A kill switch counts only if it lives outside
  the AI, is scoped to the action rather than the whole business, fails
  closed, is verified, accounts for work already in flight, and cannot be
  lifted by the thing it stops.
- **Why this deserves a separate demo:** No implemented control demonstrates
  stop-state authority, verification and recovery.

## Smallest useful design

- **Primary governance decision:** May `issue_refund` run while a stop may be
  in effect?
- **Authoritative human role or system:** Ops Manager (App Configuration Data
  Owner); ACS enforces.
- **Signal source:** The App Configuration feature flag, read without caching
  at every protected `pre_tool_call`.
- **Authoritative enforcement surface:** ACS `pre_tool_call` for
  `issue_refund`; ACS `agent_startup` for flag presence.
- **Authoritative evidence source:** ACS verdicts and `post_tool_call` results,
  plus App Configuration `AACAudit` entries for stop and recovery.
- **Stop semantics:**
  - *Linearization point:* The stop takes effect at **admission**, the ACS
    `pre_tool_call` decision. A refund admitted before the flag change may
    still execute after it. That refund is in-flight work, not a stop
    failure. Each decision records the flag ETag, the time the read completed,
    and the admission and execution timestamps. A test pauses an admitted
    refund across the toggle and shows it reported as in flight. A guarantee of
    "no commits after stop" would need fencing at the refund service itself,
    which is documented as further exploration and not claimed.
  - *Bounded reads:* Each protected call reads the flag with no caching, a
    2-second timeout and at most one retry. Evidence distinguishes
    `disabled` (the stop was observed) from `unavailable`, `throttled`,
    `missing` and `invalid` (each fails closed). The stop counts as
    **verified** only when the probe is denied because it observed
    `disabled`. A denial caused by an outage proves fail-closed behavior, not
    that the stop was observed.
  - *Scope:* one agent and one action; `lookup_order` and `reply_to_ticket`
    remain available.
  - *Deadline:* the next protected call after the flag change. Measured as the
    time from **requested** to **enforced**; no SLA is claimed.
  - *In flight:* Refunds admitted before the stop finish or fail on their
    own. They are reported, not cancelled or rolled back. Each admitted
    refund's outcome is verified against the synthetic refund ledger, not
    inferred from an ACS verdict. Because `run_tool` does not reach
    `post_tool_call` when the tool raises, an admitted refund with no verified
    ledger entry is reported as `unknown`. Accounting covers the current
    process only, because the ledger is in memory.
  - *Persistence:* the stop survives an App Service restart because the state
    lives in App Configuration.
  - *Recovery:* only a Data Owner can re-enable the flag. Resumed requests are
    re-evaluated; nothing queued is replayed automatically.
- **Healthy scenario:** The flag is enabled; the refund completes.
- **Policy-triggering scenario:** The operator disables the flag mid-session.
  The next refund is denied, lookups still work, the probe is denied and the
  in-flight report is generated.
- **Unavailable scenario:** App Configuration is unreachable or the flag is
  deleted. Refunds are denied and in-flight status is `unknown`.
- **Authority scenarios:** The runtime identity's attempt to re-enable the flag
  is refused (403). A web app restart while stopped keeps refunds denied. An
  authorized re-enable resumes refunds, and the evidence records the recovery
  actor.

## Complexity budget

- **Why each custom component is necessary:** The flag reader converts the
  read result into an explicit state ACS can evaluate; the probe makes
  "verified" observable; the in-flight report joins ACS `post_tool_call`
  results with the request time. Everything else reuses AUT-002.
- **Omitted:** Custom stop UI or button (the Azure Portal toggle is the
  button), approval service, database, second agent, APIM, AGT `KillSwitch`,
  Teams card.
- **How shadow evidence is avoided:** Stop state has one source (App
  Configuration); actor identity comes from App Configuration audit logs, not
  from the application.
- **Metadata edge cases:** Flag missing, empty value, malformed JSON, enabled,
  disabled, unreadable (timeout), throttled (429), each tested separately.

## Community fit

- **Learning level:** Intermediate
- **Estimated completion time:** Establish after the first end-to-end run.
- **Prerequisites:** As AUT-002 (Azure CLI, Python 3.12, permission to create
  RBAC role assignments), plus permission to create an App Configuration store.
- **Intentional simplifications:**
  - The same role both stops and recovers; separation of duties and PIM
    activation are further exploration.
  - The synthetic refund ledger is in memory.
  - Evidence is written to the App Service filesystem.
  - Audit logs take several minutes to reach Log Analytics.
- **Further exploration:** PIM-eligible Data Owner, two-person recovery, the
  Foundry Control Plane Stop for a published agent, the AGT `KillSwitch` for
  process termination, the Foundry `cancel` call for background responses, and
  a Teams card as the button.

## Scope boundary

- **Included:** One action-scoped, externally held, fail-closed stop with
  verification, in-flight reporting, RBAC-protected recovery and audit
  evidence.
- **Excluded:** Organization-wide AI shutdown, cancellation or rollback of
  completed refunds, physical safety, protection of tools outside the ACS path.
- **Proves:** After a flag read that does not return `enabled`, ACS refuses
  admission of new refunds from the real agent before execution. Unaffected
  actions continue. The runtime identity cannot lift the stop. The stop
  survives a restart. The stop and recovery actors appear in App Configuration
  audit logs.
- **Does not prove:** Universal coverage, an enforcement-latency SLA, that no
  refund admitted before the stop commits afterwards (no commit-side fencing),
  undoing in-flight effects, in-flight accounting across restarts, or
  separation of duties.
- **Correct and safe within this boundary?** Yes, provided every
  `issue_refund` call goes through ACS and every read failure is treated as
  stopped.

## Decision

- **Proceed / revise / reject:** Proceed.
- **Rationale:** App Configuration supplies a documented, RBAC-protected
  kill-switch state that lives outside the agent; ACS is the enforcement
  surface; Foundry Control Plane cannot provide this action-scoped stop. The
  composition teaches the full stop lifecycle, with custom code limited to the
  flag reader, the verification probe and the in-flight report.
- **Review date:** 2026-11-13
- **Quality bar (agreed 2026-11-14):** Target `Validated`, not `Implemented`: a real Azure end-to-end run in the documented order, captured screenshots or transcripts for every scenario, verified control-owned cleanup, an independent code review per control, and a control-demo-roast before any announcement. The assessment was revised after an independent design review on 2026-11-14.
- **Implementation notes (2026-11-14, after live validation):**
  - *SKU:* App Configuration **Free** supports Entra data-plane RBAC, feature
    flags and the Audit resource log, so it is used. Its daily request quota
    surfaces as `throttled`, which fails closed.
  - *Policy prerequisites:* the validation subscription's resource-type
    allow-list (subscription and management-group assignments) had to be
    extended to App Configuration stores, with the policy owner's approval.
    The `Microsoft.AppConfiguration` resource provider had to be registered.
  - *Deployment:* a synchronous zip deploy hit an App Service build gateway
    timeout (HTTP 504); the deploy script uploads asynchronously and polls the
    platform's deployment record.
  - *Audit:* `AACAudit` records `set-keyvalue` and `delete-keyvalue` with a
    `CallerIdentity` array; `infra/audit.py` reduces its `ObjectId` entry to
    a role (operator or runtime identity) and a hash. Entries arrived within
    about 4 minutes. They do not record the new switch value, and the
    runtime identity's refused write does not appear.
  - *Code review:* an independent review found a fail-open path (a mistyped
    protected tool name skipped the switch), an in-flight report gap (a
    refund still running was omitted) and an unchecked service principal
    deletion in cleanup. All three were fixed with tests before the second
    live pass. Cleanup also had to treat App Configuration's `EntityNotFound`
    as absent.
  - *Validation:* see the README's Validation section. Status: `Validated`.
- **Resolved 2026-11-14:** The `AACAudit` table schema includes a
  `CallerIdentity` column, so the actor for the stop and the recovery comes
  from App Configuration itself. The evidence stores an opaque reference to
  that identity, not a name or email address. If a record is missing or late,
  the evidence states `actor: not_yet_available` instead of inferring an actor.
- **Authoritative references:**
  - [App Configuration feature management (Switch / instant kill switch)](https://learn.microsoft.com/en-us/azure/azure-app-configuration/concept-feature-management)
  - [App Configuration Entra RBAC roles](https://learn.microsoft.com/en-us/azure/azure-app-configuration/concept-enable-rbac)
  - [Monitor App Configuration (Audit logs, AACAudit)](https://learn.microsoft.com/en-us/azure/azure-app-configuration/monitor-app-configuration)
  - [Foundry Control Plane lifecycle operations](https://learn.microsoft.com/en-us/azure/foundry/control-plane/how-to-manage-agents)
  - [ACS stateless runtime guide](https://github.com/microsoft/agent-governance-toolkit/blob/main/policy-engine/docs/stateless-runtime.md)
  - [NIST AI RMF Playbook — Manage 2.4](https://airc.nist.gov/airmf-resources/playbook/manage/)
