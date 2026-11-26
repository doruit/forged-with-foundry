# CHG-002 — control assessment

Completed before any exercise artifact, implementation code or
infrastructure was created. Reviewed 26 November 2026, after Microsoft
Ignite 2026.

## Candidate

- **Control ID:** CHG-002
- **Name:** Model version changed without regression test
- **Lifecycle phase:** Live (change to a production agent)
- **Accountable role:** AI Engineering Lead

## Governance problem

- **Risk:** A production agent is moved to a different model or model
  version "because it is newer" without testing it against the agent's
  current behaviour. Answers change silently, sometimes for the worse. The
  same happens without any human decision when a model deployment is set to
  upgrade automatically: Azure upgrades a deployment set to
  `OnceNewDefaultVersionAvailable` within two weeks of a new default version
  ([Working with models](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/working-with-models)).
  This repository's own shared `gpt-5` deployment in `infra/main.bicep` uses
  that setting.
- **Control objective:** No model change reaches production unless a
  completed regression evaluation of exactly that candidate, on a held-out
  dataset, shows it is not worse than the approved baseline; and no model
  deployment can change version without that decision.
- **Authoritative signal:** Foundry Evaluations run results (GA) for the
  baseline and the candidate agent version on the same dataset.
- **Required decision:** May this candidate model (asset ID including
  version) be released for this agent?
- **Required governance action:** Block the release in CI, and deny the
  model deployment at Azure Resource Manager when the model version is not
  approved or is set to upgrade automatically.
- **Required evidence:** Evaluation run IDs, agent versions, model asset IDs,
  dataset hash, pass rate per required evaluator for baseline and candidate,
  completeness counts, decision and reason, contract hash, timestamp,
  correlation ID, accountable role.

## Enforcement classification

- **Deterministic policy:** Yes. The release decision compares recorded pass
  rates against contract thresholds; the candidate gate re-checks the
  decision and binds it to the deployment candidate.
- **Model-assisted evaluation:** Yes, supplied by Foundry's built-in
  evaluators (an LLM judge). Their scores are inputs; they never decide.
- **Human approval:** Not required for blocking. Changing the approved
  baseline is a reviewed pull request (the evaluation evidence and the
  candidate change together).
- **Configuration assessment:** Yes. The model deployment's model version
  and `versionUpgradeOption` are evaluated by Azure Policy.
- **Monitoring/detection:** Post-release drift is QLT-006's responsibility.
- **Required fail-closed behavior:** Missing, incomplete, errored or
  mismatched evaluation evidence, a dataset hash mismatch, an unknown model,
  or an invalid contract entry blocks the release. Azure Policy denies any
  model version not on the allow-list.
- **Model/Foundry role:** `Monitored workload`. A real Foundry prompt agent
  is evaluated; the authoritative decision evaluates accumulated evaluation
  results, not an inline agent action. ACS is not the enforcement surface:
  a release decision happens before any agent run, and no ACS intervention
  point sees a model *deployment* change.

## Existing capability review

| Capability | Applicable? | What it already provides | Role in the core demo or reason not used |
|---|---:|---|---|
| Microsoft Agent Governance Toolkit | No | Runtime policy and approval | No runtime action is governed; the decision is a release gate. |
| Agent Control Specification | No (core) | `agent_startup` could refuse runs of an unapproved model | Further exploration: a third enforcement point that duplicates the Policy denial for the demo's scope. |
| Microsoft Foundry | Yes | Prompt agents with immutable versions; **Foundry Evaluations** with built-in evaluators (GA) | Core: baseline and candidate are two agent versions; Evaluations produce the authoritative signal. |
| Foundry agent optimizer | Yes | **Model selection** across candidate deployments and promotion of a winner to a new agent version (GA) | Core scenario source: shows how a model change is created. Its own score is candidate evidence only, because it scores against the dataset it optimises on and its eval model gives binary scores ([overview](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/agent-optimizer-overview)). |
| GitHub Action `microsoft/ai-agent-evals` | Partly | Baseline-versus-candidate comparison with confidence intervals and a significance test, in CI | Further exploration: preview (`v3-beta`), results only in the job summary, so it cannot be the machine-checked evidence ([how-to](https://learn.microsoft.com/en-us/azure/foundry/how-to/evaluation-github-action)). |
| `azd ai eval` (`azure.ai.evaluations` extension) | Partly | Registered evaluation and `--fail-on pass-rate` exit code | Not used: duplicates the SDK run and adds an extension dependency; documented as an alternative runner. |
| Foundry Control Plane | No | Fleet overview | Not needed for one agent. |
| Azure API Management AI Gateway | No | Traffic mediation | A model change is not a request-time decision. |
| Microsoft Purview | No | Data governance | Not applicable. |
| Microsoft Defender | No | Threat protection | Not applicable. |
| Microsoft Entra | Yes | Keyless sign-in; OIDC for the release job | Core for authentication only. |
| Azure AI Content Safety / Language | No | Content filters | Not this signal. |
| Azure Monitor / Application Insights / OTel | No | Telemetry | Not needed for an offline regression run. |
| **Azure Policy built-in "Foundry model deployments should only use approved models"** | Yes | `Deny` for deployments whose model asset ID is not allow-listed; a full asset ID pins one version; GA, v1.0.2 ([how-to](https://learn.microsoft.com/en-us/azure/foundry/how-to/model-deployment-policy)) | Core: the independent ARM enforcement route. |
| Azure Policy custom definition on `versionUpgradeOption` | Yes | Alias `Microsoft.CognitiveServices/accounts/deployments/versionUpgradeOption` exists | Core: denies automatic upgrades, the silent path around the gate. No built-in covers it. |

## Existing samples and implementations

| Repository, documentation, or sample | Overlap | What is still missing |
|---|---|---|
| [Run an evaluation in GitHub Action (preview)](https://learn.microsoft.com/en-us/azure/foundry/how-to/evaluation-github-action) | Evaluation in CI, `--fail-on pass-rate` | Binding a result to one model asset ID, blocking at ARM, and the silent auto-upgrade path |
| [Built-in policies for model deployment](https://learn.microsoft.com/en-us/azure/foundry/how-to/model-deployment-policy) | Allow-list of models | Why an asset ID is on the list: no link to evaluation evidence |
| VAL-PRE-002 (this repository) | Candidate gate plus independent Azure Policy route | A model-change signal and Foundry Evaluations evidence |
| QLT-001 (this repository) | Foundry Evaluations SDK usage | Release gating; QLT-001 monitors production |

## Repository overlap

- **Related controls:** QLT-006 (post-release regression, same agent and
  dataset), CHG-001 (prompt changes), CHG-003 (knowledge changes), CHG-004
  (guardrail changes), EVAL-PRE-001/002 (evaluation set exists and covers
  requirements), REL-PRE-001/002 (release evidence and go-live approval).
- **Reused components:** `scripts/deployment_gate.sh`, the shared contract
  validator and Conftest layer, the VAL-PRE-002 workflow shape.
- **Duplication risk:** Low. CHG-002 governs only the *model* part of a
  change; the scope boundary is recorded in the category `ARCHITECTURE.md`.

## Proposed contribution

- **Classification:** `COMPOSE`
- **Demo format:** `DEPLOYABLE_DEMO`
- **Deployment:** Required for the core learning outcome (real agent
  versions, real evaluation runs, real Policy denial).
- **Existing capabilities reused:** Foundry prompt agents and Evaluations,
  agent optimizer (scenario), Azure Policy built-in approved-models policy,
  shared contract gate.
- **How their role is visible:** the evaluation runs appear in the Foundry
  portal; the Policy denial is a captured `RequestDisallowedByPolicy`; the
  gate prints the decision bound to the candidate's asset ID.
- **Minimum custom implementation:** a deterministic regression policy, an
  evaluation runner over the SDK, a candidate binding check, one custom
  Policy definition, evidence writing.
- **Unique learning outcome:** a model change is only as safe as the
  evidence bound to *that exact model version*, enforced both in CI and at
  ARM; and "auto-upgrade" is a model change too.
- **Distinct learning beyond the official samples:** links the evaluation to
  the allow-list and closes the automatic-upgrade path.
- **Why a separate demo:** the pre-change gate is a distinct decision from
  post-release monitoring (QLT-006).
- **Why deployment is justified:** the Policy denial and real agent versions
  cannot be shown credibly in a guided exercise.

## Smallest useful design

- **Primary governance decision:** release or block a candidate model for one agent.
- **Authoritative human role:** AI Engineering Lead (approves the baseline change by merging).
- **Signal source:** Foundry Evaluations runs (baseline and candidate versions, same held-out dataset).
- **Decision surface:** CHG-002 regression policy; re-verified by the credential-free candidate gate.
- **Evidence source:** CHG-002 evidence file plus the release baseline record.
- **ACS intervention point:** none (see above).
- **Foundry/Azure services:** control-owned Foundry account and project, small model deployments, Azure Policy.
- **Governance action:** CI job fails before the release job; Azure Policy denies the deployment.
- **Healthy scenario:** candidate on an approved, evaluated model is not worse: release allowed, baseline record updated.
- **Policy-triggering scenarios:** model changed with no evaluation; evaluated candidate significantly worse; deployment set to auto-upgrade.
- **Unavailable/ambiguous scenarios:** evaluation errored or incomplete, dataset hash mismatch, invalid contract: blocked.

## Complexity budget

- **Custom components:** policy (decision logic absent from Foundry), runner
  (calls the GA SDK and records results), gate check (binding to the
  candidate), one custom Policy definition (no built-in for
  `versionUpgradeOption`).
- **Deliberately omitted:** UI, ACS runtime check, App Insights, a second
  evaluation runner.
- **Shadow evidence avoided:** the gate only accepts evidence carrying the
  Foundry run IDs; QLT-006 reads the same baseline record.
- **Metadata edge cases:** missing, empty, invalid and valid values for
  every contract threshold and the candidate asset ID are tested.

## Community fit

- **Learning level:** Intermediate
- **Estimated time:** 30-45 minutes (to be measured live)
- **Prerequisites:** Azure subscription with Foundry and Azure Policy permissions, Python 3.12
- **Intentional simplifications:** synthetic support agent with read-only
  tools; small held-out dataset; one control-owned account so the Policy
  assignment cannot affect other controls.
- **Further exploration:** `ai-agent-evals` significance report, ACS
  `agent_startup` model check, eligibility policy (deny preview models),
  model router governance.

## Scope boundary

- **Included:** model and model-version changes for one prompt agent.
- **Excluded:** prompt, knowledge and guardrail changes (CHG-001/003/004),
  model router per-request selection, retirement-forced upgrades.
- **Proves:** an unevaluated or worse model version is blocked in CI and
  denied at ARM; an automatic-upgrade setting is denied.
- **Does not prove:** that the dataset represents production, that the LLM
  judge is correct, that evidence was not forged before the CI check, or
  coverage of agents outside the Policy scope.
- **Correct and safe within this boundary:** yes, if both routes are used.

## Decision

- **Proceed.**
- **Rationale:** a distinct, GA-backed composition with a clear two-route
  enforcement story and a real-world silent-upgrade risk.
- **Review date:** 26 November 2026
- **Authoritative references:** [Microsoft Ignite 2026 Book of News](https://news.microsoft.com/events/ignite/2026/book-of-news/),
  [agent optimizer overview](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/agent-optimizer-overview),
  [model deployment policies](https://learn.microsoft.com/en-us/azure/foundry/how-to/model-deployment-policy),
  [model versions](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/model-versions),
  [working with models](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/working-with-models),
  [evaluation in GitHub Action](https://learn.microsoft.com/en-us/azure/foundry/how-to/evaluation-github-action).
