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

JSON Schema `contains`/`minContains` could technically require one fixed
contract document to declare a specific control ID, but that would hardcode
the required-control set into the structural schema itself, forcing a schema
change every time an organisation's requirements change, and giving every
deployment the same fixed rule instead of letting it vary per deployment
profile (see `examples/deployment-manifests/`). [Open Policy Agent](https://www.openpolicyagent.org/)
via [Conftest](https://www.conftest.dev/) was chosen instead so this
coverage decision is centrally managed **policy data**, kept separate from
the structural contract schemas and changeable per profile without touching
`schemas/governance-contract/` -- the standard, widely supported way to
express and unit-test this kind of "reject the input unless it satisfies
these organisational rules" policy against structured (JSON/YAML) input,
without inventing a bespoke policy engine for this repository.

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

CI verifies the downloaded release tarball's SHA-256 checksum
(`e738506fd808f7dc9794ce8e325f89b14932891a4841fe45f1f24c4a9bb3ed96` for
`conftest_0.70.0_Linux_x86_64.tar.gz`, from the official release's
`checksums.txt`) before installing it, in both `.github/workflows/tests.yml`
and both VAL-PRE-001 and VAL-PRE-002 demo workflows. Bumping
`CONFTEST_VERSION` requires updating `CONFTEST_SHA256` in all three workflows to
match the new release's `checksums.txt`, or the install step fails closed.

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
  valid contract declaring every control the chosen profile requires, and
  that the deployment manifest itself was a valid, non-empty, unambiguous
  policy input (missing/empty/wrong-typed/duplicated/unknown-control-ID
  manifests are rejected before any contract is even discovered -- see
  `scripts/build_deployment_plan.py`'s manifest validation).
- It does **not** authenticate that the underlying evidence in a
  `governance.yaml` is true, current, or produced by a real assessment --
  see the `disclaimer` field `scripts/build_evidence.py` always attaches to
  its output.
- It is not a cryptographic deployment attestation. Treat its evidence output
  as a record of what the gate checked and decided, not as unforgeable proof.
- Its evidence records `workloadSourceCommit` (from `--root`, explicitly
  documented as `unknown` or `-dirty` when the workload is not a clean git
  working tree) separately from `frameworkRevision` (this repository's own
  commit for `schemas/governance-contract`/`policy/governance-contract`),
  and `contractHashes` computed once while each contract was actually read
  and assessed -- never by re-reading files afterward.
- [VAL-PRE-001's workflow](../../.github/workflows/val-pre-001-value-gate-demo.yml)
  calls the gate inside its deployment job.
  [VAL-PRE-002's workflow](../../.github/workflows/val-pre-002-baseline-gate-demo.yml)
  runs the gate credential-free over its checked-out candidate, before the
  dependent OIDC release job. Both upload gate evidence; see each control's
  walkthrough for which workflow revision was actually live-tested.
