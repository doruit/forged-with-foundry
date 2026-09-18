# VAL-PRE-001 — implementation detail

Deep-dive companion to [`../README.md`](../README.md). Read the README first;
this file exists so the README can stay bite-sized while still linking to
every implementation decision.

## Components

| Component | Responsibility | Location |
|---|---|---|
| `agent.yaml` fixture | Authoritative, structured value hypothesis for the helpdesk agent example | [../fixtures/agent.yaml](../fixtures/agent.yaml), [../fixtures/agent.incomplete.yaml](../fixtures/agent.incomplete.yaml) |
| Structural validator | Reduces `agent.yaml` to the two tags Azure Policy checks | [../scripts/validate_value_hypothesis.py](../scripts/validate_value_hypothesis.py) |
| Validator tests | 11 boundary cases (blank/missing/non-numeric fields, `--enforce` pass/fail) | [../scripts/test_validate_value_hypothesis.py](../scripts/test_validate_value_hypothesis.py) |
| Azure Policy definition | Expresses the authoritative `deny` rule on the two reduced tags | [../infra/policy-definition.bicep](../infra/policy-definition.bicep) |
| Policy assignment | Limits the demo policy to one resource group | [../infra/main.bicep](../infra/main.bicep) |
| Validation target | Applies the assessed tags to a harmless resource for validation | [../infra/demo-target.bicep](../infra/demo-target.bicep) |
| Demo runner | Runs the assessment then both validations, printing evidence | [../demo.sh](../demo.sh) |
| OIDC identity (optional) | Managed identity, federated credential, scoped role assignment for the real CD extension | [../infra/oidc-identity.bicep](../infra/oidc-identity.bicep), see [OIDC-DEMO.md](OIDC-DEMO.md) |
| Real CI check + CD deploy demo (optional) | Runs the CI check and CD deployment for real via GitHub OIDC | [../../../../.github/workflows/val-pre-001-value-gate-demo.yml](../../../../.github/workflows/val-pre-001-value-gate-demo.yml) |

## Decision rules

- The structural validator marks a hypothesis `incomplete` unless `metric` is
  non-blank, `target.value` is present **and numeric**, `target.direction` is
  `increase` or `decrease`, `baseline.status` is `measured` or `net_new`,
  `owner` is non-blank, and `business_case_id` is non-blank. Whitespace-only
  strings count as blank; a non-numeric `target.value` (for example
  `"banana"`) is rejected explicitly.
- Its result becomes exactly two tags: `valueHypothesisStatus`
  (`complete`/`incomplete`) and `businessCaseId`. These are the only two
  values that ever cross from `agent.yaml` into an Azure request.
- The Azure Policy rule applies only when `goLiveRequested=true`. It denies
  when `valueHypothesisStatus != complete`, or `businessCaseId` is missing or
  empty. It reads only these two tags on the incoming request; it never reads
  `agent.yaml` and cannot verify the tags were produced by a real validator
  run rather than typed in by hand.
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

`agent.yaml` is a single, static file checked into source control, so any
CI/CD platform can treat it as a mandatory element of an agent's definition.
A minimal GitHub Actions CI check step:

```yaml
- name: Value hypothesis CI check
  run: |
    result=$(python scripts/validate_value_hypothesis.py agent.yaml)
    echo "$result"
    status=$(echo "$result" | python -c "import json, sys; print(json.load(sys.stdin)['valueHypothesisStatus'])")
    [ "$status" = "complete" ]
```

This CI check and the Azure Policy deployment gate are independent and
complementary, not duplicative: the CI check gives fast, credential-free
feedback before any Azure call is made, while Azure Policy remains the final,
authoritative check at deployment time and still denies a request that
bypasses CI entirely (a manual `az deployment` call). See the two-layer gate
design in `../../ARCHITECTURE.md`.

## Evidence detail

The `demo.sh` terminal record and the `.github/workflows/val-pre-001-value-gate-demo.yml`
job results are the two evidence sources. Both report the control ID, policy
version, both Azure results, deployment correlation names, a UTC timestamp,
the action taken, and the accountable role. Neither ever contains real
business case data, personal data, prompts, or model output.

## Known limitations (detail)

- Only one metric per hypothesis is represented; multi-metric agents are a
  documented simplification.
- No revision history is tracked in `agent.yaml`; a re-baselined hypothesis
  overwrites its fields with no audit trail.
- Structural completeness is not target realism: nothing checks that the
  metric is well-chosen, the target is achievable, or the named owner is a
  real, consenting accountable person.
