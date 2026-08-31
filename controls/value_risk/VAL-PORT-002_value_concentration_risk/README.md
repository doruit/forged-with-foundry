<!-- generated-control-readme -->
<p align="center">
    <img src="../../../media/themepack/fwf-badge-small-only-logo.png" alt="Forged with Foundry planned control" width="223">
</p>

# VAL-PORT-002 — Value concentration risk

> **Status:** Planned — the demo has not been implemented yet.
>
> **Last reviewed:** Not yet reviewed; set a date when implementation begins.

Remove the `generated-control-readme` marker when implementation begins so
future catalog regeneration preserves this README.

## Overview

This control detects **value concentration risk** during the **Portfolio** lifecycle
phase. This page will evolve with the implementation while retaining the
standard control documentation structure.

## Control contract

| Field | Value |
|---|---|
| **ID** | VAL-PORT-002 |
| **Lifecycle phase** | Portfolio |
| **Category / domain** | Value Risk |
| **Control / signal** | Value concentration risk |
| **Evidence / source** | Value by agent/domain |
| **Trigger / threshold** | Top agent/domain carries excessive value dependency |
| **Action / gate effect** | Resilience/redundancy plan |
| **Accountable role** | Executive Sponsor |

## Control objective

Document the risk addressed by this control, the expected outcome, and why the
control must remain deterministic and independently enforceable where relevant.

## Logical design

```mermaid
flowchart LR
    I[Governed input or evidence] --> D[Detection and evaluation]
    D --> P{VAL-PORT-002 policy decision}
    P -->|Below threshold| A[Allow or continue]
    P -->|Threshold reached| E[Apply gate effect]
    E --> O[Notify Executive Sponsor]

    classDef governance fill:#6E56CF,stroke:#A855F7,color:#FFFFFF
    classDef platform fill:#3B82F6,stroke:#00D4FF,color:#FFFFFF
    classDef success fill:#22C55E,stroke:#22C55E,color:#0D1117
    classDef attention fill:#F59E0B,stroke:#F59E0B,color:#0D1117
    class D,P governance
    class I platform
    class A success
    class E,O attention
```

## Infrastructure architecture

```mermaid
flowchart TB
    S[Signal or evidence source] --> C[Control evaluator]
    C --> R[Decision and audit record]
    R --> G[Governance action or gate]
    G --> M[Monitoring and accountable role]

    classDef governance fill:#6E56CF,stroke:#A855F7,color:#FFFFFF
    classDef platform fill:#3B82F6,stroke:#00D4FF,color:#FFFFFF
    classDef evidence fill:#00D4FF,stroke:#3B82F6,color:#0D1117
    classDef neutral fill:#1F2937,stroke:#6E56CF,color:#FFFFFF
    classDef attention fill:#F59E0B,stroke:#F59E0B,color:#0D1117
    class S neutral
    class C platform
    class R evidence
    class G governance
    class M attention
```

The implementation must replace this conceptual diagram with the actual Azure,
Microsoft Foundry, storage, identity, monitoring, and integration components.

## Implementation

### Components

- **Detector/evaluator:** To be implemented.
- **Policy decision:** To be implemented from the control contract above.
- **Action or gate:** To be implemented.
- **Audit evidence:** To be implemented without exposing sensitive payloads.

### Best-practice requirements

- Keep policy enforcement outside model reasoning when a deterministic control
  is possible.
- Use least-privilege identity and secretless authentication where supported.
- Minimize retained data and exclude sensitive values from logs and alerts.
- Fail closed when a mandatory control cannot complete safely.
- Pin or document API/model versions and review them during repository updates.

## Demo

### Prerequisites

To be documented with the implementation.

### Run

To be documented with the implementation.

### Expected scenarios

| Scenario | Expected result |
|---|---|
| Below threshold | Control allows processing or records a healthy signal. |
| Threshold reached | Control applies **Resilience/redundancy plan** and routes accountability to **Executive Sponsor**. |
| Evaluation unavailable | Mandatory enforcement fails closed or follows the documented fallback. |

## Evidence and observability

Document emitted metrics, traces, audit records, alert payloads, retention, and
the evidence required to prove that the control operated as designed.

## Security and privacy

Document threat boundaries, RBAC, managed identities, network/data flows,
sensitive-data handling, cleanup, and failure behavior.

## Validation

Document automated tests, manual demo checks, expected results, and known
limitations.

## Cleanup

Document control-specific cleanup steps and identify shared resources that must
not be deleted accidentally.

## References

- Add links to the latest authoritative Microsoft Learn documentation used by
  the implementation.
- Source catalog: [Governance Signals Repo.pdf](../../../docs/Governance%20Signals%20Repo.pdf)

---

<p align="center">
    <img src="../../../media/themepack/fwf-footer.png" alt="Forged with Foundry" width="814">
</p>
