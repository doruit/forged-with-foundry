# VAL-PRE-001 — implementation detail

Deep-dive companion to [`../README.md`](../README.md). Read the README first;
this file exists so the README can stay bite-sized while still linking to
every implementation decision.

## Components

| Component | Responsibility | Location |
|---|---|---|
| Governance contract fixtures | Authoritative, structured value hypothesis for the helpdesk agent example | [../fixtures/complete-workload/.fwf/agents/helpdesk-tier1-triage/governance.yaml](../fixtures/complete-workload/.fwf/agents/helpdesk-tier1-triage/governance.yaml), [../fixtures/incomplete-workload/.fwf/agents/helpdesk-tier1-triage/governance.yaml](../fixtures/incomplete-workload/.fwf/agents/helpdesk-tier1-triage/governance.yaml) |
| Shared schema validator | Reduces the governance contract to the two tags Azure Policy checks | [../../../../scripts/validate_governance_contract.py](../../../../scripts/validate_governance_contract.py) |
| Control schema | Declares VAL-PRE-001's exact evidence shape | [../../../../schemas/governance-contract/v1alpha1/controls/VAL-PRE-001.schema.json](../../../../schemas/governance-contract/v1alpha1/controls/VAL-PRE-001.schema.json) |
| Boundary-case + consistency tests | Equivalent coverage to the pre-migration hand-rolled validator tests, now schema-driven | [../../../../tests/test_val_pre_001_governance_contract.py](../../../../tests/test_val_pre_001_governance_contract.py), [../../../../tests/test_governance_contract_consistency.py](../../../../tests/test_governance_contract_consistency.py) |
| Azure Policy definition | Expresses the authoritative `deny` rule on the two reduced tags | [../infra/policy-definition.bicep](../infra/policy-definition.bicep) |
| Policy assignment | Limits the demo policy to one resource group | [../infra/main.bicep](../infra/main.bicep) |
| Validation target | Applies the assessed tags to a harmless resource for validation | [../infra/demo-target.bicep](../infra/demo-target.bicep) |
| Demo runner | Runs the assessment then both validations, printing evidence | [../demo.sh](../demo.sh) |
| OIDC identity (optional) | Managed identity, federated credential, scoped role assignment for the real CD extension | [../infra/oidc-identity.bicep](../infra/oidc-identity.bicep), see [OIDC-DEMO.md](OIDC-DEMO.md) |
| Real CI check + CD deploy demo (optional) | Runs the CI check and CD deployment for real via GitHub OIDC | [../../../../.github/workflows/val-pre-001-value-gate-demo.yml](../../../../.github/workflows/val-pre-001-value-gate-demo.yml) |

## Decision rules

- The structural validator (`scripts/validate_governance_contract.py`) marks
  a hypothesis `incomplete` unless the JSON Schema-checked evidence —
  `metric.name`, `metric.target` (numeric), `metric.direction`
  (`increase`/`decrease`), `baseline.status` (`measured`/`net_new`),
  `owner`, `businessCaseId`, and `expectedOutcome` — is all present and
  non-blank. Whitespace-only strings count as blank (`pattern: \S` in the
  schema); a non-numeric `metric.target` (for example `"banana"`) is
  rejected explicitly by the schema's `type: number`.
- Its result becomes exactly two tags: `valueHypothesisStatus`
  (`complete`/`incomplete`) and `businessCaseId`. These are the only two
  values that ever cross from the governance contract into an Azure
  request.
- The Azure Policy rule applies only when `goLiveRequested=true`. It denies
  when `valueHypothesisStatus != complete`, or `businessCaseId` is missing or
  empty. It reads only these two tags on the incoming request; it never reads
  the governance contract and cannot verify the tags were produced by a real
  validator run rather than typed in by hand.
- With `--enforce`, the validator itself exits non-zero when the status is
  `incomplete`. Only the CI check job passes this flag; the default mode
  always exits 0 because it is a local configuration assessment, not an
  enforcement point.

## Best-practice choices

The demo uses the supported Azure Policy engine directly, scopes its
assignment to one resource group, authenticates through the Azure CLI or
OIDC (never a stored client secret), and validates rather than creates the
placeholder workload in the core path. The optional CD job's managed
identity holds only the built-in **Monitoring Contributor** role on the demo
resource group, the least-privilege built-in role that can manage the
`Microsoft.Insights/actionGroups` resource `demo-target.bicep` declares,
matching the role-per-resource pattern used by `controls/privacy/PRI-001`/
`PRI-004`.

## CI check as a mandatory pipeline input

The governance contract is a single, static file checked into source
control, so any CI/CD platform can treat it as a mandatory element of an
agent's definition. A minimal GitHub Actions CI check step:

```yaml
- name: Value hypothesis CI check
  run: |
    result=$(python scripts/validate_governance_contract.py \
      --contract .fwf/agents/helpdesk-tier1-triage/governance.yaml \
      --control VAL-PRE-001 --enforce)
    echo "$result"
```

This CI check and the Azure Policy deployment gate are complementary, not
duplicative: the CI check gives fast, credential-free feedback before any
Azure call is made. Azure Policy is the final authoritative check for
requests that are explicitly in the tagged go-live scope
(`goLiveRequested=true`), and still denies such a request when CI was skipped
if its required decision tags are missing or invalid. Azure Policy does not
make every Azure deployment fail closed: requests that omit the trigger tag
are outside this policy rule's scope, and valid-looking metadata can be forged.
Those paths must be constrained by the governed production deployment
identity/path. See the gate design in `../../ARCHITECTURE.md`.

## Evidence detail

The `demo.sh` terminal record and the `.github/workflows/val-pre-001-value-gate-demo.yml`
job results are the two evidence sources. Both report the control ID, policy
version, both Azure results, deployment correlation names, a UTC timestamp,
the action taken, and the accountable role. Neither ever contains real
business case data, personal data, prompts, or model output.

## Known limitations (detail)

- Only one metric per hypothesis is represented; multi-metric agents are a
  documented simplification.
- No revision history is tracked in the governance contract; a re-baselined
  hypothesis overwrites its fields with no audit trail.
- Structural completeness is not target realism: nothing checks that the
  metric is well-chosen, the target is achievable, or the named owner is a
  real, consenting accountable person.
- Azure Policy evaluates this control only for requests tagged
  `goLiveRequested=true`; omission of that trigger tag is outside the policy
  rule's scope, and Azure Policy cannot distinguish genuine decision tags from
  forged valid-looking metadata.
