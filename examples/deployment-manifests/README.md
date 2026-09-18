# Deployment manifests (the "trusted pipeline" input)

These YAML files represent the small, explicit input a deployment
pipeline supplies to `scripts/deployment_gate.sh` -- **not** something a
workload repository authors or can influence. Each manifest names:

- `expectedAgents`: which agent IDs this deployment run must cover.
- `profiles.<name>.requiredControls`: which FwF control IDs are mandatory
  for agents covered by that profile.

A workload's own `.fwf/agents/<agent-id>/governance.yaml` never decides
which controls are mandatory for it -- only a manifest like these,
selected and supplied by the pipeline, can do that. See
[`../../docs/governance-contract.md`](../../docs/governance-contract.md#policy-layer).

## How a real pipeline supplies and protects this input

In a real deployment, this file lives in the **pipeline's own repository or
configuration store** (for example a platform-team-owned repo, or a
protected path with required reviewers), not in the workload repository
being deployed. It should be protected the same way any other
deployment-gating configuration is: branch protection, required reviews,
and restricted write access, so a workload team cannot quietly relax which
controls apply to it. This repository ships these manifests in `examples/`
purely to make the demo runnable; do not treat their location here as the
production pattern.

## Demos in this folder

| Manifest | Profile | Demonstrates against |
|---|---|---|
| `val-pre-001-only.yaml` | `val-pre-001-only` | `controls/value_adoption_and_finops/VAL-PRE-001_value_hypothesis_missing/fixtures/{complete,incomplete}-workload` |
| `val-pre-002-only.yaml` | `val-pre-002-only` | `controls/value_adoption_and_finops/VAL-PRE-002_kpi_baseline_missing/fixtures/{complete,incomplete}-workload` |
| `core-profile.yaml` | `core` | `examples/workload-repositories/customer-service-agent` (requires both controls together) |

Run any of them with `scripts/deployment_gate.sh`, for example:

```bash
scripts/deployment_gate.sh \
  --manifest examples/deployment-manifests/core-profile.yaml \
  --profile core \
  --root examples/workload-repositories/customer-service-agent
```
