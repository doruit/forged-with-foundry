---
title: VAL-PRE-002 deployment routes
description: Candidate CI gating, independent Azure Policy denial, OIDC release and scoped cleanup.
---

## Choose a route

| Route | Workflow input | What it establishes |
|---|---|---|
| CI-only | `ci-only` (default) | The checked-out candidate has schema-valid evidence and the `val-pre-002-only` profile's required control coverage. No Azure credential or call. |
| Azure Policy-only | `policy-only` | A deliberately incomplete tagged ARM request is denied by the VAL-PRE-002 assignment, independently of CI. This is an experiment, not a release. |
| Combined | `combined` | The candidate gate must succeed before OIDC login and deployment. The request's status comes from that gate, not a workflow input or a passing negative fixture test. |

The [workflow](../../../../.github/workflows/val-pre-002-baseline-gate-demo.yml)
checks [candidate/](../candidate/), not `fixtures/complete-workload`.
Both jobs check out the event's same commit. The candidate is the synthetic
`helpdesk-tier1-triage` workload represented by a disabled, receiver-free
Action Group. Its manifest pointer identifies the existing demo template;
no real agent is deployed or simulated.

The fixed deployment profile remains outside the candidate root and requires
`helpdesk-tier1-triage` to declare `VAL-PRE-002`. The shared validator checks
evidence; Conftest decides required-control coverage. Neither is reimplemented.

`release.needs: candidate-gate` uses GitHub's default successful-dependency
requirement. There is no `always()` or `continue-on-error` release bypass.
Negative fixture tests run separately and cannot authorize the release.

## CI-only walkthrough

From the repository root, use a Python environment with the
[schema dependencies](../../../../schemas/governance-contract/requirements.txt)
and Conftest 0.70.0 (see the [installation and checksum guidance](../../../../policy/governance-contract/README.md)).
Put that Python environment on `PATH`, because the shared gate calls `python3`.

```bash
export PATH="$PWD/.venv/bin:$PATH"
CONTROL_DIR=controls/value_adoption_and_finops/VAL-PRE-002_kpi_baseline_missing
bash scripts/deployment_gate.sh \
  --manifest examples/deployment-manifests/val-pre-002-only.yaml \
  --profile val-pre-002-only --root "${CONTROL_DIR}/candidate" \
  --evidence-out /tmp/val-pre-002-gate-evidence.json &&
  printf 'DEPLOYMENT STEP REACHED\n'
```

The final print is a harmless local stand-in for a deployment command.
It is executed only on gate exit 0. In the workflow this relationship is a
job dependency on the actual Azure release.

To exercise failure without editing your candidate, repeat with
`--root "${CONTROL_DIR}/fixtures/incomplete-workload"`. The gate must exit
nonzero and never print `DEPLOYMENT STEP REACHED`. Do not wrap a candidate
denial in an "expected failure" handler in a release pipeline.

| Candidate change | Expected outcome |
|---|---|
| Measured baseline with numeric value and calendar-valid date | Allow |
| `baseline: {status: net_new}` | Allow; no measured value/date required |
| Missing or empty evidence; nonnumeric value; invalid date | Deny |
| Missing `VAL-PRE-002`, even with another schema-valid control | Deny |
| Missing expected agent folder or missing contract file | Deny |
| Validator crash, Conftest failure, missing dependency | Stop; never treat an execution error as a successful negative test |

The executable [tests](../tests/test_release_demo.py) run the actual YAML
candidate step, then a deployment marker, and assert that rejected candidates
produce neither the marker nor the output tag. These tests are local process
and workflow-wiring evidence, not a live GitHub scheduler trace.

## Azure prerequisites and OIDC

No automatic infrastructure deployment or identity mutation occurs in the
workflow. Obtain approval before configuring these external prerequisites.

1. Choose an existing demo resource group. The shared Foundry deployment is
   not required for this control. Follow the [README deployment steps](../README.md#deploy)
   to install the VAL-PRE-002 policy definition and group assignment. Allow
   time for propagation. Inspect its `control-id`, `goLiveRequested` selector
   conditions and `kpiBaselineStatus` rule; do not remove other policies.
2. Reuse a suitably scoped demo managed identity, or create a control-owned
   user-assigned managed identity in **Azure Portal > Managed Identities**.
   A resource-group-scoped **Monitoring Contributor** assignment is the
   existing VAL-PRE-001 demo pattern for Action Groups and ARM deployments.
   Do not grant subscription Contributor or policy-write permission to the
   release identity. Record exactly which identity and role assignment you
   created; do not remove pre-existing ones during cleanup.
3. In **GitHub Settings > Environments**, create `val-pre-002-demo`. Add the
   environment variables `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`,
   `AZURE_SUBSCRIPTION_ID`, and `AZURE_RESOURCE_GROUP`. They identify the
   target and identity; no client secret is used. Keep real values out of
   tracked files and screenshots.
4. Add a separate federated credential on the identity, with issuer
   `https://token.actions.githubusercontent.com`, audience
   `api://AzureADTokenExchange` and the exact subject for this repository
   and environment. Do not replace VAL-PRE-001's existing credential.
   GitHub can use legacy or immutable-ID subject formats; use its actual
   configured subject, never assume a format. See the
   [VAL-PRE-001 subject walkthrough](../../VAL-PRE-001_value_hypothesis_missing/docs/OIDC-DEMO.md#subject-format).
5. Protect the environment's permitted branches and reviewers as appropriate
   for your repository. Protect edits to workflow, schema, coverage profile,
   policy and deployment template too. An environment name alone is not a
   protection rule. Do not give pull-request jobs Azure tokens.

The existing [VAL-PRE-001 OIDC walkthrough and captured run](../../VAL-PRE-001_value_hypothesis_missing/docs/OIDC-DEMO.md)
show a live-tested example of this identity-binding and Action Group pattern.
Those screenshots predate its Conftest addition and are not live evidence for
VAL-PRE-002, its new cleanup wrapper or current job dependencies.

## Run the Azure routes

After the workflow is available on the repository's default branch, choose
**Actions > VAL-PRE-002: candidate gate and independent Azure Policy demo >
Run workflow**. Select `combined` for the normal gated release, or
`policy-only` for the isolated admission experiment. Do not upload or push
these changes without the repository owner's approval.

For `combined`, expect `candidate-gate` to pass before `release` starts.
The status tag must be `needs.candidate-gate.outputs.baseline_status`.
For a real failure demonstration in an authorized test repository, remove
the candidate's baseline value, then run `combined`: `candidate-gate` must
fail and `release` must be skipped, with no OIDC login or Azure request.
Restore the candidate afterward.

For `policy-only`, `candidate-gate` and `release` are skipped. The experiment
sends an incomplete status intentionally. It succeeds only when Azure
returns `RequestDisallowedByPolicy` identifying the VAL-PRE-002 assignment.
Authentication failures, unrelated policy denials and unexpected permission
to deploy all fail the experiment. A successful release alone does not prove
the policy was installed; use the independent denial test for that proof.

The [existing validate-only demo](../demo.sh) remains a lower-impact Azure
option: it derives tags from both fixtures and calls `az deployment group
validate`, creating no Action Group. This does not exercise OIDC or CI gating.

## Guarantees and limits

CI proves structural completeness and required-control coverage at the
checked revision. It cannot verify the recorded number's accuracy.
Azure Policy reads only tags, never the governance contract. Requests without
`control-id=VAL-PRE-002` or `goLiveRequested=true` fall outside its selector;
a forged `kpiBaselineStatus=complete` can pass. The combined route does not
turn caller-supplied tags into an authenticated governance attestation.
Neither route universally governs agent publishing or other deployment paths.

The uploaded shared gate artifact contains hashes, evaluated controls,
profile, source revision and outcome, not raw baseline evidence. When a
dependency or evaluator crashes before evidence is produced, absence of the
artifact is not a pass: the failed job and missing tag block release.

## Cleanup

`azure-demo.sh` uses `valpre002-<route>-<run-id>-<attempt>` names. It refuses
to overwrite an existing resource or deployment record. On success and
failure it checks resource name, type, `control-id`, `purpose` and run-id,
deletes only the matching Action Group and run-specific deployment record,
and verifies both are absent. Deployment-record cleanup checks its exact
demo name and run-id parameters. It never removes a resource group, policy,
identity or other control's resource. Cleanup failure fails the job.

After interruption, authenticate to the same subscription, set
`AZURE_RESOURCE_GROUP` and `DEMO_RUN_ID` to that run's numeric `run-id-attempt`,
and invoke the corresponding recovery command:

```bash
bash "${CONTROL_DIR}/azure-demo.sh" cleanup-release
# For the independent experiment instead:
bash "${CONTROL_DIR}/azure-demo.sh" cleanup-policy-only
```

Delete a newly added federated credential in **Managed Identities > Federated
credentials** only by its recorded demo-specific name. Remove the GitHub
demo environment and its variables if no longer needed. Delete an identity
or role assignment only if created exclusively for this demo; never run
VAL-PRE-001 identity teardown against a reused identity. Policy teardown is
the separate control-owned [infra/cleanup.sh](../infra/cleanup.sh).

Remove `/tmp/val-pre-002-gate-evidence.json` after the local walkthrough when
no longer needed. GitHub evidence artifacts follow repository retention.

## Validation record

On 2026-09-21 the exact candidate workflow step was executed locally with real
Conftest and printed:

```text
1/3 Building the deployment plan (profile: val-pre-002-only)...
2/3 Evaluating the Conftest policy (policy/governance-contract)...
3/3 Recording evidence...
ALLOWED: every expected agent has a valid contract with every required control complete.
baseline_status=complete
```

The new workflow/cleanup tests plus existing baseline boundary tests then
reported `31 passed in 10.51s`. These include actual CI-step failure
propagation, `net_new`, and simulated Azure denial and cleanup errors.

The negative CI-only walkthrough was also run against `incomplete-workload`.
Selected actual output:

```text
1/3 Building the deployment plan (profile: val-pre-002-only)...
2/3 Evaluating the Conftest policy (policy/governance-contract)...
3/3 Recording evidence...
DENIED: one or more required checks failed. See the evidence artifact for detail.
```

The subsequent `DEPLOYMENT STEP REACHED` command did not run. The shared
evidence artifact recorded denial, not authorization.

Repository verification on 2026-09-21 reported `269 passed, 56 warnings in
32.24s`, `12 tests, 12 passed` for Rego and `No broken requirements found`
from the dependency check. The control validator and repository Bicep
compilation passed. Roadmap regeneration produced no content change.
The full documentation link check found one pre-existing HTTP 404 in the
VAL-PRE-001 README's Entra reference; the new walkthrough links all passed.

Current VAL-PRE-002 GitHub/OIDC live validation has not been executed. The
repository owner declined temporary external configuration and publication
for this change. The historical VAL-PRE-002 validate-only transcript remains
in the [README](../README.md#demo-walkthrough); VAL-PRE-001 supplies the
linked live OIDC pattern evidence, not a substitute validation claim.
The editor currently flags `val-pre-002-demo` and its four Azure variables
because that external GitHub environment has not been configured. Do not
silence those diagnostics by implying the prerequisites already exist.

## References

- [Azure Policy deny semantics](https://learn.microsoft.com/en-us/azure/governance/policy/concepts/effect-deny)
- [Azure Login with OpenID Connect](https://learn.microsoft.com/en-us/azure/developer/github/connect-from-azure-openid-connect)
- [GitHub job dependency semantics](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-jobs)
- [Shared governance contract](../../../../docs/governance-contract.md)