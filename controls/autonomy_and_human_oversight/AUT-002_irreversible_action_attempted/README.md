<p align="center">
  <img src="../../../media/themepack/fwf-badge-small-only-logo.png" alt="Forged with Foundry" width="223">
</p>

# AUT-002 - Irreversible action attempted

> **Status:** Implemented - local CLI and release-gated cloud path; Azure
> runtime partially live-verified. Cloud read and prohibited-action denial
> passed; delete is blocked at the exact-action approval prompt. Approved
> cloud execution, negative-role checks and owned-resource cleanup remain
> pending.
>
> **Last reviewed:** 2026-10-07 against the pinned SDKs, control tests and Azure deployment.

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

**Real-life scenario:** An assistant is asked to delete a customer record. The
action cannot be undone, but the assistant treats its own plan as permission
and calls the delete operation anyway. A human approval must be required at
the action boundary, not hidden in the assistant's conversation.

AUT-002 demonstrates a deterministic runtime gate around a synthetic
irreversible action. Agent Control Specification (ACS) escalates every
protected tool call, fails closed without approval, binds approval to the
evaluated action identity, and verifies the result after execution.

> **The agent may propose the action. ACS decides whether the tool may run.**

### Why this matters in a real agent

In a real support, finance, or operations agent, the agent may be able to call
tools that delete records, publish content, approve a request, send a payment,
or change access. The dangerous moment is not when the agent writes, “I will
delete this record.” The dangerous moment is when the delete tool is actually
called.

This control places the human approval check at that exact moment:

1. The agent proposes a protected action.
2. ACS intercepts the tool call before the tool runs.
3. Without approval, ACS blocks the call, so the irreversible action does not happen.
4. An authorized operator approves the exact action.
5. ACS allows that action, then checks the result after the tool returns.

The approval is tied to the exact action, not just to the conversation. If the
agent changes the record, target, or other important arguments after approval,
the approval cannot be reused. In practice, this gives a team a small but
important safety boundary: an agent can remain useful and autonomous for normal
work, while high-impact actions stop for human review before anything
irreversible occurs.

This pattern is useful anywhere an incorrect tool call could create financial,
legal, operational, privacy, or customer harm. It does not require the model
to judge its own safety, and it produces evidence showing whether the action
was blocked, approved, executed, and verified.

### Where the list of protected actions comes from

Declare the action boundary before release; enforce it when the tool is called.
The agent must not classify its own action as safe, reversible or approved.

| Phase / control | Declaration responsibility |
|---|---|
| [TOOL-PRE-001 - Tool inventory](../../tool_governance/TOOL-PRE-001_tool_inventory_incomplete/README.md) | Agent Owner inventories every exposed tool/action. |
| [TOOL-PRE-002 - Tool risk tier](../../tool_governance/TOOL-PRE-002_tool_risk_tier_not_approved/README.md) | Security Officer reviews high-impact tool risks. |
| [AUT-PRE-001 - Autonomy boundary](../AUT-PRE-001_autonomy_boundary_undefined/README.md) | AI Governance owns the allowed/prohibited/conditional mandate and target scope. |
| [AUT-PRE-002 - Human gates](../AUT-PRE-002_hitl_gates_missing/README.md#protected-action-matrix) | Business Owner owns the approval requirement, role, expiry and minimum evidence in that same mandate. |
| **Live: AUT-002** | The release packages the checked mandate; ACS enforces its disposition at the real tool call and the app verifies the result. |

Classify every exposed action, including read-only actions. An action is
**reversible** only when its effects can reliably be undone;
**partially reversible** when recovery leaves residual effects; otherwise it
is **irreversible**. A refund or compensating update is not necessarily an
undo. Reversible actions can still require approval because of their impact.
See the [Pre-Live classification guidance](../AUT-PRE-002_hitl_gates_missing/README.md#determining-reversibility)
for the review evidence behind these decisions.

**Current integration boundary:** AUT-PRE-001 and AUT-PRE-002 independently
evaluate the same mandate against the SDK-built tool definition. The release
wrapper rechecks the evaluated hashes and packages that mandate and definition
for ACS. On the active deployment, the read was allowed, publication denied
before execution, and delete escalated before execution. Protected OIDC
release succeeded. The delete approval/result, role-negative browser checks
and owned-resource cleanup remain unverified. TOOL-PRE-001/002 remain planned;
sample review metadata is not authenticated business-review proof.

## Demo profile

| Property | Value |
|---|---|
| **Demo format** | Deployable demo; local CLI retained for regression checks |
| **Learning level** | Intermediate |
| **Estimated time** | 60-90 minutes (estimate; tenant permissions and cloud build time vary) |
| **Primary decision** | May this irreversible tool call execute with the current approval? |
| **Primary capabilities** | Registered Foundry prompt agent, ACS tool boundaries, Entra app roles, App Service authentication |
| **Deployment** | Required for the cloud path |
| **Infrastructure** | Shared Foundry account; own project/model; one Linux webapp/plan and managed identity |
| **Model/Foundry role** | Active - real agent-generated function call governed by ACS in the Azure webapp |
| **AGT / ACS** | Reused as the real approval and enforcement mechanism |

## Demo scope

### Core demo

The cloud path sends a real request to a registered Foundry prompt agent.
The returned function call reaches ACS in the Azure webapp and is blocked
without approval. An Entra-authenticated `OpsManager` can approve the exact
pending action. ACS then checks its identity, the synthetic tool verifies
record absence, and the application returns the outcome to Foundry.

The active Azure browser path has demonstrated an allowed read, a prohibited
publication denied before execution, and a delete blocked by ACS pending
approval. The local CLI remains a credential-free regression path, not proof
of cloud identity. Approved cloud execution, wrong-role browser denial and
destructive cleanup are not yet live-verified.

### Intentional simplifications

- The record store is in memory and contains synthetic identifiers only.
- Cloud authorization checks a real Entra user role; separate requester and
  approver duties and instant role revocation are not demonstrated.
- Pending approvals are in memory; restart invalidates them.
- Evidence uses `/home/aut002/evidence` on the webapp filesystem, not an
  immutable audit service. No additional database or storage account is required.
- The policy dispatcher is native Python rather than an OPA/Rego bundle.

### What this demo proves

- The active deployment routed the Foundry read, prohibited publication and
  delete requests through ACS with the mandate hash bound to runtime evidence.
- The read was allowed and verified; publication was denied without execution;
  deletion escalated without execution pending human approval.
- Local tests cover exact approval, expiry, replay rejection and result
  verification. They do not establish those outcomes in the cloud browser.

### What this demo does not prove

It does not yet prove approved cloud execution, wrong-role browser denial or
destructive cleanup. It also does not prove universal tool coverage, durable
approval across process restarts, physical deletion, legal compliance or the
ability to undo a completed action. Completeness of the protected-action set
is the Pre-Live responsibility of
[AUT-PRE-002](../AUT-PRE-002_hitl_gates_missing/README.md).

## Control contract

| Field | Value |
|---|---|
| **ID** | AUT-002 |
| **Lifecycle phase** | Live |
| **Category / domain** | Autonomy and Human Oversight |
| **Control / signal** | Irreversible action attempted |
| **Evidence / source** | ACS tool-call decision, approval identity, action result |
| **Trigger / threshold** | One unauthorized attempt |
| **Action / gate effect** | Block action and escalate |
| **Accountable role** | Ops Manager |

## Control objective

Prevent an unauthorized irreversible action from reaching its tool
implementation. Any approval must be current and bound to the exact action
evaluated by ACS. Missing, stale, rejected, mismatched, or unavailable control
decisions fail closed.

## Logical design

```mermaid
flowchart LR
  A[Agent proposes protected tool call] --> P[ACS pre_tool_call]
  P --> D{Approval available?}
  D -->|No or invalid| B[Block and escalate]
  D -->|Yes, exact action| X[Execute synthetic action]
  X --> Q[ACS post_tool_call]
  Q --> V{Result verified?}
  V -->|No or unknown| U[Record unresolved outcome]
  V -->|Yes| E[Record verified evidence]

  classDef governance fill:#6E56CF,stroke:#A855F7,color:#FFFFFF
  classDef platform fill:#3B82F6,stroke:#00D4FF,color:#FFFFFF
  classDef success fill:#22C55E,stroke:#22C55E,color:#0D1117
  classDef attention fill:#F59E0B,stroke:#F59E0B,color:#0D1117
  class A,X platform
  class P,D,Q governance
  class E success
  class B,U attention
```

## Demo infrastructure setup (simplified)

The runtime runs in Azure: a real Foundry prompt agent requests a function
implemented in App Service, where ACS remains an in-process enforcement
library. Entra authenticates the operator; managed identity authenticates the
webapp to Foundry. There is no separate approval service or database.

<p align="center">
  <img src="media/architecture.png" alt="AUT-002 Azure resources: registered Foundry prompt agent and modeldeployment, App Service with ACS and synthetic tool, persistent evidence, managed identity and Entra app roles" width="902">
</p>

Shared infrastructure creates the account, default project and shared GPT-5.
AUT-002 adds its own project and separately named GPT-5 deployment within that
account. Model deployments are account-scoped, not project-scoped. The webapp
has the supported project-scoped `Foundry User` role and account-level inference permissions;
the project is not a claim of complete model isolation.
The `Foundry User` role also permits agent management inside this project.
The narrower Responses runtime role returned HTTP 403 in the real webapp;
the supported role was selected after testing, not as an approval authority.

## Implementation

| Component | Responsibility | Location |
|---|---|---|
| ACS manifest | Declares the guarded tool and intervention points | [policy/acs_manifest.yaml](policy/acs_manifest.yaml) |
| Policy dispatcher | Escalates every irreversible action | [src/aut_002/acs_gate.py](src/aut_002/acs_gate.py) |
| Approval resolver | Enforces current, exact, single-use approval behavior | [src/aut_002/acs_gate.py](src/aut_002/acs_gate.py) |
| Synthetic action | Makes blocked versus executed behavior observable | [src/aut_002/demo.py](src/aut_002/demo.py) |
| Foundry adapter | Registers the prompt agent and validates function calls | [src/aut_002/foundry.py](src/aut_002/foundry.py) |
| Authenticated cloud chat | Checks roles and invokes ACS for the exact pending call | [app.py](app.py), [src/aut_002/cloud_chat.py](src/aut_002/cloud_chat.py) |
| Claims adapter | Maps trusted App Service identity to the approval resolver | [src/aut_002/auth.py](src/aut_002/auth.py) |
| Azure and Entra setup | Deploys resources, app roles and secretless authentication | [infra/deploy.py](infra/deploy.py), [infra/configure_entra.py](infra/configure_entra.py) |
| Evidence writer | Emits minimized control evidence | [src/aut_002/evidence.py](src/aut_002/evidence.py) |
| Focused tests | Validate ACS decisions and fail-closed behavior | [tests/test_acs_gate.py](tests/test_acs_gate.py) |
| Governance schema | Validates declared AUT-002 evidence shape | [schemas/governance-contract/v1alpha1/controls/AUT-002.schema.json](../../../schemas/governance-contract/v1alpha1/controls/AUT-002.schema.json) |

The model is not an approval authority. The protected tool must be invoked
through ACS `run_tool`; a direct call to the synthetic action would be outside
this demonstrated boundary.

## Demo

See the [captured paired mandate walkthrough](../AUT-PRE-001_autonomy_boundary_undefined/docs/DEMO-WALKTHROUGH.md)
for the real allowed read, prohibited publication and separate release/action
approvals. Approved cloud deletion remains pending in that walkthrough.

### Captured cloud block

On the active deployment, an Entra-authenticated request reached the real
Foundry agent and ACS escalated the delete before the synthetic executor ran.
The browser is left at the exact-action approval prompt; no approval or delete
execution is implied.

![Live delete request blocked by ACS](media/mandate-delete-blocked.png)

_Privacy note: the capture is cropped to the ACS message and synthetic target;
browser, account and tenant chrome are excluded._

Excerpt from the actual minimized cloud evidence:

```json
{
  "control_id": "AUT-002",
  "policy_version": "1.0",
  "timestamp": "2026-10-07T13:59:49.165505+00:00",
  "correlation_id": "4fffbe2b-feca-437d-a1a3-d71fc3342c44",
  "tool_name": "permanently_delete_demo_record",
  "decision": "escalate",
  "executed": false,
  "verified": false,
  "reason": "approval_missing"
}
```

This proves only that the observed tool call was escalated and not executed.
It does not prove approved execution, role-negative browser behavior or cleanup.
The [shared walkthrough](../AUT-PRE-001_autonomy_boundary_undefined/docs/DEMO-WALKTHROUGH.md)
contains the complete set of observed handoffs and remaining checks.

### Prerequisites

Have Azure CLI, `uv`, Azure resource deployment/RBAC permissions, and Entra
permissions for applications, service principals, federated credentials and
user app-role assignments. Use existing users in the target tenant. Subscription
ownership alone does not grant directory permissions. Check quota for both
shared and control model deployments.

### Install and bootstrap

Run from the repository root:

```bash
uv venv --python 3.12 .venv
uv pip install -c constraints.txt -r controls/autonomy_and_human_oversight/AUT-002_irreversible_action_attempted/requirements.txt
uv pip check
az login --tenant "<target-tenant-id>"
az account set --subscription "<target-subscription-id>"
```

Obtain tenant/subscription IDs from Azure Portal **Directories + subscriptions**.
Continue only when dependencies pass and `az account show` displays the intended
context. Enter credentials only in the sign-in UI, never chat or source files.

Create the private shared configuration from the repository root without
overwriting an existing environment:

```bash
[[ -f infra/.env ]] || cp infra/.env.example infra/.env
```

Enter `AZURE_SUBSCRIPTION_ID`, `AZURE_RESOURCE_GROUP`, `AZURE_LOCATION` and
a globally unique `FOUNDRY_ACCOUNT_NAME` in `infra/.env`. Use the subscription
selected above, a demo resource-group name and a region with model capacity.
Keep `FOUNDRY_PROJECT_NAME=default-project`; shared GPT-5 capacity defaults to
50 thousand tokens/minute. Never commit the environment. Run:

```bash
./infra/deploy.sh
```

Continue only when it completes and writes the project endpoint and model
deployment name to the gitignored shared environment.

### Configure and deploy AUT-002

From the control directory:

```bash
cd controls/autonomy_and_human_oversight/AUT-002_irreversible_action_attempted
mkdir -p .azure
cp infra/config.env.example .azure/config.env
```

Enter the same tenant, subscription, region, resource group and account in
`.azure/config.env`. Obtain existing user **Object IDs** from Entra **Users >
user > Overview**. Enter the approver ID and optionally a negative-test user ID.
Never commit this configuration or overwrite another environment's file.

```bash
./infra/deploy.sh --check
./infra/deploy.sh
./infra/deploy.sh --status
```

Setup creates the app registration, user-only `OpsManager`/`DemoUser` roles,
assignments, federation and Easy Auth. It registers one prompt-agent version
and uploads the webapp. Upload acceptance is not completion: `--status`
returns exit code 2 while the build is incomplete. Retry the status check
later, not the deployment. Continue only with status `4`, `complete: True`
and an active deployment.

After changing only application code, use `./infra/deploy.sh --code-only`,
then the same `--status` check. This does not recreate identities or resources.

### Open the cloud demo

Use the [shared release and runtime walkthrough](../AUT-PRE-001_autonomy_boundary_undefined/docs/DEMO-WALKTHROUGH.md)
for the single step-by-step procedure and current screenshots. It records the
active deployment's allowed read, prohibited publication denial and delete
escalation, and clearly marks the exact-action approval as pending. Do not
report approved execution until the Entra `OpsManager` completes that action
and the result is verified. Wrong-role browser checks and destructive cleanup
also remain pending.

### Inspect in Azure

| Inspect | Where | Verify |
|---|---|---|
| Owned resources | Resource group > Resources; `control-id: AUT-002` tags where supported | One webapp/plan, identity and control project |
| Model and agent | Foundry account > Model deployments; control project > Agents | `aut-002-gpt-5` and one `aut-002-irreversible-action` prompt agent with the protected function |
| Authentication | Webapp > Settings > Authentication | Microsoft provider, target tenant, authentication required, managed-identity federation |
| Roles and identity | Entra > Enterprise applications > control app > Users and groups; webapp > Identity | `OpsManager`/`DemoUser` assignments; runtime identity has no approval role |
| Enforcement | Cloud chat and `/home/aut002/evidence` | ACS identity, Foundry call correlation, execution and verification |

### Optional local CLI regression

```bash
cd controls/autonomy_and_human_oversight/AUT-002_irreversible_action_attempted
PYTHONPATH=. ../../../.venv/bin/python -m src.aut_002.demo
```

The command creates local `evidence/blocked.json` and
`evidence/approved.json` files and prints both metadata-only records.

### Historical local proof

<details>
<summary>Local CLI and original chat evidence, 2026-09-28</summary>

These screenshots show the original local chat, not Azure hosting or
Entra-authenticated approval. See [Validation](#validation) for the cloud boundary.

The documented command was run on 2026-09-28. It produced one record with
`decision: escalate`, `executed: false`, and `reason: approval_missing`, then
one record with `decision: allow`, `executed: true`, and `verified: true`.
The approved record contained an ACS `sha256:` action identity and the same
correlation identity as the blocked attempt.

The same flow was also tested live through the local Chainlit chat agent:

![AUT-002 live chat start](media/chat-start.png)

_Figure 1. The chat agent presents the protected action and the explicit test steps._

![AUT-002 ACS block](media/chat-blocked.png)

_Figure 2. ACS blocks the action before the synthetic delete tool executes._

![AUT-002 approved action](media/chat-approved.png)

_Figure 3. The Ops Manager approval allows the exact action, and the result is verified._

Captured evidence excerpt:

```json
{
  "control_id": "AUT-002",
  "decision": "allow",
  "action_identity": "sha256:7598b31cf2c0ed5ac3669132f2835305ed329e81a21e19e07a3bb757ad49cecc",
  "executed": true,
  "verified": true,
  "reason": "exact_action_approved_and_verified",
  "accountable_role": "Ops Manager"
}
```

### What the historical local test shows

Read the three screenshots as one real-world moment. In Figure 1 the agent is
about to do something that cannot be undone. In Figure 2 nothing happens,
because ACS stopped the tool call before the delete ran; no one had to trust
the agent to stop itself. In Figure 3 a synthetic approval event approved that exact
action, ACS let it through once, and the demo checked that the record is
really gone before it reported success.

The evidence excerpt is what makes this usable in practice. The
`action_identity` hash ties the approval to this specific tool call and its
arguments, so the same approval cannot be reused for a different record.
`executed` and `verified` are separate fields, so a team can tell the
difference between "the agent said it deleted it" and "it is actually gone."
The `accountable_role` records who was responsible without storing a name or
any record content. See
[Why this matters in a real agent](#why-this-matters-in-a-real-agent) for the
full explanation of the flow.

</details>

## Evidence and observability

Each evidence record includes the control ID, policy version, timestamp,
correlation ID, guarded tool name, ACS identity, decision, execution and
verification status, reason and accountable role. Cloud records also correlate
the Foundry agent version, response and function call. An authenticated
approval adds an opaque keyed approver reference, not a name, email or raw
directory identifier. This is pseudonymous evidence, not a claim of anonymity.
Prompts, answers, tokens, secrets, complete arguments and record content are excluded.

Safe failure diagnostics expose the stage, exception class and HTTP status;
when available, they identify a denied Azure operation. They do not display
the raw service error body, user claims or credentials. A diagnostic is not
approval and is not evidence of successful tool execution.

The governance contract schema validates structural completeness only. It does
not prove that the action was safe, that an approver was authenticated, or
that every agent action passed through ACS.

## Security and privacy

- The action is synthetic and contains no customer data.
- ACS enforcement is outside model reasoning.
- Missing approval and enforcement errors fail closed.
- The demo does not expose secrets or raw prompts in evidence.
- The local CLI ticket is synthetic. Cloud authorization requires trusted
  App Service claims and the `OpsManager` role; prompts and payloads cannot supply it.
- Runtime uses managed identity; Easy Auth uses federation, not a client secret.
  The Chainlit signing secret remains only in protected webapp settings.
- Use synthetic prompts only. Foundry responses are retained until session
  cleanup; governance evidence does not contain prompts or answers.
- A production implementation would need durable approval records, replay
  protection across restarts, current authorization checks and complete tool coverage.

## Validation

On 2026-10-07 shared/control deployments completed, Entra roles and federation
were configured, Oryx deployment status was `4`, Chainlit passed the Azure
startup probe, and unauthenticated browsing redirected to the configured Entra
tenant. A real SDK connectivity probe returned this captured output:

```text
Real registered Foundry agent: aut-002-irreversible-action version 1
Function call received: call_rZeL72eCbUGVOXUhon5NUT39
Strict synthetic target accepted: True
Probe responses deleted.
```

This is not a browser-approval transcript. Authenticated cloud approval,
wrong-role browser denial and
control-resource cleanup remain unverified. Do not call the extension `Validated`.
The cleanup preview was run against the real deployment; no control resources
were deleted. Easy Auth's hybrid `code + id_token` flow is configured with
ID-token issuance enabled and implicit access-token issuance disabled.

A later real authenticated-browser check initially failed at the Foundry
request with `PermissionDeniedError`, HTTP 403. Granting the supported
`Foundry User` role only on the control project corrected the request. The
webapp then obtained a real function call using managed identity and displayed
`Blocked by ACS`, the synthetic target and an action identity. No approval was
granted during this diagnostic check; the record was not deleted. The failed
temporary read-only role was removed. Future deployments use the verified role.

### Live validation checklist

| Check | Current boundary | Required observation |
|---|---|---|
| Real request without approval | Live-observed | Real function call, `escalate`, `executed: false`, record still present |
| Exact Ops Manager approval | Local tests only | Authenticated approver; same identity/correlation; `executed: true`, `verified: true` |
| Wrong-role browser request | Local tests only | `DemoUser` has no approval button; forged callback cannot execute the tool |
| Expiry, decline and replay | Local tests only | Action remains unexecuted; an old or completed approval cannot execute again |
| Unavailable control | Failure and local tests observed | No approval granted and no execution; preserve failure evidence, not a success record |
| Session cleanup | Not live-verified | Only this session's evidence and stored responses disappear |
| Resource cleanup | Preview verified | Recorded control resources and Entra objects absent; shared account/project/model remain |

Complete the remaining browser scenarios first. Retain minimized proof before
session cleanup, then run the ownership-checked resource cleanup and inspect
the retained shared resources. Do not mark the cloud path `Validated` before
approved execution, negative scenarios and cleanup have been demonstrated.

### Troubleshooting

| Symptom | Action | Continue only when |
|---|---|---|
| `foundry_request; PermissionDeniedError; HTTP 403` | Open control project **Access control (IAM)** and verify the webapp's user-assigned identity has `Foundry User`; verify model inference permission on the account. Run control setup if a required assignment is missing. Do not grant `OpsManager` to the runtime identity. | A fresh browser request reaches the ACS block, not a service denial |
| Sign-in returns 401 or an approval session expires | Refresh and complete normal Entra sign-in. Start a fresh request; never reuse an old ticket or extend its expiry to bypass the check. | The authenticated chat starts and a new call has a current identity |
| Upload accepted but the old error text remains | Run `./infra/deploy.sh --status` from the control directory. If it succeeds but the worker is stale, restart only that webapp using the command below, then refresh. | The active worker serves the new code; no success inferred from upload acceptance |
| `unresolved` result or unavailable Foundry follow-up after execution | Inspect execution/verification evidence. Do not retry the delete automatically. | The action outcome is known independently of model narration |

For the stale-worker case, obtain the webapp name from `.azure/deployment.json`
(`webAppName`) and the resource group from `.azure/config.env`, then run:

```bash
az webapp restart --name "<webapp-name>" --resource-group "<resource-group>"
```

This command restarts the process and invalidates pending approvals. It does
not grant approval or delete the synthetic record as a governed action.

Run the focused control tests:

```bash
.venv/bin/python -m pytest controls/autonomy_and_human_oversight/AUT-002_irreversible_action_attempted/tests -q
```

Run the control-contract tests:

```bash
.venv/bin/python -m pytest tests/test_aut_002_governance_contract.py tests/test_governance_contract_consistency.py -q
```

Also run from the repository root:

```bash
az bicep build --file controls/autonomy_and_human_oversight/AUT-002_irreversible_action_attempted/infra/main.bicep --stdout >/dev/null
bash -n controls/autonomy_and_human_oversight/AUT-002_irreversible_action_attempted/infra/deploy.sh
```

Tests cover strict calls/arguments, roles/expiry, prebound action identity,
concurrent replay, changed state, minimized evidence and deployment/cleanup
boundaries. An `unresolved` runtime failure record is not a successful
governance-contract declaration.

## Further exploration

- Persist approval and evidence records in a durable, access-controlled store.
- Add separate requester/approver duties and distributed execution only when
  those become distinct learning outcomes.
- Add multiple irreversible action classes with separate accountable roles.
- Send minimized telemetry to Application Insights or Azure Monitor.

## Cleanup

From the control directory, preview targets first:

```bash
../../../.venv/bin/python infra/cleanup.py
```

Check the targets against `.azure/deployment.json`, then repeat with `--confirm`.
Cleanup stops the webapp and deletes only the recorded agent, control project
and model, webapp/plan, identity, RBAC and Entra application/service principal.
The shared account, default project, model and resource group remain. Keep the
manifest until cleanup is confirmed. Webapp deletion removes its evidence files.

For the optional local CLI, remove only its generated evidence:

```bash
rm -rf controls/autonomy_and_human_oversight/AUT-002_irreversible_action_attempted/evidence
```

Shared infrastructure cleanup is a separate explicit operation in
[infra/README.md](../../../infra/README.md); never delete the shared resource
group as the control's cleanup action.

## References

- [Agent Control Specification](https://github.com/microsoft/agent-governance-toolkit/tree/main/policy-engine)
- [Agent Governance Toolkit](https://github.com/microsoft/agent-governance-toolkit)
- [FwF governance contract](../../../docs/governance-contract.md)
- [Foundry function calling](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/function-calling)
- [App Service Entra authentication](https://learn.microsoft.com/en-us/azure/app-service/configure-authentication-provider-aad)
- [Entra app roles](https://learn.microsoft.com/en-us/entra/identity-platform/howto-add-app-roles-in-apps)
- [AUT-PRE-002 - HITL gates missing (protected-action matrix)](../AUT-PRE-002_hitl_gates_missing/README.md)
- [AUT-PRE-001 - Autonomy boundary undefined](../AUT-PRE-001_autonomy_boundary_undefined/README.md)
- [TOOL-PRE-001 - Tool inventory incomplete](../../tool_governance/TOOL-PRE-001_tool_inventory_incomplete/README.md)
- [TOOL-PRE-002 - Tool risk tier not approved](../../tool_governance/TOOL-PRE-002_tool_risk_tier_not_approved/README.md)
- [Control assessment](ASSESSMENT.md)

---

<p align="center">
    <img src="../../../media/themepack/fwf-footer.png" alt="Forged with Foundry" width="100%">
</p>