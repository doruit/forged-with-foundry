# Forged with Foundry — AI Governance Control Demos

A growing repository of practical, independently runnable AI governance control demos built with Microsoft Foundry and related Azure services.

> **Governance outside the agent; intelligence inside the agent.**

## Purpose

AI governance becomes useful when policy is translated into observable, testable, and enforceable controls. This repository demonstrates that translation in code. Each implemented control shows:

- the governance risk and deterministic control contract;
- where enforcement sits relative to an AI agent or workflow;
- the Azure and Microsoft Foundry infrastructure involved;
- the logical decision flow and resulting gate or escalation;
- a small demo with safe scenarios and expected outcomes;
- evidence, observability, security, privacy, and validation considerations.

This is a demonstration repository, not a complete production governance platform. Implementations should be adapted to organizational policy, risk appetite, legal requirements, and operational standards.

## Incremental roadmap

The repository is intentionally expanded **weekly or monthly**, one or more controls at a time. Each increment may add a new demo, improve an existing control, refresh dependencies, or align documentation and architecture with new platform capabilities.

Updates follow these principles:

1. **Use current best practices.** Implementations are reviewed against the latest authoritative Microsoft documentation and supported SDK/API behavior.
2. **Prefer focused demos.** Each control remains understandable and runnable without requiring a complete governance platform.
3. **Keep governance explicit.** Thresholds, decisions, actions, accountable roles, and failure behavior are documented rather than hidden in model reasoning.
4. **Secure by default.** Prefer managed identity, least privilege, data minimization, metadata-only alerts, secure cleanup, and fail-closed behavior for mandatory controls.
5. **Evolve transparently.** API versions, model choices, assumptions, known limitations, and validation evidence belong in the control documentation.

Because cloud and AI capabilities change quickly, “latest best practices” means **reviewed at the time of each control update**, not permanently current. Every implemented control should identify the authoritative references on which it is based.

## Repository model

The catalog is organized by governance category and control:

```text
controls/<category>/<control-id_control-name>/
├── README.md          # Complete control and demo documentation
└── ...                # Optional implementation assets local to the control
```

Shared application code belongs in [app](app), reusable helpers in [shared](shared), and reusable infrastructure in [infra](infra). The source catalog is available in [docs/Governance Signals Repo.pdf](docs/Governance%20Signals%20Repo.pdf).

The catalog currently covers **160 controls across 56 categories** and three lifecycle phases: **Pre-Live**, **Live**, and **Portfolio**. A catalog entry may be planned before its demo is implemented; its README states the current status.

## Category overview

The full catalog is under [controls](controls). This grouped overview shows representative topics that are implemented or planned.

| Category group | Example controls covered by the catalog |
|---|---|
| **Security** | Prompt-injection attempts, successful prompt injection, unauthorized access, data exfiltration, secret exposure, supply-chain vulnerabilities |
| **Privacy** | PII exposure, retention violations, personal data in logs, DPIA and lawful-basis checks |
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

Examples of catalog entries:

- [PRI-001 — PII exposure](controls/privacy/PRI-001_pii_exposure/README.md)
- [SEC-001 — Prompt injection attempts](controls/security/SEC-001_prompt_injection_attempts/README.md)
- [RUN-001 — Low confidence or grounding score](controls/runtime/RUN-001_low_confidence_or_grounding_score/README.md)
- [QLT-005 — Citation support failure](controls/grounding/QLT-005_citation_support_failure/README.md)
- [TOOL-001 — Unauthorized tool usage](controls/tool_governance/TOOL-001_unauthorized_tool_usage/README.md)
- [FIN-001 — Cost spike](controls/finops/FIN-001_cost_spike/README.md)

## Standard control README

Every control README follows the same readable pattern:

1. **Status and overview**
2. **Control contract** — ID, phase, category, signal, evidence, threshold, action, and accountable role
3. **Control objective**
4. **Logical design** — Mermaid decision-flow diagram
5. **Infrastructure architecture** — Mermaid component/deployment diagram
6. **Implementation** — components and best-practice requirements
7. **Demo** — prerequisites, run instructions, and expected scenarios
8. **Evidence and observability**
9. **Security and privacy**
10. **Validation**
11. **Cleanup**
12. **References** — authoritative sources and catalog provenance

Use [docs/control-readme-template.md](docs/control-readme-template.md) when implementing or reviewing a control. Planned controls contain explicit placeholders; implemented controls replace those placeholders with concrete architecture, commands, evidence, and test results.

## Current implementation

The first complete demo is [PRI-001 — PII exposure](controls/privacy/PRI-001_pii_exposure/README.md). Its control README contains the architecture, logical flow, implementation details, demo instructions, and validation information. The root README deliberately keeps control-specific details out of the repository overview.

## Working with the catalog

Regenerate planned control documentation from the source catalog:

```bash
python scripts/scaffold_controls.py
```

The generator updates only generated/planned README files. It preserves implemented control documentation so detailed demos are not overwritten.

To contribute a control demo:

1. Select a planned control under [controls](controls).
2. Remove the `generated-control-readme` marker and replace every placeholder
	in its README with control-specific content. Removing the marker protects the
	implemented documentation from future catalog regeneration.
3. Add implementation and infrastructure with no hardcoded secrets.
4. Add automated tests and safe synthetic demo scenarios.
5. Verify Mermaid diagrams, links, deployment steps, cleanup, and failure paths.
6. Link authoritative Microsoft documentation and record versions/limitations.

## Shared setup

General infrastructure guidance is in [infra/README.md](infra/README.md). Control-specific deployment and run instructions belong in each control README. Use a local `.env` file for environment-specific values and secrets; never commit it.

## Disclaimer

The controls and thresholds in this repository are examples for education and prototyping. They do not constitute legal, compliance, security, or risk advice. Production adoption requires review and approval by the appropriate accountable roles.
