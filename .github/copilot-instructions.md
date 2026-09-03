# Forged with Foundry — Copilot instructions

## Mission

Forged with Foundry is a series of small, isolated, runnable AI governance
control demonstrations. Each control translates a concrete risk or signal into
an explicit control contract, an appropriate enforcement point, a governance
action, safe evidence, and a reproducible best-practice implementation.

This repository demonstrates how supported capabilities work together. It is
not an alternative to Microsoft Foundry, the Microsoft Agent Governance Toolkit
(AGT), the Agent Control Specification (ACS), or existing Microsoft services.

## Reuse-first rule

Before proposing or implementing a control, assess whether the capability
already exists in:

1. AGT and its official examples;
2. ACS intervention points and runtime semantics;
3. Microsoft Foundry and Foundry Control Plane;
4. Azure API Management AI Gateway;
5. Microsoft Purview, Defender, and Entra;
6. Azure AI Content Safety and Azure AI Language;
7. Azure Monitor, Application Insights, and OpenTelemetry;
8. another supported Microsoft service, SDK, or official sample;
9. an implemented control already present in this repository.

Prefer composing and demonstrating supported capabilities over reimplementing
them. Do not create a competing policy engine, approval protocol, control
specification, audit schema, identity mechanism, content filter, evaluator,
tracing mechanism, or gateway capability when a suitable supported capability
already exists.

Custom code is limited to the smallest amount required for control-specific
deterministic policy, orchestration, adapters, safe evidence, and the teaching
interface. Document why every custom component is necessary.

## Mandatory assessment before implementation

Do not implement a new control until its `ASSESSMENT.md` has been completed
using `docs/control-assessment-template.md`.

The assessment must identify existing capabilities and samples, what will be
reused, the smallest genuine gap, overlap with existing controls, and the unique
learning outcome. Classify the proposal as:

- `REUSE_ONLY`: existing documentation or samples are sufficient;
- `COMPOSE`: demonstrate a useful combination of existing capabilities;
- `ADAPT`: add a small adapter around existing capabilities;
- `IMPLEMENT_GAP`: implement a genuine missing control capability;
- `REJECT_DUPLICATE`: do not implement because it duplicates existing work.

Only `COMPOSE`, `ADAPT`, and `IMPLEMENT_GAP` normally become new demos. During
the assessment task, stop before creating code or infrastructure.

## Bite-sized demo scope

Each demo must:

- demonstrate one primary governance decision;
- use the smallest realistic architecture;
- remain understandable and runnable in isolation;
- avoid becoming a generic governance platform;
- keep control-specific code, infrastructure, tests, configuration, and media
  inside its control directory;
- avoid shared abstractions until multiple implemented controls need them;
- use synthetic data;
- include safe, policy-triggering, and dependency/control-failure scenarios;
- show the expected decision, governance action, and safe evidence;
- state what it proves and does not prove;
- include precise validation and cleanup instructions;
- fail closed when a mandatory control cannot be evaluated safely.

Several products may be composed in one demo, but every product must have one
specific, documented role in the control flow.

## Community-first demo design

Optimize controls for community learning. A core demo must be correct and safe
within its declared scope, but it does not need to implement every enterprise
concern. Prefer one small runnable control path over an enterprise reference
architecture.

Do not add infrastructure, frameworks, abstractions, or integrations solely for
completeness. Implement an advanced integration only when it adds a distinct
learning outcome; otherwise document it as optional further exploration with a
link to authoritative product documentation.

Every implemented control README must distinguish:

- the core demo that is actually implemented and tested;
- intentional simplifications made to keep it accessible;
- what the demo proves and does not prove;
- optional extensions and exploration paths for community contributors.

Intentional simplifications must never weaken the primary governance decision,
create an undocumented unsafe path, or be presented as production best practice.
When AGT, ACS, Foundry, or another Microsoft service already supplies a relevant
capability, keep the core demo small when appropriate and link to that capability
under `Further exploration`.

Each README must include a demo profile with learning level, estimated time,
primary decision, primary Microsoft capabilities, infrastructure requirements,
and AGT/ACS usage.

## Root README navigation

Treat the root `README.md` as the community landing page, not as a dump of the
entire planned catalog. When a control becomes `Implemented` or `Validated`:

- add it to `Recently added — runnable demos`, newest first;
- link directly to its README, Demo section, Demo scope, and `ASSESSMENT.md`;
- state one learning outcome, level, and estimated time;
- keep planned controls out of the runnable table;
- update status labels elsewhere in the root README so they do not conflict.

Keep this section compact. Do not add a row for documentation-only scaffolds or
empty planned control folders.

## Authority and enforcement

Never hide mandatory governance decisions in model prompts. Explicitly classify
each decision as deterministic policy, model-assisted evaluation, human
approval, configuration assessment, or monitoring/detection.

An agent may explain or orchestrate an authoritative decision, but it must not
override that decision, grant its own approval, remove a protection, or claim an
action succeeded without authoritative verification.

For sensitive or irreversible actions, bind approval to the exact action,
target, relevant state or version, policy decision, and expiry.

Use AGT and ACS when they provide the appropriate enforcement surface. Identify
the applicable ACS intervention point and preserve supported runtime semantics,
verdicts, fail-closed behavior, action identities, and content-safe telemetry.
Do not reproduce ACS concepts in a competing local specification. When AGT or
ACS is not used, document why it is not the correct control surface.

## Evidence

Every control defines a minimum evidence contract showing which control and
policy version ran, the decision and reason, the action taken, verification of
that action, timestamp, correlation identity, and accountable role.

Evidence and telemetry must not include raw PII, secrets, complete prompts,
sensitive content, approval tokens, or unnecessary tool arguments. Never claim
legal compliance, production readiness, completeness, fairness, or security
beyond what the demo actually establishes.

## Technology and currency

Use current authoritative Microsoft documentation, specifications, supported
SDK behavior, and official repositories as primary sources. Verify support
status before selecting an API, model, SDK, or preview feature. Prefer supported
GA capabilities when they satisfy the control. Record review dates, important
versions, preview dependencies, limitations, and authoritative references.

## Repository conventions

- Language: primarily Python, with the language best supported by the selected
  official capability allowed when justified.
- Authentication: prefer Microsoft Entra ID, managed identity, and least
  privilege. Never hardcode credentials or commit `.env` files.
- Structure: follow the current grouped `controls/` hierarchy and
  `docs/control-readme-template.md`.
- Tests: validate decisions, failure behavior, authority boundaries, evidence
  minimization, and governance-action verification.
- Infrastructure: keep resources owned by one control with that control; only
  genuinely reusable resources belong in shared infrastructure.
