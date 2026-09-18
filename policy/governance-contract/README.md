# Governance-contract policy layer (Conftest / OPA Rego)

This directory holds the **organisational policy** layer of the Forged with
Foundry Agent Governance Contract architecture: which agents are expected to
exist, and which controls are mandatory for them before a deployment is
allowed to proceed. It is deliberately separate from
[`schemas/governance-contract/`](../../schemas/governance-contract/README.md),
which owns **structural validity** (is this contract well-formed, are dates
real, are fields the right shape). See
[`docs/governance-contract.md`](../../docs/governance-contract.md) for how the
two layers fit together end to end.

## Why Conftest / Rego, and not more Python

JSON Schema cannot express "this specific set of agents must each declare
these specific controls" -- that is an organisational policy decision, not a
structural one, and it varies per deployment profile (see
`examples/deployment-manifests/`). [Open Policy Agent](https://www.openpolicyagent.org/)
via [Conftest](https://www.conftest.dev/) is the standard, widely supported
way to express and unit-test this kind of "reject the input unless it
satisfies these organisational rules" policy against structured (JSON/YAML)
input, without inventing a bespoke policy engine for this repository.

## Files

| File | Purpose |
| --- | --- |
| `deployment_gate.rego` | The `deny` rules a deployment plan document must satisfy. |
| `deployment_gate_test.rego` | Rego unit tests for those rules, run via `conftest verify`. |

## Pinned Conftest version

This repository's CI installs and this policy has been tested against
**Conftest 0.70.0** (which defaults to Rego v1 syntax: `if` / `contains`
keywords in rule bodies and partial sets). If you install a different major
version locally, re-run `conftest verify` before trusting the result; a
future major version may change defaults again.

```bash
brew install conftest        # macOS / Linux via Homebrew
conftest --version            # confirm 0.70.0 or note the difference
```

## Running the policy layer locally

```bash
# Unit-test the Rego rules themselves (no real contracts needed):
conftest verify --policy policy/governance-contract

# Evaluate a real deployment plan document against the rules:
python scripts/build_deployment_plan.py \
  --manifest examples/deployment-manifests/core-profile.yaml \
  --profile core \
  --root examples/workload-repositories/customer-service-agent \
  > /tmp/deployment-plan.json
conftest test --policy policy/governance-contract --output json /tmp/deployment-plan.json

# Or run the whole boundary end to end (discovery -> schema validation ->
# Conftest -> evidence artifact) via the single enforcement script:
scripts/deployment_gate.sh \
  --manifest examples/deployment-manifests/core-profile.yaml \
  --profile core \
  --root examples/workload-repositories/customer-service-agent
```

## What this layer does and does not prove

- It proves that, at evaluation time, every expected agent had a structurally
  valid contract declaring every control the chosen profile requires.
- It does **not** authenticate that the underlying evidence in a
  `governance.yaml` is true, current, or produced by a real assessment --
  see the `disclaimer` field `scripts/build_evidence.py` always attaches to
  its output.
- It is not a cryptographic deployment attestation. Treat its evidence output
  as a record of what the gate checked and decided, not as unforgeable proof.
