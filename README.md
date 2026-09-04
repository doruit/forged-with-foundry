<p align="center">
	<img src="media/themepack/fwf-banner-trans.png" alt="Forged with Foundry — practical AI governance controls" width="100%">
</p>

# Forged with Foundry — AI Governance Control Demos

[![License: MIT](https://img.shields.io/github/license/doruit/forged-with-foundry)](LICENSE)
[![Tests](https://github.com/doruit/forged-with-foundry/actions/workflows/tests.yml/badge.svg)](.github/workflows/tests.yml)
![Community demos](https://img.shields.io/badge/community%20demos-6-6E56CF)
![PRs welcome](https://img.shields.io/badge/PRs-welcome-22C55E)

Forged with Foundry is a hands-on series of practical AI governance control demos. The examples primarily build on Microsoft Foundry and the broader Microsoft AI ecosystem, with the Microsoft Agent Governance Toolkit featuring where it provides a useful governance or enforcement capability. Individual demos may combine additional Microsoft and non-Microsoft technologies where they help demonstrate the control in the most practical way.

> **Governance outside the agent. Intelligence inside the agent.**

> [!IMPORTANT]
> **This repository grows one bite-sized governance control at a time.** The
> full catalog is the roadmap. Every week or month, selected controls are
> turned into small, isolated community demos that show one governance
> decision, the Microsoft capabilities reused, and the evidence produced.

## Start here

> [!TIP]
> **New to the repository? Start with a community demo below.** The wider control
> catalog is the roadmap; planned entries are useful for discovery but do not
> contain a working implementation yet.

### Recently added — community demos

<!-- Keep implemented or validated demos only. Newest first. Include guided exercises, hybrid demos, and deployable demos. -->

| Demo | What you will learn | Format · level · time | Date added |
|---|---|---|---|
| **[PRI-PRE-002 — Lawful basis or purpose missing](controls/privacy/PRI-PRE-002_lawful_basis_or_purpose_missing/README.md)**<br>[Run the demo](controls/privacy/PRI-PRE-002_lawful_basis_or_purpose_missing/README.md#demo) · [Scope](controls/privacy/PRI-PRE-002_lawful_basis_or_purpose_missing/README.md#demo-scope) · [Assessment](controls/privacy/PRI-PRE-002_lawful_basis_or_purpose_missing/ASSESSMENT.md) | Flag a project processing personal data without a documented GDPR lawful basis or purpose using a real Azure Policy `audit` assignment — a non-blocking remediation flag, contrasting with PRI-PRE-001's hard `deny` block. | Deployable · Advanced · 30–45 min | 2026-09-04 |
| **[PRI-PRE-001 — DPIA required but missing](controls/privacy/PRI-PRE-001_dpia_required_but_missing/README.md)**<br>[Run the demo](controls/privacy/PRI-PRE-001_dpia_required_but_missing/README.md#demo) · [Scope](controls/privacy/PRI-PRE-001_dpia_required_but_missing/README.md#demo-scope) · [Assessment](controls/privacy/PRI-PRE-001_dpia_required_but_missing/ASSESSMENT.md) | Block go-live for a high-risk AI system without a completed DPIA using a real Azure Policy `deny` assignment as the actual enforcement backstop, not just application code. | Deployable · Advanced · 45–60 min | 2026-09-04 |
| **[PRI-004 — Personal data in logs](controls/privacy/PRI-004_personal_data_in_logs/README.md)**<br>[Run the demo](controls/privacy/PRI-004_personal_data_in_logs/README.md#demo) · [Scope](controls/privacy/PRI-004_personal_data_in_logs/README.md#demo-scope) · [Assessment](controls/privacy/PRI-004_personal_data_in_logs/ASSESSMENT.md) | Detect personal data in real Azure Monitor Logs, keep the model non-authoritative, and guard a real, asynchronous Data Purge request with a content-hash re-verification. | Deployable · Intermediate · 45–60 min | 2026-09-04 |
| **[PRI-003 — Data subject request SLA breach](controls/privacy/PRI-003_data_subject_request_sla_breach/README.md)**<br>[Run the demo](controls/privacy/PRI-003_data_subject_request_sla_breach/README.md#demo) · [Scope](controls/privacy/PRI-003_data_subject_request_sla_breach/README.md#demo-scope) · [Assessment](controls/privacy/PRI-003_data_subject_request_sla_breach/ASSESSMENT.md) | Detect an at-risk or breached DSR SLA deadline, keep the model non-authoritative, and guard a one-time due-date extension with ETag concurrency. | Deployable · Foundation / Intermediate · 30–45 min | 2026-09-03 |
| **[PRI-002 — Retention violation](controls/privacy/PRI-002_retention_violation/README.md)**<br>[Run the demo](controls/privacy/PRI-002_retention_violation/README.md#demo) · [Scope](controls/privacy/PRI-002_retention_violation/README.md#demo-scope) · [Assessment](controls/privacy/PRI-002_retention_violation/ASSESSMENT.md) | Detect a Blob missed by a lifecycle tag, keep the model non-authoritative, require explicit approval, and verify guarded deletion. | Deployable · Foundation / Intermediate · 30–45 min | 2026-09-03 |
| **[PRI-001 — PII exposure](controls/privacy/PRI-001_pii_exposure/README.md)**<br>[Run the demo](controls/privacy/PRI-001_pii_exposure/README.md#demo) · [Scope](controls/privacy/PRI-001_pii_exposure/README.md#demo-scope) · [Assessment](controls/privacy/PRI-001_pii_exposure/ASSESSMENT.md) | Put Text PII and native Document PII around a Foundry agent so only safe or redacted content crosses the boundary. | Deployable · Foundation · 30–45 min | 2026-08-31 |

### Choose your path

- **Try a control now:** choose a demo from the table above.
- **Understand the approach:** read [Purpose](#purpose) and the
  [repository model](#repository-model).
- **Explore the roadmap:** browse the [category groups](#category-overview), the
  [controls directory](controls), or the
  [source catalog](docs/Governance%20Signals%20Repo.pdf).
- **Add a control:** start with the
  [control assessment template](docs/control-assessment-template.md), then use
  the [control README template](docs/control-readme-template.md).

## FAQ

**Why not just use AGT, ACS, or Foundry Control Plane directly?**
In most cases, you should. This repository is not an alternative to those
platforms. Every control starts with an assessment that checks whether AGT,
ACS, Microsoft Foundry, Purview, Defender, Entra, or another supported
Microsoft capability already solves the problem before any custom code gets
written. Each control's `ASSESSMENT.md` records that reasoning. See the
reuse-first rule in [.github/copilot-instructions.md](.github/copilot-instructions.md)
for the exact evaluation process.

**Is this repository production-ready?**
No. It is a demonstration repository for learning and prototyping. See the
[Disclaimer](#disclaimer).

**How often is it updated?**
One or more controls at a time, weekly or monthly. See the
[Incremental roadmap](#incremental-roadmap).

## Purpose

AI governance becomes useful when policy is translated into observable,
reviewable, testable, or enforceable controls. This repository demonstrates
that translation through guided exercises, small executable examples, and
deployable demos. Each implemented control shows:

- the risk or signal being governed and the control contract;
- how the control works and the resulting gate or escalation;
- where enforcement or authoritative decision-making sits relative to an AI
  agent, workflow, or human governance process;
- the evidence the control produces;
- the smallest useful demonstration, with synthetic scenarios and expected outcomes;
- relevant observability, security, privacy, and validation considerations.

This is a demonstration repository, not a complete production governance platform. Implementations should be adapted to organizational policy, risk appetite, legal requirements, and operational standards.

## Incremental roadmap

<p align="center">
	<img src="media/themepack/fwf-badge-small-one-control-a-week.png" alt="One governance control at a time" width="184">
</p>

The repository is intentionally expanded **weekly or monthly**, one or more controls at a time. Each increment may add a new demo, improve an existing control, refresh dependencies, or align documentation and architecture with new platform capabilities.

> [!TIP]
> New controls ship weekly or monthly. Follow
> [Douwe van de Ruit on LinkedIn](https://www.linkedin.com/in/dvanderuit/) for
> release announcements, or star/watch this repository on GitHub.

Updates follow these principles:

1. **Use current best practices.** Implementations are reviewed against the latest authoritative Microsoft documentation and supported SDK/API behavior.
2. **Prefer focused demos.** Each control remains understandable and reproducible without requiring a complete governance platform or unnecessary deployment.
3. **Keep governance explicit.** Thresholds, decisions, actions, accountable roles, and failure behavior are documented rather than hidden in model reasoning.
4. **Secure by default.** Prefer managed identity, least privilege, data minimization, metadata-only alerts, secure cleanup, and fail-closed behavior for mandatory controls.
5. **Evolve transparently.** API versions, model choices, assumptions, known limitations, and validation evidence belong in the control documentation.

Because cloud and AI capabilities change quickly, “latest best practices” means **reviewed at the time of each control update**, not permanently current. Every implemented control should identify the authoritative references on which it is based.

## Repository model

The catalog is organized by governance category and control. A control uses
only the folders needed by its selected demo format:

```text
controls/<category-group>/<control-id_control-name>/
├── README.md          # Complete control and demo documentation
├── exercise/          # Optional guided scenario, evidence pack, and answer key
├── infra/             # Optional Azure resources owned by this control
├── src/               # Optional control-specific implementation
├── tests/             # Optional tests for executable decision logic
└── ...                # Optional templates, UI, configuration, and media assets
```

```mermaid
flowchart LR
  A[Lifecycle phase] --> B[Category group]
  B --> C[Control]
  C --> D{Demo format}
  D -->|Guided exercise| E[Scenario, evidence pack, answer key]
  D -->|Hybrid demo| F[Guided core + small executable]
  D -->|Deployable demo| G[Real Azure deployment]
  E --> H[Decision, evidence, accountable role]
  F --> H
  G --> H

  classDef governance fill:#6E56CF,stroke:#A855F7,color:#FFFFFF
  classDef platform fill:#3B82F6,stroke:#00D4FF,color:#FFFFFF
  classDef success fill:#22C55E,stroke:#22C55E,color:#0D1117
  class A,B,C governance
  class D,E,F,G platform
  class H success
```

Control-specific code, infrastructure, variables, dependencies, tests,
configuration, and media belong in that control's folder. Only resources and
variables generic to all controls belong in [infra](infra). Control deployments
run incrementally after the shared deployment. The source catalog is available
in [docs/Governance Signals Repo.pdf](docs/Governance%20Signals%20Repo.pdf).

The catalog currently covers **160 controls across 56 categories, grouped into 13 category groups**, and three lifecycle phases: **Pre-Live**, **Live**, and **Portfolio**. A catalog entry may exist before its community demo is available.

## Category overview

The full roadmap is under [controls](controls). Most catalog folders currently
describe **planned** controls. Use [Recently added — community demos](#recently-added--community-demos)
when you want a completed exercise or working example; use this overview when
you want to explore what may be implemented next.

| Category group | Example controls covered by the catalog |
|---|---|
| **Privacy** | PII exposure, retention violations, personal data in logs, DPIA and lawful-basis checks |
| **Security** | Prompt-injection attempts, successful prompt injection, unauthorized access, data exfiltration, secret exposure, supply-chain vulnerabilities |
| **Grounding and quality** | Low grounding scores, hallucination rate, answer accuracy, citation support, production evaluation regressions |
| **Responsible AI and fairness** | Bias indicators, fairness degradation, explainability gaps, missing impact assessments |
| **Data and knowledge** | Data classification, lineage, data quality, knowledge freshness, conflicting sources, retrieval relevance, permission trimming |
| **Runtime and operations** | Availability, latency, failure rates, rate limits, agent loops, context contamination, stale memory, missing traces |
| **Autonomy and human oversight** | Undefined autonomy boundaries, HITL bypass, irreversible actions, missing human gates |
| **Tool governance** | Unauthorized tool use, excessive calls, tool failures, credential misuse, missing inventories |
| **Change, release, and evaluation** | Unapproved prompt/model/source changes, guardrail regression, test-coverage gaps, red-team testing, release evidence |
| **Compliance, legal, and risk** | Regulatory control failures, policy violations, IP/copyright risk, residual-risk acceptance, risk concentration |
| **Value, adoption, and FinOps** | KPI underperformance, ROI degradation, adoption decline, cost spikes, retry-loop leakage, portfolio value |
| **Architecture, resilience, and scale** | Architecture drift, unapproved integration patterns, rollback design, scale readiness, reusable capabilities |
| **Lifecycle and portfolio governance** | Ownership changes, overdue reviews, registry completeness, retirement, archival evidence, governance cadence |

## Shared setup

General infrastructure guidance is in [infra/README.md](infra/README.md).
Control-specific setup, exercise, and run instructions belong in each control README.
Use [constraints.txt](constraints.txt) as an optional overlay when you want the
exact top-level dependency versions tested by this repository.
Environment files stay beside their owning infrastructure or control and must
never be committed.

## Community

- Read the [Contributing guide](CONTRIBUTING.md) before proposing a new control.
- This project follows the [Code of Conduct](CODE_OF_CONDUCT.md).
- Report vulnerabilities through the process in [SECURITY.md](SECURITY.md), not a public issue.
- Licensed under the [MIT License](LICENSE).

## Disclaimer

The controls and thresholds in this repository are examples for education and prototyping. They do not constitute legal, compliance, security, or risk advice. Production adoption requires review and approval by the appropriate accountable roles.

---

*Maintained by [Douwe van de Ruit](https://www.linkedin.com/in/dvanderuit/), Sr. AI Transformation Lead & Solution Architect at Capgemini and Microsoft MVP on Microsoft Foundry.*

<p align="center">
	<img src="media/themepack/fwf-footer.png" alt="Forged with Foundry" width="100%">
</p>
