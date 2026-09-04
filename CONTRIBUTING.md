# Contributing

Forged with Foundry grows one bite-sized governance control demo at a time.
This guide covers how to propose and submit one.

## Before you write any code

Every new control starts with an assessment, not code. Copy
[docs/control-assessment-template.md](docs/control-assessment-template.md)
into the target control's folder as `ASSESSMENT.md` and complete it first.
The assessment must show what existing Microsoft capability (AGT, ACS,
Microsoft Foundry, Purview, Defender, Entra, Azure AI Content Safety/Language,
Azure Monitor, or another supported service) was considered, what is reused,
and the smallest genuine gap this control fills. See
[.github/copilot-instructions.md](.github/copilot-instructions.md) for the
full reuse-first rule and demo-format decision guide
(`GUIDED_EXERCISE` / `HYBRID_DEMO` / `DEPLOYABLE_DEMO`).

Open a draft pull request with just the `ASSESSMENT.md` if you'd like early
feedback before building the rest of the demo.

## Building the demo

Once the assessment is accepted:

1. Use [docs/control-readme-template.md](docs/control-readme-template.md) as
   the structure for the control's `README.md`.
2. Keep control-specific code, infrastructure, tests, and configuration
   inside that control's own folder — only genuinely shared resources belong
   in the root [infra/](infra).
3. Use synthetic data only. Never commit real personal data, credentials, or
   `.env` files (only `.env.example`).
4. Give the control a real, working cleanup action scoped to its own
   synthetic resources — never one that could delete the shared resource
   group or another control's data.
5. Add a plain-language "Real-life scenario" as the first thing in the
   README's Overview section.

## Testing

```bash
.venv/bin/python -m compileall -q src app.py tests
.venv/bin/python -m pytest -q tests
```

Also run the repository-wide structural checks before opening a pull request:

```bash
.venv/bin/python -m pytest -q tests/test_control_readme_structure.py
```

## Submitting a pull request

- Update the root [README.md](README.md)'s "Recently added — community demos"
  table in the same change that marks a control `Implemented` or `Validated`
  (newest first).
- Verify the full deploy path end to end (shared `infra/deploy.sh` first,
  then the control's own `infra/deploy.sh`, then the demo) before marking a
  control `Implemented` or `Validated`.
- Describe what the demo proves and does not prove — this repo is explicit
  about scope boundaries rather than overselling a small demo.

## Code of conduct

This project follows the [Code of Conduct](CODE_OF_CONDUCT.md). Report
concerns as described there.

## Security issues

Do not open a public issue for a security concern — see
[SECURITY.md](SECURITY.md).
