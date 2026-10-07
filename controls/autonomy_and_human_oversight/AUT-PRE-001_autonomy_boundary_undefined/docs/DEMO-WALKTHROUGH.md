# Autonomy mandate: release review and runtime decisions

A support assistant can inspect a fictional record, but it cannot publish it.
Deleting the record requires a person's approval. The team declares those
limits before release; the runtime enforces them when the agent requests a tool.

## What the audience can verify

Follow one synthetic agent from a default-deny mandate to the actual built
tools, through a protected release, and into real ACS decisions. A missing
delete gate visibly stops a candidate; the valid release then produces three
distinct runtime outcomes: allow an in-scope read, deny prohibited publication,
and escalate deletion before execution. The handoff evidence shows which
declaration and candidate were checked and what the runtime observed. This is
bounded tool-call governance, not a compliance certification.

## Validation boundary

Captured on **2026-10-07** against the real Azure-hosted AUT-002 demo:

| Observation | Result |
|---|---|
| Credential-free hosted candidate check | Passed for the valid candidate |
| Candidate with a missing delete gate | Failed; dependent release skipped |
| Human GitHub environment review | Approved; not performed by the assistant |
| First release attempt | Azure login failed because the federated subject did not match |
| Retry after correcting federation | Candidate gate and protected release succeeded |
| Azure deployment status | Status `4`; complete and active |
| Cloud read | Allowed; synthetic record present |
| Cloud publication request | Denied; tool not executed |
| Read-session cleanup | Its correlation-specific evidence file was confirmed absent |
| Cloud delete request | Blocked by ACS; exact-action approval is displayed and pending |
| Approved cloud delete | Pending the real OpsManager's action and result verification |

The hosted retry completed successfully, and the documented Azure status
check returned `4`, `complete: True` with an active deployment. The runtime
checks below were run against that active app. Resource cleanup and the
remaining role/expiry/replay browser checks are not established here. Neither
Pre-Live control is marked Validated.

## Two approvals, different authority

| Decision | Who decides | What it authorizes |
|---|---|---|
| Reviewed mandate | AI Governance and Business Owner | Declared scope and human-gate requirements; sample review metadata is not authenticated business-review proof |
| GitHub release approval | Configured environment reviewer | The waiting release job for that workflow run; not an individual tool action |
| Runtime delete approval | Entra-authenticated user with `OpsManager` | One pending ACS action, target and relevant state within its expiry |

Approving a release does not approve every later delete. Conversely, runtime
approval cannot make a prohibited publication permissible. The model proposes
a function call; ACS, not model text, controls execution.

The disposable validation environment permits self-review and retains the
platform's administrator-bypass default. Its approval event demonstrates a
real review pause, not separation of duties or universal bypass prevention.

## Lifecycle at a glance

The two Pre-Live controls stay distinct: AUT-PRE-001 asks whether the agent's
mandate and scope are explicit; AUT-PRE-002 asks whether actions requiring
human oversight have a complete gate. Their contract entries reference the
same mandate bytes. The shared gate evaluates both findings against the actual
SDK-built definition before a protected release can proceed.

```mermaid
flowchart TB
  subgraph DECLARE["1. Declare and assess"]
    Owners["AI Governance + Business Owner"] --> Contract["governance.yaml<br/>AUT-PRE-001 + AUT-PRE-002"]
    Contract --> Mandate["One versioned mandate<br/>scope + action dispositions"]
    Mandate --> Gate["Shared schema, resolver + Rego gate"]
    Definition["Actual SDK-built Foundry definition"] --> Gate
    Gate -->|"Fail: stop release"| Findings["Distinct control findings"]
    Gate -->|"Pass: bind evaluated hashes"| GateEvidence["Gate evidence"]
  end

  subgraph RELEASE["2. Review and release"]
    Human["Human GitHub environment reviewer"] -->|"release approval only"| OIDC["Protected workflow + Entra OIDC"]
    OIDC --> Recheck["Re-run gate; check contract, mandate,<br/>definition against evaluated evidence"]
    Recheck --> Package["Prepare package with checked mandate<br/>and definition"]
    Package --> Publish["Create pinned Foundry version<br/>and deploy app package"]
  end

  subgraph RUNTIME["3. Enforce each tool call"]
    Call["Real Foundry function call"] --> ACS["ACS pre_tool_call<br/>packaged mandate + expected hash"]
    ACS --> Match{"Tool and target in scope?<br/>Disposition?"}
    Match -->|"No, unknown or prohibited"| Deny["DENY<br/>executor not called"]
    Match -->|"Allowed"| Execute["Execute through ACS"]
    Match -->|"Approval required"| Hold["ESCALATE<br/>no execution yet"]
    Hold --> Operator["Entra OpsManager<br/>reviews exact action identity"]
    Operator -->|"Approve while valid"| Execute
    Operator -->|"Decline, expire or mismatch"| Deny
    Execute --> Post["ACS post_tool_call"]
    Post --> Verify["Verify action result"]
  end

  subgraph PROOF["4. Inspect conformance evidence"]
    Event["Minimized event evidence<br/>decision + reason + tool + action identity<br/>execution + verification + correlation<br/>mandate hash"]
    Check["Compare observed event with<br/>declared action and required gate"]
    Outcome["Conformance demonstrated<br/>for this observed action"]
    Gap["Mismatch or unresolved result<br/>stop and investigate"]
    Event --> Check
    Check -->|"Matches"| Outcome
    Check -->|"Mismatch or incomplete"| Gap
  end

  GateEvidence --> Human
  Publish --> Call
  Mandate -. "same declared version" .-> ACS
  Deny --> Event
  Verify --> Event
  Mandate -. "expected disposition and scope" .-> Check

  style DECLARE fill:#172033,stroke:#3B82F6,color:#FFFFFF
  style RELEASE fill:#172033,stroke:#F59E0B,color:#FFFFFF
  style RUNTIME fill:#172033,stroke:#6E56CF,color:#FFFFFF
  style PROOF fill:#172033,stroke:#22C55E,color:#FFFFFF
```

The final comparison is an operator's evidence review in this demo, not a
separate automated compliance-certification service. Azure Policy is also
outside this runtime path: its independent experiment denies selected ARM
requests from tags and does not evaluate the mandate or govern Foundry tool
calls. The lane colors identify lifecycle phases; diamonds are decisions,
solid arrows are execution flow, and dotted arrows carry the expected mandate
version or disposition into later checks.

## Handoff evidence

| Handoff | Consistency mechanism | Observed proof | Boundary of the claim |
|---|---|---|---|
| Declaration to Pre-Live decisions | Both control entries name the same relative mandate path and SHA-256. The resolver reads the attachment; AUT-PRE-001 and AUT-PRE-002 retain separate evidence, owners and findings. | The canonical contract and mandate pass schema validation; the incomplete delete-gate candidate produced `AUT-PRE-002: human_gate_incomplete` and its dependent release was skipped. | The digest binds bytes, not the truth of the declaration, an authenticated business signature, or completeness of actions nobody put in the candidate. |
| Declaration to actual agent | The shared Rego gate compares the resolved mandate with the SDK-built Foundry tool definition; release code checks that definition against `agent_definition()`. | The valid three-tool candidate passed; a missing required human gate failed closed. | The demo covers one synthetic record and its three exposed functions, not an arbitrary tool ecosystem or hidden side effects inside external services. |
| Gate to released artifact | Release re-runs the gate, compares contract, mandate and definition hashes with gate evidence, prepares the package once, and includes the checked mandate and definition. The hosted job checks out the triggering commit and uses protected OIDC. | Candidate gate and protected release succeeded; Azure deployment status was `4`, complete and active. | This is not a signed supply-chain attestation or proof that privileged administrators cannot bypass platform controls. |
| Released agent to runtime decision | The app requires the expected mandate hash, checks the packaged definition and compares the live pinned Foundry version's model/tools; ACS maps each observed call to the packaged disposition and exact target. | On the active deployment, `read_demo_record` was allowed and verified; `publish_demo_record` was denied before execution; delete reached ACS escalation. | Runtime acceptance covers these observed calls. Wrong-role, expiry, replay, every possible invocation path and approved delete execution still need live checks. |
| Runtime decision to evidence | AUT-002 records a bounded event with control/policy version, correlation, action identity, decision/reason, execution/verification and mandate hash; content and arguments are excluded. | The read event says `allow`, executed and verified; publication says `deny`, not executed; delete says `escalate`, not executed. | Evidence supports review of these actions; it is not by itself a compliance verdict, immutable audit retention, or proof of unobserved behavior. |

This is how the controls compose without becoming one vague check: the
Pre-Live controls answer different questions against one declaration, the
release boundary carries the evaluated declaration and candidate forward,
and ACS enforces the declared disposition at the tool boundary. The observed
events can then be checked against that same mandate version. A mismatch,
missing hash, unknown tool or unavailable decision must stop the relevant
path rather than be interpreted as permission.

## 1. Inspect the one declaration

Open [the mandate](../candidate/.fwf/agents/aut-002-irreversible-action/mandate.yaml)
and [its governance contract](../candidate/.fwf/agents/aut-002-irreversible-action/governance.yaml).
Both control entries reference the same attachment and digest:

| Action | Declared disposition | Runtime outcome |
|---|---|---|
| `read_demo_record` | `allowed` | Read presence of `synthetic-record-001` |
| `publish_demo_record` | `prohibited` | Deny; no approval option |
| `permanently_delete_demo_record` | `approval_required` | Escalate; require `OpsManager`, expiry and verified result |

Think of the mandate as a job description, scope as the set of records that
job covers, and sign-off as permission for one exceptional action. The Agent
Owner describes effects, the technical owner verifies recovery, and the
Business Owner owns the human-gate decision. A compensating transaction does
not necessarily undo an effect.

Continue only when every actual SDK-built tool is covered and both entries
reference the reviewed bytes. The digest checks consistency, not truth,
authenticity or the quality of a risk classification.

## 2. Run the credential-free candidate gate

Install the dependencies and pinned Conftest from the
[paired prerequisites](../README.md#prerequisites). From the repository root, run:

```bash
.venv/bin/python controls/autonomy_and_human_oversight/AUT-PRE-001_autonomy_boundary_undefined/demo.py
```

Verify exit code zero and `ALLOWED`. Stop on any finding or evaluation error;
do not use `--build` to silently refresh an altered declaration's review hash.

In GitHub **Actions > Autonomy mandate gate demo**, inspect `candidate-gate`.
The valid candidate passed without Azure credentials. The separately executed
missing-delete-gate candidate failed with `AUT-PRE-002: human_gate_incomplete`;
its release job was skipped. A successful negative test is not authorization
to publish that invalid candidate.

![Successful candidate gate and protected release](../media/release-workflow-success.png)

*Privacy note: captured from the actual completed workflow graph; repository
owner/avatar chrome and the reviewer identity are excluded. The successful
candidate gate, dependent release and skipped independent Policy experiment
remain visible.*

## 3. Approve the waiting release

Use the already-configured disposable repository and protected
`autonomy-mandate-demo` environment. Open its combined workflow run under
**Actions**, verify that `candidate-gate` passed, then select **Review
deployments**, tick **autonomy-mandate-demo**, enter an optional review comment
and select **Approve and deploy**. The configured human reviewer performs
this step directly; an assistant must not approve on their behalf.

Verify that `release` starts. That change proves the review pause was released,
not that Azure authentication, publication or runtime validation succeeded.
The supplied reviewer-dialog and in-progress graph screenshots illustrate
the initial human review. The saved receipt below masks the reviewer identity;
the graph above records the final result, not merely the earlier in-progress
state.

![Protected environment approval receipt](../media/release-human-review.png)

*Privacy note: captured from the real GitHub deployment-protection receipt;
reviewer username and avatar are masked. The approved environment name and
approval event remain visible.*

The observed first attempt failed at `azure/login@v2` after approval. The retry
required a fresh review, then completed the candidate gate and release job.
Stop on a failed job; do not infer success from the approval dialog or an
in-progress graph.

### Resolve an OIDC subject mismatch

For the observed new repository, GitHub's default subject included immutable
owner and repository IDs. The original Entra trust expected the older
name-only subject, so it did not match. Inspect the actual configuration:

```bash
gh api repos/<owner>/<repository>/actions/oidc/customization/sub
```

Obtain `<owner>/<repository>` from the disposable repository's URL. Keep
environment-specific output out of public documentation and screenshots.
When `use_immutable_subject` is true, use the returned `sub_claim_prefix` plus
`:environment:autonomy-mandate-demo`; do not reconstruct it from names alone.
Check issuer and audience as well. The
[setup helper](../../AUT-PRE-002_hitl_gates_missing/infra/setup_oidc.py)
now reads this API and handles the actual default format, rejecting an
unreviewed custom subject configuration.

The repaired retry completed successfully, and the Azure deployment status
reported build `4` complete and active. No token, credential or claims were
printed to create this guide. See
[GitHub's OIDC reference](https://docs.github.com/en/actions/reference/security/oidc)
for subject formats.

## 4. Verify publication before opening the new build

Verify `release` has completed successfully. From the repository root, with
the existing private target configuration and the intended Azure login, run:

```bash
controls/autonomy_and_human_oversight/AUT-002_irreversible_action_attempted/infra/deploy.sh --status
```

Continue only when status is `4`, completion is `True` and the deployment is
active. This run returned exactly that result. Upload acceptance alone is
insufficient; `--status` exits with code 2 while the build is incomplete.
Check status later rather than starting a second release. Then perform the
runtime checks below on a fresh session.

The independent Azure Policy experiment already produced
`RequestDisallowedByPolicy` for both reduced status-tag checks. Follow the
[Policy procedure](../../AUT-PRE-002_hitl_gates_missing/README.md#demo)
for that separate route. Policy does not inspect mandate files, authenticate
status tags, or guard Foundry data-plane publication and ZIP code uploads.

## 5. Open an authenticated cloud session

Open the app URL printed by `--status` and sign in directly through Entra as
the assigned demo user. Never enter credentials in chat, source files or
screenshots. Verify the synthetic record and three action buttons.

![Cloud demo's three mandate actions](../../AUT-002_irreversible_action_attempted/media/mandate-start.png)

*Privacy note: captured only the synthetic demo panel; browser address,
account/tenant chrome and user menu are excluded. The fictional record and
action controls remain visible.*

Sessions and pending approvals expire after five minutes. If an action
redirects to sign-in or reports session expiry, sign in again and start a fresh
request. During this capture run the first read attempt redirected to Entra;
normal authentication was renewed before the successful read below.

## 6. Read within the mandate

Select **Read synthetic record**. Wait for **Allowed within mandate** and
`Synthetic record present: True`. Stop if the service or control is unavailable.

![Real cloud read allowed](../../AUT-002_irreversible_action_attempted/media/mandate-read-allowed.png)

*Privacy note: captured only the result panel; identity and tenant chrome are
excluded. The authoritative result and synthetic presence boolean remain visible.*

This excerpt was read from the real minimized cloud evidence before cleanup:

```json
{
  "timestamp": "2026-10-07T13:46:54.947344+00:00",
  "correlation_id": "574763a4-6b17-4c53-8940-12b0dac8c689",
  "decision": "allow",
  "tool_name": "read_demo_record",
  "executed": true,
  "verified": true,
  "reason": "read_within_mandate"
}
```

Retain the permitted evidence you need, then select **Clean up this demo**.
Wait for a new **AUT-002** start message and use that message's controls.
An immediate next click can report **Resolve the pending action first**
while cleanup is still running. The read's correlation-specific evidence file
was confirmed absent after cleanup; response deletion was not independently
checked against Foundry in this capture phase.

## 7. Request prohibited publication

Select **Request publication** in the new start message. Wait for **Denied
by mandate**. Verify there is no publication approval button; a release review
or an OpsManager role cannot expand the declared mandate.

![Real cloud publication denied](../../AUT-002_irreversible_action_attempted/media/mandate-publication-denied.png)

*Privacy note: captured only the denial panel; identity, account/tenant chrome
and browser address are excluded. The policy outcome remains visible.*

The actual minimized record reported:

```json
{
  "timestamp": "2026-10-07T13:48:57.998003+00:00",
  "correlation_id": "fc82d0ba-7cbe-4785-ade4-892748c490e8",
  "decision": "deny",
  "tool_name": "publish_demo_record",
  "executed": false,
  "verified": false,
  "reason": "mandate_prohibits_action"
}
```

`verified: false` does not mean publication happened. This record is a
pre-execution denial, not a verified execution result. Both observed records
also contained the bound mandate digest; their displayed fields are excerpts,
not the complete evidence contract.

## 8. Request deletion and obtain exact-action approval

Clean up the preceding session and wait for its new start message. Select
**Attempt irreversible action**. Expect **Blocked by ACS**, the delete tool,
the synthetic target, an ACS action identity and five-minute expiry.

![Real cloud delete blocked pending exact-action approval](../../AUT-002_irreversible_action_attempted/media/mandate-delete-blocked.png)

*Privacy note: captured only the ACS block and approval controls; browser,
account and tenant chrome are excluded. The synthetic target, pseudonymous
action identity and five-minute expiry remain visible.*

Inspect that exact target and identity. The real Entra `OpsManager` must
select **Approve exact action** within the pending action's expiry. Expect
**Action executed**, `Verification: True` and the same ACS identity. Verify
that blocked and approved evidence share their correlation ID, that the
approved record reports execution and verification, and that its source
records authenticated approval. Model narration alone is not proof.

The active browser is currently left at this approval prompt. The delete has
not been approved or executed in this capture. If approval expires,
do not retry the old callback: decline or clean up as available, sign in again
and request a fresh action. If the result is unresolved, preserve evidence
and investigate; never automatically retry an irreversible action.

## 9. Clean up the synthetic session

Retain permitted metadata evidence, select **Clean up this demo**, and wait
for the fresh start message. This operation removes only the current session's
evidence and stored Foundry responses, and resets its in-memory synthetic
record. Resetting a fictional demo record is not proof that real deletion
is reversible. It does not remove Azure resources or another session's data.

For infrastructure teardown, use the ownership-checked
[Pre-Live cleanup](../../AUT-PRE-002_hitl_gates_missing/README.md#cleanup)
and [AUT-002 cleanup](../../AUT-002_irreversible_action_attempted/README.md#cleanup)
only for the resources intended for removal. Do not delete the shared resource
group to clean up this paired review demonstration. Destructive resource
cleanup remains unverified.