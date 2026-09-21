# customer-service-agent (fictional example workload repository)

This is a **fictional workload repository**, not a real Forged with Foundry
control. It exists to show, in miniature, where the Forged with Foundry
Agent Governance Contract belongs inside a normal application repository —
not inside this repository's own `controls/` catalog.

## Table of contents

* [What this shows](#what-this-shows)
* [Intentionally omitted](#intentionally-omitted)
* [Try it](#try-it)

## What this shows

```
customer-service-agent/
└── .fwf/
    └── agents/
        └── customer-support-agent/
            ├── governance.yaml
            └── evidence/
                └── kpi-baseline.json
```

- **The discovery path is fixed:** `.fwf/agents/<agent-id>/governance.yaml`.
  A validator (or CI pipeline) never needs to be told where to look; it
  globs this exact shape. See
  [`../../../docs/governance-contract.md`](../../../docs/governance-contract.md).
- **One subfolder per deployable agent.** A repository with several agents
  (a triage bot, a summarizer, a scheduling assistant) would have one
  `.fwf/agents/<agent-id>/` folder per agent, each with its own
  `governance.yaml` declaring only the controls that actually apply to
  *that* agent.
- **`evidence/kpi-baseline.json` is illustrative supporting detail**, not a
  file the FwF schema requires or validates. A workload team keeps whatever
  backup makes a declared number auditable (sample size, measurement
  window, method); the schema only checks the number itself
  (`evidence.baseline.value`/`measuredDate`) declared inline in
  `governance.yaml`.
- **Microsoft or vendor agent manifests may coexist elsewhere in the same
  repository** — for example a real Microsoft Foundry hosted-agent
  `agent.yaml` (with its own `kind`/`protocols`/`resources` schema) living
  under `src/agents/customer_support/`. The FwF governance contract
  **complements** that manifest; it never replaces, re-validates, or claims
  to be it. This example's `governance.yaml` references that hypothetical
  path via `spec.agentRef.definition`, but does not require the file to
  exist.
- **CI validates all contracts before deployment.** A pipeline step calling
  `scripts/validate_governance_contract.py --root .` from this repository's
  root would discover and validate every `.fwf/agents/*/governance.yaml` in
  one pass, the same way it does inside Forged with Foundry's own control
  demos.

## Intentionally omitted

Real runtime code (`src/agents/customer_support/`) and infrastructure-as-code
(`infra/customer-support-agent.bicep`) for this fictional agent are
deliberately **not** included here — empty placeholder source/IaC files
would only add noise without teaching anything about the governance
contract, which is this example's actual point. In a real workload
repository, those folders would hold the agent's application code and its
IaC, side by side with the `.fwf/` folder shown above.

## Try it

```bash
.venv/bin/python scripts/validate_governance_contract.py \
  --root examples/workload-repositories/customer-service-agent \
  --control VAL-PRE-001
.venv/bin/python scripts/validate_governance_contract.py \
  --root examples/workload-repositories/customer-service-agent \
  --control VAL-PRE-002
```

Both should report `"status": "complete"` — every field each control's
schema requires is present.

This is only the **schema-valid** check (this repository's own evidence is
structurally complete). It is also used as the target of the **policy-pass**
demo manifest at
[`examples/deployment-manifests/core-profile.yaml`](../../deployment-manifests/README.md),
which asserts this specific agent has both required controls before a
deployment would be allowed to proceed:

```bash
scripts/deployment_gate.sh \
  --manifest examples/deployment-manifests/core-profile.yaml \
  --profile core \
  --root examples/workload-repositories/customer-service-agent
```

See
[`docs/governance-contract.md`](../../../docs/governance-contract.md#where-enforcement-happens)
for how schema-valid, policy-pass, and deployment-allowed differ.
