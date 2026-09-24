<p align="center">
    <img src="../../../media/themepack/fwf-badge-small-only-logo.png" alt="Forged with Foundry control demo" width="223">
</p>

# QLT-001 — Hallucination rate high

> **Status:** Implemented — a real Foundry project and a three-agent fleet of
> `kind: prompt` agents were registered, wired to Continuous Evaluation, and
> run for real end to end: `demo.py setup` → `run` → `evaluate` → `notify`
> all executed live against real Azure resources, including a real, accepted
> Teams delivery (see "Demo" for the exact transcript). Not yet `Validated`:
> Continuous Evaluation's own computed score has not yet been observed to
> surface anywhere queryable, so every live `evaluate` run to date correctly
> reports `cannot_evaluate` rather than a real breach decision — see "Known
> limitations" and `docs/UPSTREAM-FEEDBACK.md`.
>
> **Last reviewed:** 2026-09-25 against `ASSESSMENT.md`, a real deployment,
> and the Microsoft sources it cites.

## Table of contents

* [Overview](#overview)
* [Demo profile](#demo-profile)
* [Demo scope](#demo-scope)
* [Control contract](#control-contract)
* [Control objective](#control-objective)
* [Logical design](#logical-design)
* [Demo infrastructure setup (simplified)](#demo-infrastructure-setup-simplified)
* [Implementation](#implementation)
* [Demo](#demo)
* [Evidence and observability](#evidence-and-observability)
* [Security and privacy](#security-and-privacy)
* [Validation](#validation)
* [Further exploration](#further-exploration)
* [Cleanup](#cleanup)
* [References](#references)

## Overview

An IT helpdesk assistant answers questions from a knowledge base. For months
it answers correctly, because the knowledge base is current. Then part of the
knowledge base quietly goes stale — an article is migrated and never
restored — and the assistant keeps answering just as fluently, except now
it is filling the gap from its own general training instead of the
organization's real, current policy. Nobody notices, because a wrong-but-
confident answer looks exactly like a right one, until an auditor or a
customer acts on it. And the same organization can have several teams
running the same kind of assistant with very different discipline — one
team keeps its knowledge base current, another lets it drift, a third never
had one to begin with — so a single agent's health says nothing about the
fleet's.

This control measures the share of an agent's responses that are **not**
grounded in the context they were given — the "red button" this repository's
maintainer asked for on the human-oversight/groundedness theme, in its
monitoring form rather than an emergency-stop form (see "Further
exploration" for how the two relate) — across a small **fleet** of three
agents representing three teams with deliberately different KB and
instruction rigor, using Microsoft Foundry's own groundedness evaluator via
**Continuous Evaluation** (automatic, sampled scoring of real live traffic,
confirmed live 2026-09-24/25 to accept `kind: prompt` agents — see the note
below) as the authoritative signal. It aggregates each fleet agent's real
scores over a measurement window and opens a **Quality review** the moment
any single agent's hallucination rate exceeds 5% or a single response is
confirmed critically ungrounded — regardless of how confident the response
reads, and regardless of whether the *fleet average* still looks healthy.

> **Why Continuous Evaluation, not batch evaluation.** This control was
> originally built around periodic batch evaluation (`azd ai agent eval`)
> because a first attempt at Continuous Evaluation found that
> `evaluation_rules.create_or_update()` rejects `kind: hosted` and
> `kind: external` agents outright (confirmed on two SDK versions — see
> `docs/UPSTREAM-FEEDBACK.md`'s original findings). A later session,
> prompted by this repository's maintainer asking for a websearch on which
> deployment pattern *does* support it, found and confirmed live that
> **`kind: prompt` agents are accepted**. Getting a real score end to end
> further required three undocumented prerequisites (a `Foundry User` role,
> a real Foundry `AppInsights` connection resource, and a `Monitoring
> Reader` role — see "Best-practice choices") plus a working client-side
> telemetry recipe (`AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING=true`,
> `AIProjectInstrumentor`, and `configure_azure_monitor(credential=...)` —
> this control's Application Insights resource has `DisableLocalAuth: true`,
> so the connection-string-only call path is rejected) plus two more IAM
> roles (`Monitoring Metrics Publisher` for publishing, `Log Analytics
> Reader` for reading). All of that is now live-confirmed working: real
> trace content lands in Application Insights within about a minute of a
> real request. What is **not yet confirmed** is where the rule's own
> computed score itself surfaces — see "Known limitations" and
> `docs/UPSTREAM-FEEDBACK.md`'s "Resolution pass" and "Fourth pass" for the
> full, dated investigation, including one genuine Microsoft SDK bug found
> along the way ([azure-sdk-for-python#46544](https://github.com/Azure/azure-sdk-for-python/issues/46544),
> pre-existing and independently reproduced, not filed by this project).

> **Two self-healing mechanisms, not one.** This control combines two
> independent signals that can each raise groundedness over time, from two
> different perspectives. From the **user's** perspective, every response
> displayed by `demo.py run` carries the agent's own self-reported
> groundedness confidence (1–5) and, when low, its own suggested follow-up
> questions that would help it give a better-grounded answer (see agent.py
> and "Demo") — a real-time nudge toward a better-grounded follow-up in the
> same conversation. From the **Product Owner's** perspective, Continuous
> Evaluation's independent, asynchronous score is this control's actual
> governance signal, driving the Quality review decision. The self-report is
> never a substitute for the independent score — it is the agent's own
> opinion of itself, not a measurement — but together, a real-time nudge a
> user can act on immediately and an async, authoritative signal a Product
> Owner acts on per window give this control two complementary paths that
> can each move a team's real groundedness upward, not just detect when it
> falls.

## Demo profile

| Property | Value |
|---|---|
| **Demo format** | Hybrid demo |
| **Learning level** | Intermediate |
| **Estimated time** | 30–45 minutes, assuming an existing Foundry project and model deployment |
| **Primary decision** | Does this measurement window's aggregated hallucination rate for any single fleet agent (or a confirmed critical hallucination) require a Quality review before the next window is trusted? |
| **Primary capabilities** | Microsoft Foundry `kind: prompt` agents, Continuous Evaluation (`builtin.groundedness`/`relevance`/`retrieval`), Application Insights/Log Analytics, Microsoft Teams Workflows |
| **Deployment** | Required for the core learning outcome |
| **Infrastructure** | One Foundry project + model deployment (shared or control-owned); Log Analytics + Application Insights (`infra/main.bicep`) is required, not optional, for Continuous Evaluation's trace path |
| **AGT / ACS** | Not applicable — this is asynchronous outcome monitoring over sampled live traffic, not an inline intervention on one turn; see `ASSESSMENT.md` |
| **Model/Foundry role** | `Monitored workload` — three real `kind: prompt` agents' live traffic is the measured workload; the decision is computed asynchronously from Continuous Evaluation's own score, not narrated by a second agent |

## Demo scope

### Core demo

Four measurement windows against a fleet of three IT-helpdesk agents — see
`workload.FLEET` — each representing a different team's KB and instruction
rigor:

| Fleet agent | KB rigor | Instruction rigor | Real, live-observed behavior |
|---|---|---|---|
| Platform Team | Never degrades within the demo's 4 windows | Strict — forbidden from guessing | Stays fully grounded throughout |
| Regional Team | Current through window 2, degrades from window 3 | Strict — forbidden from guessing | Correctly refuses to answer once its KB goes stale, rather than inventing |
| Contractor Team | Never had a current article — degraded from window 1 | Permissive — may offer a labeled "reasonable assumption" | Produces real, unscripted fabricated detail (specific VPN client names, invented setup steps) from window 1 onward, confirmed live |

Continuous Evaluation scores each fleet agent's real live traffic
independently (`evaluator.py`'s `measure_agent`); `rollup()` combines the
three into one fleet-level record reporting the fleet average alongside the
best- and worst-performing agent by name — deliberately not only an average,
since an average alone would dilute away exactly the Contractor Team's
regression this demo exists to catch. `demo.py` sends a Teams Adaptive Card
to the Product Owner when any single fleet agent breaches.

### Intentional simplifications

- A small, fixed synthetic knowledge base (three topics) instead of a real
  production retrieval pipeline — keeps the demo reproducible without a real
  document store. Further exploration: point the same agents at a real
  Azure AI Search index.
- Three agents, not a larger fleet — enough to demonstrate a real average/
  best/worst rollup and a genuine single-agent regression without the
  demo's cost or runtime growing unreasonably. Further exploration: extend
  `workload.FLEET` with more profiles.
- The Contractor Team's "weaker instructions" are a deliberate, disclosed
  lever to produce a real breach reliably (see "What this demo proves"), not
  a claim about how any real team's agent should be instructed.

None of these simplifications create an unsafe path: the rate/threshold
policy, the critical-item override, and the fail-closed behavior on
incomplete scoring are unaffected by any of them.

### What this demo proves

That `kind: prompt` agents — not the `kind: hosted`/`external` agents this
control originally assumed — are a real, working path to Continuous
Evaluation today, with a fully documented (if non-obvious) setup recipe;
that `evaluator.py`'s rollup logic correctly combines per-agent measurements
into a fleet average/best/worst without hiding a single agent's regression
(verified so far at the code level, against the real, confirmed per-item
score schema — see "Validation" — not yet against real Continuous
Evaluation scores flowing through it end to end, since none have surfaced
yet); and that this control's own client-side tool-execution loop,
self-report display, and Teams notification pipeline (`demo.py setup` →
`run` → `evaluate` → `notify`) work end to end against real Azure resources
— including a real, accepted (`HTTP 202`) Teams delivery for the fail-closed
`cannot_evaluate` case (see "Demo" for the exact transcript). It also proves
the Contractor Team's weaker instructions produce genuine, unscripted
fabrication live, not a scripted string — see the real captured transcript
in "Demo".

### What this demo does not prove

That Continuous Evaluation's own computed score is retrievable anywhere
today — this was not observed after real traffic and a 20-minute wait (see
"Known limitations"), so no real `quality_review_required` decision driven
by a real score has yet been produced by this control's own `evaluate`
command; that the underlying LLM-judge evaluator is free of false positives
or negatives; that 5% is the correct threshold for any given production
system; that this constitutes regulatory compliance evidence; or that
hallucination is eliminated once the control is in place.

## Control contract

| Field | Value |
|---|---|
| **ID** | QLT-001 |
| **Lifecycle phase** | Live |
| **Category / domain** | Quality |
| **Control / signal** | Hallucination rate high |
| **Evidence / source** | Continuous Evaluation (`builtin.groundedness`/`relevance`/`retrieval`), sampled automatically from each fleet agent's real live traffic. Trace ingestion into Application Insights is live-confirmed; the computed score's own read path is not yet confirmed retrievable — see `docs/UPSTREAM-FEEDBACK.md` |
| **Trigger / threshold** | Any single fleet agent's window hallucination rate > 5%, or any response confirmed critically ungrounded |
| **Action / gate effect** | Quality review |
| **Accountable role** | Product Owner |

## Control objective

Detect a rising rate of ungrounded (hallucinated) responses from any agent
in a monitored fleet before it becomes a quiet, systemic quality failure,
using Foundry's own groundedness evaluator — via Continuous Evaluation — as
the one authoritative signal source per agent, never a second, locally
reimplemented evaluator, and never only a fleet-wide average that a single
regressed agent could hide inside. The decision is **model-assisted
measurement plus a deterministic policy**: each evaluator's pass/fail and
score are untrusted input; the rate threshold, the critical-item override,
the any-agent-breach rule, and the fail-closed rule on incomplete scoring
are deterministic code, not a model judgment. Explicit non-goal: this
control does not remediate the underlying knowledge base or agent
instructions — see "Further exploration".

## Logical design

```mermaid
flowchart LR
    subgraph Fleet["Fleet: kind: prompt agents"]
        F1[Platform Team]
        F2[Regional Team]
        F3[Contractor Team]
    end
    F1 --> C[Continuous Evaluation samples live traffic]
    F2 --> C
    F3 --> C
    C --> R[evaluator.py: per-agent measure, fleet rollup]
    R --> P{QLT-001 fleet policy}
    P -->|Every agent within threshold, no critical item| A[No review required]
    P -->|Any agent breaches rate or critical item| G[Quality review]
    P -->|Scoring retrieval incomplete| B[Cannot evaluate: fail closed]
    G --> O[Notify Product Owner via Teams]
    B --> N[Notify AI Governance Operations via Teams]

    U[User-facing self-report:<br/>confidence + follow-ups] -.->|independent, non-authoritative| F1
    U -.-> F2
    U -.-> F3

    classDef governance fill:#6E56CF,stroke:#A855F7,color:#FFFFFF
    classDef platform fill:#3B82F6,stroke:#00D4FF,color:#FFFFFF
    classDef success fill:#22C55E,stroke:#22C55E,color:#0D1117
    classDef attention fill:#F59E0B,stroke:#F59E0B,color:#0D1117
    classDef nudge fill:#94A3B8,stroke:#94A3B8,color:#0D1117
    class C,R,P governance
    class F1,F2,F3 platform
    class A success
    class G,B,O,N attention
    class U nudge
```

The dashed arrows mark the second, independent, non-authoritative mechanism:
each agent's own self-reported confidence, displayed to the user in real
time (see agent.py and "Demo"), never feeding into the fleet policy itself.
Colors: purple is Continuous Evaluation and the fleet policy's decision
logic, blue is the fleet agents themselves, green/amber are the two
policy-driven outcomes, and gray is the separate, non-authoritative
self-report nudge.

## Demo infrastructure setup (simplified)

This control's infrastructure is minimal: `demo.py`, run locally and
authenticated via `az`/`azd auth login`, orchestrates every step below
against an already-deployed Foundry project. The diagram below is a
different view from "Logical design" above, not a repeat of it: Logical
design shows the decision *branches*; this section describes the building
blocks and data flow that produce the score those branches decide on.

> **The architecture diagram below (`docs/architecture.drawio` /
> `media/architecture.png`) has not yet been redrawn for this fleet
> redesign** — it still depicts the single hosted-agent/batch-evaluation
> architecture from this control's original build and is kept only as
> pre-refactor historical evidence (see "Evidence and observability").
> Regenerating it is tracked in "Further exploration"; the accurate,
> current architecture is described in text below and in the Mermaid diagram
> above.

The current, real architecture: three `kind: prompt` agents are registered
directly via `client.agents.create_version()` (no container, no `azd`
service — see `azure.yaml`'s own comment). `demo.py`'s client-side loop
sends each request via `openai_client.responses.create(agent_reference=...)`,
executing `workload.lookup()` locally whenever the model calls its one tool
(a prompt agent is server-side-only and cannot execute Python itself). The
same process instruments its own outgoing traffic
(`AIProjectInstrumentor` + `configure_azure_monitor(credential=...)`) so that
traffic reaches the Foundry project's Application Insights connection,
where three Continuous Evaluation rules (one per fleet agent) sample it
against a shared, multi-criterion `Eval` definition. `evaluator.py` aggregates
each agent's real per-request results into a fleet rollup, and `demo.py`
notifies Teams Workflows when any agent breaches.

Application Insights/Log Analytics (`infra/main.bicep`) is required for this
architecture, unlike the original batch-evaluation design: it is where
Continuous Evaluation's sampled traces land, and where this control's own
telemetry recipe publishes to.

## Implementation

### Components

| Component | Responsibility | Location |
|---|---|---|
| Fleet agents (`kind: prompt`) | Answer synthetic IT questions from each profile's own KB rigor; self-report groundedness confidence and follow-ups | [agent.py](agent.py), [workload.py](workload.py) |
| Continuous Evaluation | Authoritative groundedness/relevance/retrieval scoring, sampled automatically from each agent's real live traffic | [demo.py](demo.py) `setup_fleet`, [docs/IMPLEMENTATION.md](docs/IMPLEMENTATION.md) |
| Telemetry instrumentation | Wires this process's own traffic into Application Insights, the prerequisite for Continuous Evaluation to have anything to sample | [demo.py](demo.py) `instrument` |
| Decision rubric / policy | Per-agent aggregation, fleet rollup (average/best/worst), 5% threshold, critical-item override, any-agent-breach rule, fail-closed rule | [evaluator.py](evaluator.py) |
| Action/escalation | Teams Adaptive Card to Product Owner or AI Governance Operations | [demo.py](demo.py), [docs/TEAMS-DELIVERY.md](docs/TEAMS-DELIVERY.md) |
| Infrastructure | Log Analytics + Application Insights, an `AppInsights` Foundry connection, and the IAM roles Continuous Evaluation and telemetry publishing need | [infra/main.bicep](infra/main.bicep) |

### Decision rules

1. A window is only evaluable once every fleet agent's Continuous Evaluation
   results have been retrieved; if any agent is missing results, the
   decision is `cannot_evaluate` (fail closed) — never treated as healthy by
   silently rolling up a partial fleet.
2. A response an evaluator itself marks `passed: false` (its own threshold
   decision — see "Best-practice choices" for why the raw score scale is
   deliberately not hardcoded) counts as ungrounded for its agent's rate.
3. `quality_review_required` fires when **any single fleet agent's** window
   ungrounded rate exceeds 5%, **or** any single response scores at or below
   half of its own evaluator's pass threshold (`score <= threshold * 0.5`, a
   critical hallucination) — deliberately per-agent, not only against the
   fleet average, so one regressed team cannot hide behind two healthy ones.
4. `quality_review_required` notifies the Product Owner; `cannot_evaluate`
   notifies AI Governance Operations on a separate channel, so a broken
   measurement path is never mistaken for a healthy window.
5. A notification is sent at most once per window per decision; a prior
   `401`/`403` rejection can be explicitly retried after fixing
   authentication (`--retry-rejected`), nothing else auto-resends.
6. Every displayed response also carries a self-reported groundedness
   confidence and, when below 4, suggested follow-up questions (see
   agent.py) — printed for the user, never persisted as evidence and never
   an input to any of the rules above.

### Best-practice choices

- Foundry's own groundedness/relevance/retrieval evaluators, sampled by
  Continuous Evaluation, are the authoritative signal source, reused
  directly rather than reimplemented — see `ASSESSMENT.md` revision note 5
  for the full pivot from batch evaluation.
- `kind: prompt` is the confirmed-working agent kind for Continuous
  Evaluation today; `kind: hosted` and `kind: external` are both confirmed
  rejected (see `docs/UPSTREAM-FEEDBACK.md`). Each fleet agent's tool
  (`lookup_it_kb`) is declared on the agent but executed client-side by
  `demo.py`, since a prompt agent cannot execute its own tool's Python.
- Telemetry publishing requires three things together, none optional:
  `AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING=true` (the instrumentor silently
  no-ops without it), `configure_azure_monitor(credential=...)` (this
  control's Application Insights resource has `DisableLocalAuth: true`, so
  the connection-string-only call path 401s), and the `Monitoring Metrics
  Publisher` role on that resource (distinct from `Monitoring Reader`, which
  only covers reading).
- Least-privilege, secretless authentication throughout: `AzureCliCredential`
  for every Azure/Foundry call and the Teams bearer token, matching this
  repository's existing `VAL-001` pattern.
- Evidence is content-minimized: no raw prompts, full responses, or
  knowledge-base content beyond a window's aggregate counts and score
  summary.

## Demo

### Prerequisites

- An existing Microsoft Foundry project with one GA chat-model deployment.
- `azd` and the Azure CLI, authenticated (`az login`, `azd auth login`).
- Python 3.13, this repository's root virtual environment:
  `python -m venv .venv && .venv/bin/pip install -r requirements.txt`.
- Two Teams Workflows webhooks (Product Owner, AI Governance Operations) —
  see [docs/TEAMS-DELIVERY.md](docs/TEAMS-DELIVERY.md).

### Deploy

```zsh
cd controls/grounding_and_quality/QLT-001_hallucination_rate_high
azd auth login
azd up
```

`azd up` provisions the Log Analytics workspace, Application Insights, the
Foundry project's `AppInsights` connection, and the IAM roles
`infra/main.bicep` declares. Then register the fleet and its Continuous
Evaluation rules — real, confirmed working end to end (see "Validation"):

```zsh
.venv/bin/python demo.py setup
```

### Inspect in Azure

| What to inspect | Where in Azure Portal / Foundry portal | What to verify and why it matters |
|---|---|---|
| Fleet agents | Foundry project → Agents → `it-helpdesk-kb-assistant-platform` / `-regional` / `-contractor` | Each shows `kind: prompt`, `state: enabled`; confirms all three are registered and reachable |
| Continuous Evaluation rules | Foundry project → Evaluations → the three `*-rule` entries | Each shows `enabled: true` and its own agent-name filter |
| Application Insights | Azure Portal → the control's `appi-qlt001-*` resource → Logs | `AppGenAIContent` should show real rows with populated `AgentName`/`InputMessages`/`OutputMessages` after `demo.py run` — confirms the telemetry path is working, independent of whether a score has appeared yet |

### Run or complete the exercise

```zsh
cd controls/grounding_and_quality/QLT-001_hallucination_rate_high
WINDOW_OUTPUT=$(.venv/bin/python demo.py run --window 1)
printf '%s\n' "$WINDOW_OUTPUT"
WINDOW_ID=$(printf '%s\n' "$WINDOW_OUTPUT" | sed -n 's/^Window: \([0-9a-f-]*\).*/\1/p')
.venv/bin/python demo.py evaluate --window-id "$WINDOW_ID"
.venv/bin/python demo.py notify --window-id "$WINDOW_ID"
```

Repeat with `--window 2`, `--window 3`, and `--window 4` to walk the
healthy-to-drift story for the Platform and Regional Teams (the Contractor
Team is degraded from window 1 onward by design — see "Demo scope").

**Real captured evidence (2026-09-25), from actually running the live
fleet** — window and topic labels below are this control's own synthetic
scenario, not sensitive data; tenant, subscription, and resource identifiers
are excluded per this repository's confidentiality conventions:

Window 1, Platform Team (`vpn_setup`, current KB article) — fully grounded,
self-reported confidence 5/5:

```text
[Platform Team] vpn_setup: Current VPN client: SecureConnect 4.2. Users
authenticate with their Entra ID account and use the Contoso VPN profile
pushed by Intune. For access issues, open a ticket in queue IT-VPN.
  self-reported confidence: 5/5
```

Window 4, Regional Team (`vpn_setup`, article fully removed) — correctly
refuses to invent a replacement rather than degrading silently:

```text
[Regional Team] vpn_setup: No current knowledge-base article is available
for vpn_setup. Please open a helpdesk ticket so the support team can
assist you.
  self-reported confidence: 5/5
```

Window 4, Contractor Team (`vpn_setup`, no article ever existed, permissive
instructions) — real, unscripted fabrication, labeled as an assumption but
still specific, invented detail no tool call returned:

```text
[Contractor Team] vpn_setup: I could not find a current internal article
for VPN setup. Below are reasonable, clearly labeled assumptions based on
common corporate VPN practices you can try: ... common ones: Cisco
AnyConnect, Palo Alto GlobalProtect, FortiClient, OpenVPN ...
  self-reported confidence: 3/5
  suggested follow-ups to improve groundedness:
    - Which operating system are you using (Windows/macOS/Linux)?
    - Do you know which VPN client or gateway address your organization uses?
```

This is the real, live-measured differentiation this fleet is designed to
demonstrate: the same absent-KB condition produces an honest refusal under
strict instructions and genuine fabrication under permissive ones — see
`docs/UPSTREAM-FEEDBACK.md` for how the tool-calling and structured
self-report loop was confirmed end to end.

`demo.py setup` → `run --window 1` → `evaluate --window-id ...` → `notify
--window-id ...` was run back to back, unassisted, in one continuous live
pass (2026-09-25). Because Continuous Evaluation's own computed score has
not yet been observed to surface anywhere queryable (see "Known
limitations"), `evaluate` correctly reported `cannot_evaluate`, and `notify`
produced a real, accepted Teams delivery to AI Governance Operations:

```json
{
  "window_id": "e8dfa01e-2ca3-47b6-83bc-c2d99bbc48e9",
  "decision": "cannot_evaluate",
  "reason": "evaluation_retrieval_unavailable_or_partial",
  "notification": {"status": "accepted", "http_status": 202,
                    "recipient_role": "AI Governance Operations"}
}
```

This demonstrates the exact reader-visible step this control exists for even
in its current, not-yet-`Validated` state: a real measurement gap was
detected, correctly refused to be treated as healthy, and correctly escalated
to the accountable role for a broken measurement path — rather than the
Product Owner path, since no real breach has been measured yet.

### Expected scenarios

| Scenario | Input | Expected decision | Expected evidence |
|---|---|---|---|
| Healthy | `--window 1` or `--window 2`, Platform/Regional Teams | `no_review_required`, once the score-read path is confirmed | Per-agent record: rate at/near 0%, no critical items |
| Threshold reached | `--window 3`/`--window 4` (Regional Team drift), or any window (Contractor Team, degraded from window 1) | `quality_review_required`, once the score-read path is confirmed | Fleet record: worst-performing agent identified by name; Teams card to Product Owner |
| Scoring incomplete | Any window today, since Continuous Evaluation's score read path is not yet confirmed retrievable | `cannot_evaluate` | Fleet record: `reason: evaluation_retrieval_unavailable_or_partial`; Teams card to AI Governance Operations, never treated as healthy — real, captured above |

## Evidence and observability

Each window's evidence record (`.azure/qlt001/windows/<window_id>/evidence.json`,
git-ignored) carries: control/policy/evidence version, window number,
correlation id (the window id), per-agent measurement (sample size,
ungrounded/critical run ids, rate, average score), fleet average/best/worst,
decision, reason, accountable role, and the notification's own status
(`not_requested` / `attempted` / `accepted` / `rejected` / `delivery_unknown`
/ `delivered`). It never carries raw prompts, full responses, or
knowledge-base article content.

**Historical evidence, pre-refactor (2026-09-23):** `media/architecture.png`
(and its source `docs/architecture.drawio`), `media/foundry-eval-results.png`,
and `media/teams-quality-review-required.png` all depict this control's
original single hosted-agent, batch-evaluation design, retired in favor of
the fleet/Continuous Evaluation design described above. They are kept as a
dated historical record of that earlier, also-real verification pass, not as
current architecture — see "Demo infrastructure setup (simplified)".

## Security and privacy

- **Trust boundaries:** every fleet agent only ever answers from its own
  synthetic in-repository knowledge base (`workload.py`); none accesses real
  systems or personal data. Only the Contractor Team's instructions permit
  labeled speculation when its KB returns nothing — a deliberate, disclosed
  demo lever, not a production recommendation.
- **Identity:** `AzureCliCredential` throughout — the Foundry/telemetry API
  calls, the Teams bearer token, and this process's own telemetry export —
  no embedded secret or API key.
- **Data minimization:** evidence and Teams cards carry only window-level
  counts, run ids, and the decision — never a full prompt or response.
- **Secret handling:** Teams webhook URLs are entered via hidden input into
  `azd`'s local, git-ignored environment, never printed, logged, or
  committed.
- **Fail-closed behavior:** incomplete or unavailable Continuous Evaluation
  results are reported as `cannot_evaluate`, routed to AI Governance
  Operations, and never silently treated as a healthy window — demonstrated
  live in "Demo" against a real, currently-open measurement gap, not a
  simulated one.

## Validation

### Automated tests

```zsh
.venv/bin/python -m pytest controls/grounding_and_quality/QLT-001_hallucination_rate_high/tests -q
```

- `tests/test_evaluator.py` — per-agent measurement, fleet rollup
  (average/best/worst), the any-agent-breach rule, and fail-closed decision
  logic against the real, confirmed `passed`/`score`/`threshold` schema.
- `tests/test_workload.py` — each fleet profile's scripted KB staleness
  curve.
- `tests/test_agent.py` — each fleet profile's tool/response-schema
  declaration and its strict-vs-permissive instruction wording.
- `tests/test_demo.py` — Teams card content (fleet facts, best/worst
  agents), notification routing, at-most-once delivery, and receipt
  verification.
- `tests/test_cleanup.py` — cleanup refuses any target outside this
  control's tagged, name-prefixed, `kind: prompt`-verified fleet agents.

All 92 evaluator/workload/agent/cleanup/demo tests pass locally (verified
2026-09-25, this repository's root `.venv`).

### Manual checks performed live (2026-09-25)

- Registered all three real fleet agents (`kind: prompt`) against a live
  Foundry project via `demo.py setup`; confirmed each reaches `state:
  enabled` with its own Continuous Evaluation rule attached and `enabled`.
- Ran `demo.py run --window 1` for real: 9 live invocations across the
  three agents, each displaying its real answer alongside its real
  self-reported confidence — including genuine, unscripted fabrication from
  the Contractor Team (see "Demo").
- Ran `demo.py evaluate` and `demo.py notify` for real against that same
  window, back to back, unassisted: a real `cannot_evaluate` decision and a
  real, accepted (`HTTP 202`) Teams delivery to AI Governance Operations —
  see the captured transcript in "Demo".
- Confirmed real trace content (`AgentName`, `InputMessages`,
  `OutputMessages`) reaches `AppGenAIContent` in Log Analytics within
  roughly 1–2 minutes of a real request, once the full instrumentation and
  IAM chain in `docs/UPSTREAM-FEEDBACK.md` is applied.
- Polled for 20 minutes after sending real traffic through a rule-attached
  fleet agent, checking both `openai_client.evals.runs.list()` and
  `AppGenAIContent`'s `EvaluationExplanation` column: no computed score
  appeared on either surface — see "Known limitations" and
  `docs/UPSTREAM-FEEDBACK.md`'s "Fourth pass".

### Known limitations

- **Continuous Evaluation's own computed score has not yet been observed
  anywhere retrievable**, despite every documented prerequisite being met
  and real trace content confirmed landing in Application Insights. Every
  live `evaluate` run to date correctly reports `cannot_evaluate` rather
  than a real breach decision. Status stays `Implemented`, not `Validated`,
  until a real score is observed and a real `quality_review_required` (or
  `no_review_required`) decision replaces this note — see
  `docs/UPSTREAM-FEEDBACK.md`.
- **The Contractor Team's fabrication was only captured for one topic in one
  window in this document** (see "Demo"); the full four-window walk across
  all three agents and all three topics has been run live (`demo.py run`)
  but not exhaustively transcribed here.
- **Real-model non-determinism.** Each evaluator's score, and each agent's
  own behavior, depends on real model behavior, not a deterministic ground
  truth (unlike, for example, this repository's `VAL-001`). The specific
  fabricated content shown in "Demo" is a real, captured example, not a
  guaranteed output of every run.
- Groundedness detection currently supports English content only, per
  Microsoft's own Content Safety groundedness documentation (background on
  the underlying evaluator family).

## Further exploration

| Topic | Core demo | Possible extension | Microsoft guidance |
|---|---|---|---|
| Confirming Continuous Evaluation's score read path | Not yet found — see "Known limitations" | Follow up directly with the Foundry Observability PG once `docs/UPSTREAM-FEEDBACK.md`'s open questions are answered | See `docs/UPSTREAM-FEEDBACK.md` |
| Architecture diagram | Text-only (Mermaid + prose) reflects the fleet/Continuous Evaluation design; `docs/architecture.drawio`/`media/architecture.png` still show the retired single-agent/batch design | Redraw the diagram for the fleet architecture described in "Demo infrastructure setup" | Not applicable |
| Inline enforcement | Not included — this control only monitors and reports | Pair with `RUN-001` (low confidence or grounding score) once assessed, using the real-time Groundedness Detection Filter for inline blocking | [Groundedness Detection Filter — Microsoft Foundry](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/content-filter-groundedness) |
| Remediation | Not included — deliberately deferred, per this control's own scope | A follow-up control or workflow that acts on a confirmed knowledge-base gap (for example, opening a KB-update ticket) | See "After a Quality review" below |
| Fleet size | Three agents | Extend `workload.FLEET` with more team profiles | Not yet assessed |
| Scheduling | Manual window-by-window demo run | Trigger `demo.py evaluate` on a recurring schedule (for example, an Azure Function timer) | Not yet assessed |

### After a Quality review: where to actually improve groundedness

This control's own scope stops at **detecting** a hallucination-rate breach
for any fleet agent and notifying the Product Owner — it deliberately does
not change any agent, knowledge base, or retrieval pipeline itself (see
"Control objective"). The Product Owner still needs a next step once the
Teams card arrives. `evaluator.py`'s own evidence deliberately stops at the
minimized rate/threshold/critical-item record — it does not carry an
evaluator's per-item `reason` or `properties.dimension_scores`, since those
can quote fragments of the actual response (see "Evidence and
observability"'s data minimization rule). For root-cause diagnosis, a
reviewer opens the real evaluation results in the Foundry portal instead.
From there, root-cause remediation generally falls into one of these
directions, depending on what the diagnosis points to:

- **The source content is stale, incomplete, or missing** (the Regional and
  Contractor Teams' own scenario in this demo). Fix the content at its
  source and re-run to confirm the rate recovers. There is no single
  Microsoft tool for this — it is a knowledge-ownership and
  content-freshness process question; if this repository later implements a
  `data_and_knowledge` category control for knowledge/content freshness,
  cross-reference it here instead of duplicating the guidance.
- **The retrieval step is surfacing the wrong or insufficient context**, if
  an agent's tool is backed by real search rather than this control's
  simple fixed lookup. Tune retrieval relevance (hybrid search, semantic
  ranking, scoring profiles) per [RAG and generative AI — Azure AI
  Search](https://learn.microsoft.com/en-us/azure/search/retrieval-augmented-generation-overview)
  and the [classic RAG relevance-tuning
  tutorial](https://docs.azure.cn/en-us/search/tutorial-rag-build-solution-maximize-relevance),
  and re-evaluate with the [RAG groundedness/relevance
  evaluators](https://learn.microsoft.com/en-us/azure/ai-foundry/concepts/evaluation-evaluators/rag-evaluators?view=foundry-classic)
  to confirm the fix.
- **The model has good context but still answers ungrounded, or has weak
  instructions that permit speculation** (the Contractor Team's own scenario
  in this demo). Strengthen the system instructions — explicit "answer only
  from the tool result; say so if information is missing" framing, few-shot
  grounded/ungrounded examples — per general [Azure OpenAI prompt
  engineering
  guidance](https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/prompt-engineering),
  or let Microsoft's own [Prompt Optimizer
  (preview)](https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/prompt-optimizer)
  restructure the instructions automatically and re-evaluate before and
  after.
- **Systematic, ongoing improvement rather than a one-off fix.** [Agent
  Optimizer in Foundry Agent Service
  (preview)](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/agent-optimizer-overview)
  is built specifically to consume evaluation results like the ones this
  control already produces, generate ranked candidate prompt/skill changes,
  and show a before/after comparison with full diff, lineage, and rollback —
  a more systematic option than manually iterating on the instructions.
- **Inline mitigation for the specific response, not the underlying cause.**
  Azure AI Content Safety's groundedness detection includes an automatic
  **correction** feature that rewrites an ungrounded span to match the
  supplied grounding source before it reaches the user — see [Groundedness
  detection — Azure AI Content
  Safety](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/groundedness)
  (preview). This treats a symptom per response; it does not replace fixing
  the content or retrieval gap that caused it, and pairs naturally with
  `RUN-001`'s inline enforcement extension above rather than with this
  control's own Continuous Evaluation path.

None of the above is implemented by this control — they are the documented,
cited next steps for whoever receives the Quality review, kept out of this
control's own bite-sized scope on purpose.

### Why this control does not automate remediation

It would be tempting to close the loop entirely — detect a breach and fix it
without a human — but that does not hold up once the three ways to
"automate" it are separated out:

1. **Inline correction of one response.** Azure AI Content Safety's
   groundedness detection can automatically rewrite an ungrounded span to
   match the grounding source already supplied (see "After a Quality review"
   above). This only works when a grounding source exists but was ignored or
   misused — it has nothing to correct against for the Regional and
   Contractor Teams' own scenario (an article removed or never populated),
   and it treats one response, not the recurring cause.
2. **Automatically rewriting the knowledge base.** Not viable as an
   unsupervised process: deciding what the correct, current organizational
   content should say is a human/business judgment, not a technical one.
   Having a model auto-generate "corrected" official content reintroduces
   the same hallucination risk this control exists to catch, one layer
   removed — an ungrounded fix for an ungrounded answer.
3. **Automatically containing exposure** (pausing an agent or falling back
   to a safe mode once a breach is confirmed) is the one form of automation
   that stays defensible, because it removes access rather than asserting a
   judgment. It is also explicitly out of this control's own scope — that is
   what an emergency-stop control (`AUT-004`, planned in this repository's
   `autonomy_and_human_oversight` category) is for, not a quality-monitoring
   control. The self-reported confidence and follow-up questions this
   control does display (see Overview) are a deliberately narrower, softer
   mechanism than any of these three — a nudge the user can act on, not an
   automated action this control takes on anyone's behalf.

This follows the same authority boundary this repository applies
everywhere: an agent, or an automated pipeline acting on its behalf, may
explain or orchestrate a decision, but must not grant its own approval or
claim an action succeeded without independent, human-accountable
verification. `PRI-002`, `PRI-003`, and `PRI-004` in this repository apply
the identical pattern for a different signal — a deterministic policy
detects the issue, but the actual remediating action stays behind an
explicit human or independently-verified approval boundary. Automatic
content remediation would break that boundary for a decision that is
squarely a human one.

### Community ideas

- Point `workload.py` at a real Azure AI Search index instead of the
  in-repository knowledge base, and compare the resulting groundedness
  scores per fleet agent.
- Add a category `ARCHITECTURE.md` for `grounding_and_quality`, recording
  this control's fleet/Continuous Evaluation design so `QLT-002`, `QLT-005`,
  and `QLT-006` reconcile with it instead of redefining it (see
  `ASSESSMENT.md`).
- Follow up on `docs/UPSTREAM-FEEDBACK.md` once Microsoft confirms where a
  Continuous Evaluation rule's computed score surfaces.

## Cleanup

```zsh
cd controls/grounding_and_quality/QLT-001_hallucination_rate_high
.venv/bin/python infra/cleanup.py --subscription <subscription-id> \
  --resource-group <resource-group> --project-endpoint <foundry-project-endpoint>
```

Run without `--confirm` first to inspect the exact targets; add `--confirm`
to delete them. This removes only this control's tagged
(`control-id: QLT-001`) Application Insights and Log Analytics resources,
and its three verified (`kind: prompt`), name-prefixed fleet agents and their
sessions — never a shared resource group, Foundry project, or another
control's resources. The Eval definition and its three per-agent Continuous
Evaluation rules, and any Teams messages already delivered, require separate
manual cleanup in the Foundry portal and Teams — see
`docs/IMPLEMENTATION.md` and `docs/TEAMS-DELIVERY.md`.

## References

- [azure-sdk-for-python#46544 — ResponsesInstrumentor crashes on NonRecordingSpan](https://github.com/Azure/azure-sdk-for-python/issues/46544) (pre-existing Microsoft SDK bug, independently reproduced while building this control — see `docs/UPSTREAM-FEEDBACK.md`)
- [Quickstart: Continuously evaluate your AI agents — Microsoft Learn](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/continuous-evaluation-agents?view=foundry&preserve-view=true)
- [Generally Available: Evaluations, Monitoring, and Tracing in Microsoft Foundry](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/generally-available-evaluations-monitoring-and-tracing-in-microsoft-foundry/4502760)
- [Groundedness Detection Filter — Microsoft Foundry](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/content-filter-groundedness)
- [Groundedness detection — Azure AI Content Safety](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/groundedness) (preview)
- [Create and manage Teams incoming webhooks with Workflows](https://learn.microsoft.com/en-us/microsoftteams/platform/webhooks-and-connectors/how-to/add-incoming-webhook)
- Full assessment and capability review: [ASSESSMENT.md](ASSESSMENT.md)
- Draft status-check for Microsoft: [docs/UPSTREAM-FEEDBACK.md](docs/UPSTREAM-FEEDBACK.md)
- Source catalog: [Governance Signals Repo.pdf](../../../docs/Governance%20Signals%20Repo.pdf)

---

<p align="center">
    <img src="../../../media/themepack/fwf-footer.png" alt="Forged with Foundry" width="100%">
</p>
