---
description: "VAL-001 KPI underperformance implementation in progress and captured validation evidence"
---
<p align="center">
    <img src="../../../media/themepack/fwf-badge-small-only-logo.png" alt="Forged with Foundry planned control" width="223">
</p>

# VAL-001 — KPI underperformance

> **Status:** Planned. The live value-review path is proven; complete data cleanup, the additional measurement-failure notification route, and clean-checkout onboarding remain release blockers.
>
> **Last reviewed:** 2026-09-21.

## Table of contents

- [Overview](#overview)
- [Control contract](#control-contract)
- [Control objective](#control-objective)
- [Logical design](#logical-design)
- [Infrastructure architecture](#infrastructure-architecture)
- [Implementation](#implementation)
- [Demo](#demo)
- [Evidence and observability](#evidence-and-observability)
- [Security and privacy](#security-and-privacy)
- [Validation](#validation)
- [Cleanup](#cleanup)
- [References](#references)

## Overview

A helpdesk manager expects an assistant to resolve routine tickets without
human handling. If that stops happening, staff inherit the work while the
manager may still believe the assistant is meeting its target. This control
requests a value review when verified outcomes remain below the agreed limit.

The approved design is in [ASSESSMENT.md](ASSESSMENT.md). Target 35 means an
absolute 35% deflection rate. A review requires both consecutive periods to
be strictly below 28%; equality does not trigger a review. The agent is a
Monitored workload, without an inline ACS gate.

| Demo profile | Value |
|---|---|
| Format / level | DEPLOYABLE_DEMO / Intermediate |
| Estimated time | 45-60 minutes after access setup |
| Primary decision | Request a review after two periods below 80% of the absolute target |
| Capabilities | Agent Framework, Foundry, Application Insights, Log Analytics, Teams Workflows |
| Deployment / infrastructure | Required; existing Foundry project/model, isolated Monitor resources |
| AGT / ACS | Not used for this asynchronous monitored workload |

> [!IMPORTANT]
> To implement the control, start with the numbered
> [implementation path](#implementation-path), then run the
> [demo](#demo). To understand the design first, read the
> [logical design](#logical-design). To review proof from the completed test,
> go directly to [captured validation evidence](#captured-validation-evidence).

## Control contract

| Field | Value |
|---|---|
| **ID** | VAL-001 |
| **Lifecycle phase** | Live |
| **Category / domain** | Value |
| **Control / signal** | KPI underperformance |
| **Evidence / source** | KPI vs target dashboard |
| **Trigger / threshold** | <80% target for 2 periods |
| **Action / gate effect** | Value review |
| **Accountable role** | Business Owner |

## Control objective

Connect the declared value hypothesis to verified outcomes. The agent performs
synthetic work; the deterministic evaluator reads target and owner through the
shared contract validator. Missing or ambiguous data yields `cannot_evaluate`,
never a healthy result. See [deployment and validation details](docs/IMPLEMENTATION.md).

## Logical design

```mermaid
---
config:
  layout: dagre
  look: classic
---
flowchart LR
  subgraph sources[Authoritative inputs]
    contract["governance.yaml<br/>VAL-PRE-001 target + owner"]
    telemetry["Application Insights<br/>TicketTriaged events"]
  end
  subgraph decision[VAL-001 control logic]
    query["Log Analytics workspace<br/>KQL query for two periods"]
    evaluator["evaluator.py<br/>Deterministic 80% threshold"]
    record["evidence.json<br/>Decision and measured rates"]
  end
  subgraph action[Governance action]
    reviewNotify["Power Automate Teams Workflow<br/>Value review notification"]
    owner["Business Owner<br/>Reviews the outcome"]
    governanceNotify["Power Automate Teams Workflow<br/>Measurement failure notification"]
    governance["AI Governance Operations<br/>Restores the measurement path"]
  end

  telemetry --> query --> evaluator
  contract --> evaluator
  evaluator --> record
  record -->|review_required| reviewNotify --> owner
  record -->|cannot_evaluate| governanceNotify --> governance
  record -->|no_review_required| endstate["No notification<br/>Healthy or no trigger"]

  style sources fill:#172033,stroke:#60A5FA,color:#FFFFFF
  style decision fill:#211B38,stroke:#A855F7,color:#FFFFFF
  style action fill:#302516,stroke:#F59E0B,color:#FFFFFF
  classDef input fill:#3B82F6,stroke:#00D4FF,color:#FFFFFF
  classDef control fill:#6E56CF,stroke:#A855F7,color:#FFFFFF
  classDef evidence fill:#00D4FF,stroke:#3B82F6,color:#0D1117
  classDef actionNode fill:#F59E0B,stroke:#F59E0B,color:#0D1117
  classDef success fill:#22C55E,stroke:#22C55E,color:#0D1117
  classDef neutral fill:#1F2937,stroke:#6E56CF,color:#FFFFFF
  class contract,telemetry input
  class query,evaluator control
  class record evidence
  class reviewNotify,owner,governanceNotify,governance actionNode
  class endstate neutral
```

> [!NOTE]
> **Relationship to Policy as Code:** VAL-001 connects the pre-live value
> hypothesis and baseline to live outcome monitoring. The value hypothesis
> supplies the schema-validated target and Business Owner that VAL-001 reads
> and revalidates. The baseline declaration establishes that a measured
> starting point exists or that the workload is `net_new`; it provides
> governance context but is not an input to this target-attainment
> calculation. The shared Rego deployment gate can require both declarations
> before deployment, but it does not evaluate runtime KPI performance.

## Infrastructure architecture

```mermaid
---
config:
  layout: dagre
  look: classic
---
flowchart TB
  subgraph azure[Azure subscription, control-owned resources]
    appi["Azure Application Insights<br/>Microsoft.Insights/components<br/>Ingests custom events"]
    law["Azure Log Analytics workspace<br/>Microsoft.OperationalInsights/workspaces<br/>Stores and queries AppEvents"]
    rbac["Azure RBAC role assignment<br/>Monitoring Metrics Publisher<br/>Allows telemetry publishing"]
    appi -->|Workspace-based ingestion| law
    rbac -.->|Scoped to| appi
  end
  subgraph foundry[Microsoft Foundry, hosted workload]
    project["Foundry project<br/>azure.ai.project<br/>Hosts the deployment"]
    agent["Hosted Foundry agent<br/>azure.ai.agent<br/>helpdesk-tier1-triage"]
    identity["Microsoft Entra managed identity<br/>DefaultAzureCredential<br/>No embedded credentials"]
    project --- agent
    identity -.->|Authenticates| agent
  end
  subgraph control[Developer or pipeline execution context]
    bicep["Bicep deployment<br/>infra/main.bicep<br/>Creates App Insights + workspace"]
    runner["demo.py<br/>Runs synthetic ticket batches<br/>Queries KQL and calls evaluator"]
    evaluator["evaluator.py<br/>Writes .azure/val001/runs/*/evidence.json"]
    contract["Governance contract fixture<br/>VAL-PRE-001 target + owner<br/>Read-only Stream A"]
    bicep -.->|Provision once| azure
    runner --> evaluator
    contract --> evaluator
  end
  subgraph external[Microsoft 365 tenant, external integration]
    businessFlow["Power Automate Teams Workflow<br/>Business Owner webhook"]
    business["Teams channel<br/>Business Owner notification"]
    governanceFlow["Power Automate Teams Workflow<br/>AI Governance webhook"]
    governance["Teams channel<br/>AI Governance Operations notification"]
    businessFlow --> business
    governanceFlow --> governance
  end

  agent -->|TicketTriaged custom events| appi
  identity -.->|Publishes with Entra auth| appi
  law -->|KQL AppEvents query| runner
  evaluator -->|review_required| businessFlow
  evaluator -->|cannot_evaluate| governanceFlow

  style azure fill:#172033,stroke:#60A5FA,color:#FFFFFF
  style foundry fill:#152A24,stroke:#34D399,color:#FFFFFF
  style control fill:#211B38,stroke:#A855F7,color:#FFFFFF
  style external fill:#302516,stroke:#F59E0B,color:#FFFFFF
  classDef azureNode fill:#3B82F6,stroke:#00D4FF,color:#FFFFFF
  classDef foundryNode fill:#16856A,stroke:#34D399,color:#FFFFFF
  classDef controlNode fill:#6E56CF,stroke:#A855F7,color:#FFFFFF
  classDef externalNode fill:#F59E0B,stroke:#F59E0B,color:#0D1117
  class appi,law,rbac azureNode
  class project,agent,identity foundryNode
  class bicep,runner,evaluator,contract controlNode
  class businessFlow,business,governanceFlow,governance externalNode
```

The control-owned Azure resources are the Log Analytics workspace,
Application Insights component, and its scoped publisher role assignment.
The Foundry project and hosted agent are the measured workload, not the
decision maker. The local evaluator owns the deterministic decision and its
evidence record. The two Teams Workflows are external notification
dependencies, not a second policy engine. The Business Owner receives a
proven value-review signal; AI Governance Operations receives a measurement
failure that requires control remediation.

| Resource or component | Type | Role in VAL-001 | Ownership |
|---|---|---|---|
| `log-val001-*` | `Microsoft.OperationalInsights/workspaces` | Stores `AppEvents` and answers the two-period KQL query | Control-owned Azure resource |
| `appi-val001-*` | `Microsoft.Insights/components` | Receives minimized `TicketTriaged` telemetry from the hosted agent | Control-owned Azure resource |
| `metrics-publisher` | `Microsoft.Authorization/roleAssignments` | Grants the publishing identity permission scoped to Application Insights | Control-owned Azure resource |
| `helpdesk-tier1-triage` | Foundry hosted `azure.ai.agent` | Performs synthetic Tier-1 triage whose verified outcomes are measured | Foundry workload |
| `evaluator.py` and `demo.py` | Local Python components | Apply the deterministic threshold, write evidence, and invoke notification | Control implementation |
| `governance.yaml` | FwF governance contract fixture | Supplies the read-only target and Business Owner from VAL-PRE-001 | Existing contract source |
| Business Owner Teams Workflow | Power Automate flow with HTTP trigger | Delivers `review_required` to the Business Owner | External Microsoft 365 dependency |
| AI Governance Teams Workflow | Power Automate flow with HTTP trigger | Delivers `cannot_evaluate` to AI Governance Operations | External Microsoft 365 dependency |

### Notification routing

The notification recipient depends on what the decision means:

* `review_required` is sent to the declared Business Owner through
  `VAL001_TEAMS_WEBHOOK_URL`. This means the measured KPI is below the
  threshold and a value review is needed.
* `cannot_evaluate` is sent to **AI Governance Operations**, also called the
  **Control Operator**, through `VAL001_GOVERNANCE_TEAMS_WEBHOOK_URL`. This
  means the measurement path or its evidence is unavailable, invalid, or
  incomplete. It must not be presented as evidence of business
  underperformance.

AI Governance Operations is the best accountable role for the second route
because it owns control execution, telemetry availability, evidence quality,
and remediation of monitoring failures. The Business Owner can be added as a
secondary escalation after the governance team confirms that the measurement
failure affects a business review, but is not the primary recipient.

### Positive performance reporting

The demo records healthy measurements as `no_review_required`, but does not
send a notification for every healthy run. A production implementation could
publish a positive performance summary once per month to the Business Owner,
AI Governance Operations, or both. Developers could build that reporting view
in Power BI from the retained Log Analytics data and control evidence.

That reporting cadence, monthly aggregation, Power BI workspace, and dashboard
design are intentionally outside this demo. VAL-001 focuses on the
deterministic underperformance decision and on fail-closed handling when the
measurement path is unavailable.

## Implementation

### Components

| Component | Responsibility |
|---|---|
| [agent.py](agent.py) and [workload.py](workload.py) | Execute synthetic ticket work and independently read back the result |
| [main.py](main.py) | Host the Foundry agent and export minimized events with Entra authentication |
| [evaluator.py](evaluator.py) | Validate the contract and telemetry, then apply the exact threshold |
| [demo.py](demo.py) | Run scenarios, query telemetry, write evidence, and request notifications |
| [infra/main.bicep](infra/main.bicep) | Create the control-owned Application Insights and Log Analytics resources |
| [infra/cleanup.py](infra/cleanup.py) | Verify ownership before deleting control-owned Azure resources |

### Implementation path

Complete these steps in order. Replace every `<placeholder>` with a value from
your environment. The control remains `Planned` until this path is replayed
from a clean checkout and both notification routes are live-validated.

#### 1. Install the dependencies and sign in

From the repository root, run:

```zsh
cd controls/value_adoption_and_finops/VAL-001_kpi_underperformance
../../../.venv/bin/python -m pip install -r requirements.txt -r ../VAL-PRE-001_value_hypothesis_missing/requirements.txt
az login
azd auth login
```

Do not continue until both sign-in commands succeed and Python reports no
installation error.

#### 2. Create and configure the local azd environment

Run these commands from the control directory:

```zsh
azd env new val-001-kpi-underperformance-dev
azd env set AZURE_SUBSCRIPTION_ID "<subscription-id>"
azd env set AZURE_TENANT_ID "<tenant-id>"
azd env set AZURE_RESOURCE_GROUP "<existing-resource-group>"
azd env set AZURE_LOCATION "<azure-location>"
azd env set AZURE_AI_PROJECT_ID "<foundry-project-resource-id>"
azd env set FOUNDRY_PROJECT_ENDPOINT "<foundry-project-endpoint>"
azd env set AZURE_AI_PROJECT_ENDPOINT "<foundry-project-endpoint>"
azd env set AZURE_AI_MODEL_DEPLOYMENT_NAME "<model-deployment-name>"
```

If the environment already exists, select it with `azd env select` instead of
creating it again. Keep the generated `.azure/` directory local and ignored.
The [deployment configuration](docs/IMPLEMENTATION.md#deployment-configuration)
defines each value.

#### 3. Deploy the monitoring resources

Create the Log Analytics workspace and Application Insights component:

```zsh
az deployment group create \
  --subscription "<subscription-id>" \
  --resource-group "<existing-resource-group>" \
  --name val001-monitor \
  --template-file infra/main.bicep \
  --parameters location="<azure-location>" \
  --query properties.provisioningState \
  --output tsv
```

Expect `Succeeded`. Then read the deployment outputs and store them without
printing the connection string:

```zsh
APPLICATION_INSIGHTS_ID=$(az deployment group show --resource-group "<existing-resource-group>" --name val001-monitor --query properties.outputs.applicationInsightsId.value --output tsv)
VAL001_WORKSPACE_ID=$(az deployment group show --resource-group "<existing-resource-group>" --name val001-monitor --query properties.outputs.workspaceId.value --output tsv)
azd env set VAL001_WORKSPACE_ID "$VAL001_WORKSPACE_ID"
set +x
APPLICATIONINSIGHTS_CONNECTION_STRING=$(az resource show --ids "$APPLICATION_INSIGHTS_ID" --api-version 2020-02-02 --query properties.ConnectionString --output tsv)
azd env set APPLICATIONINSIGHTS_CONNECTION_STRING "$APPLICATIONINSIGHTS_CONNECTION_STRING"
unset APPLICATIONINSIGHTS_CONNECTION_STRING
```

Do not continue until the deployment succeeded and both shell variables are
non-empty.

#### 4. Deploy the hosted agent and grant its publishing role

Deploy the agent, retrieve its instance identity, and apply the role assignment:

```zsh
azd deploy helpdesk-tier1-triage --no-prompt
AGENT_PRINCIPAL_ID=$(azd ai agent show helpdesk-tier1-triage --output json | jq -r '.instance_identity.principal_id')
test -n "$AGENT_PRINCIPAL_ID" && test "$AGENT_PRINCIPAL_ID" != "null"
az deployment group create \
  --subscription "<subscription-id>" \
  --resource-group "<existing-resource-group>" \
  --name val001-monitor-publisher \
  --template-file infra/main.bicep \
  --parameters location="<azure-location>" publisherPrincipalId="$AGENT_PRINCIPAL_ID" \
  --query properties.provisioningState \
  --output tsv
```

Expect `Succeeded`. In Application Insights, open **Access control (IAM)** and
confirm that the agent instance has **Monitoring Metrics Publisher** at this
resource's scope. Allow time for RBAC propagation before running the demo.

#### 5. Create and store both Teams notification routes

Follow the [Teams delivery walkthrough](docs/TEAMS-DELIVERY.md#find-and-configure-the-webhook-url)
twice:

1. Create a tenant-authenticated workflow for `review_required` and route it
   to the Business Owner.
2. Create a separate tenant-authenticated workflow for `cannot_evaluate` and
   route it to AI Governance Operations.

Paste each generated URL into hidden input and store it in azd:

```zsh
set +x
read -rs 'VAL001_TEAMS_WEBHOOK_URL?Paste the Business Owner URL (hidden): '
printf '\n'
azd env set VAL001_TEAMS_WEBHOOK_URL "$VAL001_TEAMS_WEBHOOK_URL"
unset VAL001_TEAMS_WEBHOOK_URL
read -rs 'VAL001_GOVERNANCE_TEAMS_WEBHOOK_URL?Paste the AI Governance URL (hidden): '
printf '\n'
azd env set VAL001_GOVERNANCE_TEAMS_WEBHOOK_URL "$VAL001_GOVERNANCE_TEAMS_WEBHOOK_URL"
unset VAL001_GOVERNANCE_TEAMS_WEBHOOK_URL
printf '' | pbcopy
```

Do not print, commit, screenshot, or paste either URL into chat.

#### 6. Run both governance scenarios

Run both command blocks in [Run](#run). Confirm that the underperforming run
returns `review_required` and the missing-contract run returns
`cannot_evaluate`. For each run, open
`.azure/val001/runs/<run-id>/evidence.json` and verify the decision, reason,
target, threshold, and two period rates.

#### 7. Verify Teams delivery and record the receipt

Open each Power Automate run. Match its input correlation to the VAL-001 run,
then confirm that the Teams posting action returned `201`. A webhook `202`
response alone is not delivery evidence. Record only the inspected receipt:

```zsh
../../../.venv/bin/python demo.py record-delivery \
  --run-id "<run-id>" \
  --flow-run-id "<checked-flow-run-id>" \
  --message-id "<checked-teams-message-id>"
```

Open the corresponding `evidence.json` again and confirm
`notification.status` is `delivered` and `delivery_verified` is `true`.

#### 8. Run the tests and clean up

Run the [validation command](#validation). If it passes, run the inspection
command and then the confirmed deletion command in [Cleanup](#cleanup). Verify
that the control-owned agent and Monitor resources are gone while the shared
Foundry project and resource group still exist.

The focused Azure Portal checks and screenshots are in
[Inspect in Azure](docs/IMPLEMENTATION.md#inspect-in-azure).

### Demo scope

The demo proves a synthetic workload-to-measurement-to-review-request chain,
not production ticket resolution, statistical confidence from five tickets,
target adequacy, or completion of a human review. Periods are compressed and
explicitly tagged. The private test recipient stands in for the fictional owner.
There are no production actions, agent shutdowns, schedulers, portfolio services,
or new VAL-001 declaration schemas. The shared deployment gate remains an
upstream pre-live boundary and is not part of this runtime flow. Inline ACS
tool governance remains further exploration. The added measurement-failure
route has not been live validated.

### Best-practice requirements

- Keep policy enforcement outside model reasoning when a deterministic control
  is possible.
- Use least-privilege identity and secretless authentication where supported.
- Minimize retained data and exclude sensitive values from logs and alerts.
- Fail closed when a mandatory control cannot complete safely.
- Pin or document API/model versions and review them during repository updates.

## Demo

### Prerequisites

Complete steps 1 through 5 of the [implementation path](#implementation-path)
before running the demo. Confirm that both webhook values are configured
without printing them. Never paste an endpoint into chat, source control, a
screenshot, or an ordinary shell command line.

### Run

Run the underperformance scenario against the hosted Foundry agent. The command prints a `Run:` identifier.

```zsh
cd controls/value_adoption_and_finops/VAL-001_kpi_underperformance
RUN_OUTPUT=$(../../../.venv/bin/python demo.py run --scenario underperforming)
printf '%s\n' "$RUN_OUTPUT"
RUN_ID=$(printf '%s\n' "$RUN_OUTPUT" | sed -n 's/^Run: //p')
../../../.venv/bin/python demo.py evaluate --run-id "$RUN_ID"
../../../.venv/bin/python demo.py notify --run-id "$RUN_ID"
```

Expect `review_required`. The Business Owner Teams Workflow receives the red
attention card after the evaluator writes the evidence record. Configure the
endpoint in the ignored local `azd` environment as
`VAL001_TEAMS_WEBHOOK_URL`.

To reproduce the fail-closed `cannot_evaluate` card, run a separate healthy
workload and evaluate it against a deliberately missing contract path:

```zsh
RUN_OUTPUT=$(../../../.venv/bin/python demo.py run --scenario healthy)
printf '%s\n' "$RUN_OUTPUT"
RUN_ID=$(printf '%s\n' "$RUN_OUTPUT" | sed -n 's/^Run: //p')
../../../.venv/bin/python demo.py evaluate --run-id "$RUN_ID" --contract /tmp/val001-missing-governance.yaml
../../../.venv/bin/python demo.py notify --run-id "$RUN_ID"
```

Expect `cannot_evaluate`. Configure the separate governance endpoint as
`VAL001_GOVERNANCE_TEAMS_WEBHOOK_URL`. Never put a real webhook URL in this
README, shell history, or chat.

### Capture the Teams card

Use the Teams desktop app or the headed browser started by Playwright. Do not
use the VS Code Simple Browser, because it cannot render the current Teams web
client in this environment. Open the Workflows chat, locate the new VAL-001
card, and use macOS `Cmd+Shift+4` to select only the card.

Exclude or mask personal names, email addresses, tenant details, webhook URLs,
and unnecessary service identifiers before adding a capture to the repository.

| Decision | Visual state | Captured in the repository |
|---|---|---|
| `review_required` | Red attention dot and Business Owner review text | Left card in [`media/teams-cards-both-decisions.png`](media/teams-cards-both-decisions.png) |
| `cannot_evaluate` | Amber warning icon and measurement remediation text | Right card in the same capture |
| `no_review_required` | Green positive-performance card, optional future report | Not captured by the core demo |

Both governance outcomes share one capture on purpose: a single Workflows chat
shows the routing difference more clearly than two separate crops, and it keeps
one image in the repository instead of three.

The screenshot proves Teams delivery and visual rendering only. The JSON
evidence record remains the authoritative proof of the control decision.

### Expected scenarios

| Scenario | Expected result |
|---|---|
| Both periods strictly below 28% | `review_required`, separately track notification status. |
| Either period at or above 28% | `no_review_required`, evidence recorded; no notification in this demo. |
| Missing, invalid, incomplete, or ambiguous inputs | `cannot_evaluate`, never a healthy result, and notify AI Governance Operations. |

### Captured validation evidence

The [integrated live test](docs/IMPLEMENTATION.md#live-validation) used real
queried outcomes: both periods at `1/5 (20%)` produced `review_required`,
followed by a matching Teams `201` posting receipt. A separate run at
`2/5 (40%)` in both periods produced `no_review_required` without notification.
Interrupted runs produced `cannot_evaluate`.

![Log Analytics results for the underperforming KPI run](media/azure-kpi-query-review-required.png)

The Log Analytics results show two consecutive periods at 20%, below the 28%
threshold, and the resulting `review_required` decision.

<p align="center">
  <img src="media/teams-cards-both-decisions.png" alt="Teams notifications for KPI review required and Measurement unavailable" width="700">
</p>

The Teams capture shows two separate governance paths. The red card is the
`review_required` notification for the confirmed KPI underperformance shown in
the Log Analytics results. The amber **Measurement unavailable** card shows the
separate `cannot_evaluate` path and asks AI Governance Operations to restore the
measurement path. The [Teams walkthrough](docs/TEAMS-DELIVERY.md) provides the
delivery and workflow details.

The evaluator's JSON evidence record remains authoritative for the control
decision. The screenshots demonstrate the queried measurements and the
resulting human-facing notifications.

## Evidence and observability

Each run has one authoritative `.azure/val001/runs/<run-id>/evidence.json`
binding versions, correlation, contract hash/reference, owner, counts, rates,
target, threshold, decision, reason, and notification verification/history.
Raw prompts, model responses, tokens, and webhook URLs are excluded. For a
developer-focused investigation example, see the [Observability Agent
walkthrough](docs/OBSERVABILITY-AGENT.md). It shows how to explore the
telemetry behind a `cannot_evaluate` result without making the exploratory
agent authoritative for the control decision.

## Security and privacy

Only isolated synthetic state is modified. The agent instance receives
Monitoring Metrics Publisher on its own Application Insights resource, with
local auth disabled. Operators use Entra auth for queries and Teams requests.
Local evidence assumes trusted filesystem access and is not tamper-proof.

## Validation

From the repository root, run:

```bash
.venv/bin/python -m pytest controls/value_adoption_and_finops/VAL-001_kpi_underperformance/tests -q
```

Tests cover exact boundaries, mixed periods, incomplete/sampled telemetry,
duplicates, contract validity, verified execution, notification failures and
retries, minimization, and cleanup ownership. See the
[implementation guide](docs/IMPLEMENTATION.md) for live results and release gates.

The [prerelease review](docs/REVIEW.md) records open findings on complete cleanup,
community onboarding, notification validation, and readability. It is not a final
release approval.

## Cleanup

Synthetic in-memory ticket state is destroyed when its context exits, including
on failure. The retained Teams test flow and message have separate cleanup
steps in the [delivery walkthrough](docs/TEAMS-DELIVERY.md#cleanup).
Azure cleanup was executed and independently checked: nine session
filesystems, the agent, two Monitor resources, and the linked automatic alert
were deleted; the shared group remained. From the control directory:

```bash
../../../.venv/bin/python infra/cleanup.py --subscription <subscription-id> --resource-group <resource-group>
../../../.venv/bin/python infra/cleanup.py --subscription <subscription-id> --resource-group <resource-group> --confirm
```

The first command inspects; the second deletes only verified targets. It does
not delete platform conversation history, Teams messages/flow, or retained
local audit evidence. Full data cleanup remains incomplete. Do not delete the
shared Foundry project or resource group to work around that limitation.

## References

- [Create and configure workspace-based Application Insights resources](https://learn.microsoft.com/en-us/azure/azure-monitor/app/create-workspace-resource)
  — the ingestion target for the `TicketTriaged` events this control measures.
- [Overview of Log Analytics in Azure Monitor](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/log-analytics-overview)
  — the workspace and KQL surface behind the two-period query.
- [Azure built-in roles for Monitor](https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles/monitor)
  — the `Monitoring Metrics Publisher` assignment scoped to the control's own
  Application Insights resource.
- [Observability Agent in Azure Monitor](https://learn.microsoft.com/en-us/azure/azure-monitor/aiops/observability-agent-overview)
  — the exploratory agent used in the [observability walkthrough](docs/OBSERVABILITY-AGENT.md),
  which is never authoritative for the control decision.
- [Agent identity concepts in Microsoft Foundry](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/agent-identity)
  and [Manage hosted agents](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/manage-hosted-agent)
  — the hosted `helpdesk-tier1-triage` workload and the instance identity that
  cleanup verifies before deletion.
- [Configure keyless authentication with Microsoft Entra ID](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/configure-entra-id)
  — the secretless authentication path used instead of connection strings.
- Teams Workflows webhook and Adaptive Card references are listed in the
  [delivery walkthrough](docs/TEAMS-DELIVERY.md#references).
- Source catalog: [Governance Signals Repo.pdf](../../../docs/Governance%20Signals%20Repo.pdf)

---

<p align="center">
    <img src="../../../media/themepack/fwf-footer.png" alt="Forged with Foundry" width="814">
</p>
