# Forged with Foundry Agent Governance Contract — schemas

Declarative JSON Schema only. No executable logic lives in this folder; the
validator that discovers and checks contract instances against these
schemas is [`scripts/validate_governance_contract.py`](../../scripts/validate_governance_contract.py).

Read [`docs/governance-contract.md`](../../docs/governance-contract.md) first
for the full explanation of what this architecture is, what it is not, and
how to add a newly implemented control to it.

## Layout

```
schemas/governance-contract/
├── README.md                                  (this file)
└── v1alpha1/
    ├── fwf-governance-contract.schema.json     the central/root schema
    └── controls/
        ├── VAL-PRE-001.schema.json             one schema per implemented control
        └── ...
```

Only controls that are actually `Implemented`/`Validated` get a schema file
here. A planned or skeleton control never gets a placeholder schema.

## Versioning

`v1alpha1` is the contract **API version** — the shape of the envelope
(`apiVersion`, `kind`, `metadata`, `spec`). It changes independently of:

- a control's own `version` field inside a contract instance (that control's
  evidence shape), and
- the FwF catalog control ID itself (`VAL-PRE-001`), which is permanent.

A future breaking change to the envelope gets a new `v1alpha2`/`v1beta1`/...
folder alongside this one, never an in-place rewrite of `v1alpha1`.
