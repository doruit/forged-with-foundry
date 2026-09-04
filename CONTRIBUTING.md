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

If the control's folder doesn't exist yet, `scripts/scaffold_controls.py`
generates the `controls/<category-group>/<control-id>_<slug>/README.md`
skeleton for every catalog entry from the source PDF — useful when starting
a planned control that has no folder yet.

## Building the demo

Once the assessment is accepted:

1. Use [docs/control-readme-template.md](docs/control-readme-template.md) as
   the structure for the control's `README.md`.
2. Keep control-specific code, infrastructure, tests, and configuration
   inside that control's own folder — only genuinely shared resources belong
   in the root [infra/](infra).
3. Use synthetic data only. Never commit real personal data, credentials, or
   `.env` files (only `.env.example`).
4. If the control creates resources or state, give it a real, working cleanup
   action scoped to its own synthetic resources — never one that could delete
   the shared resource group or another control's data. For a guided exercise
   that creates no state, state that cleanup is not applicable.
5. Add a plain-language "Real-life scenario" as the first thing in the
   README's Overview section.

## Testing

For an executable control, create a repository-level virtual environment and
install that control's dependencies. Then run its checks from the control
directory:

```bash
# From the repository root; replace <control-path> with the selected control.
python3 -m venv .venv
.venv/bin/python -m pip install -c constraints.txt -r <control-path>/requirements.txt
cd <control-path>
../../../.venv/bin/python -m compileall -q src app.py tests
../../../.venv/bin/python -m pytest -q tests
```

For a guided exercise with no executable, validate the documented walkthrough,
expected decisions, evidence checks, and answer key instead.

Also run the repository-wide structural checks before opening a pull request:

```bash
python3 -m pytest -q tests/test_control_readme_structure.py
```

## Submitting a pull request

- Update the root [README.md](README.md)'s "Recently added — community demos"
  table in the same change that marks a control `Implemented` or `Validated`
  (newest first).
- Verify the complete path appropriate to the selected format before marking a
  control `Implemented` or `Validated`: the walkthrough and answer key for a
  guided exercise, every claimed executable path for a hybrid demo, or the
  shared infrastructure, control infrastructure, and runnable demo for a
  deployable demo.
- Describe what the demo proves and does not prove — this repo is explicit
  about scope boundaries rather than overselling a small demo.

## Code of conduct

This project follows the [Code of Conduct](CODE_OF_CONDUCT.md). Report
concerns as described there.

## Security issues

Do not open a public issue for a security concern — see
[SECURITY.md](SECURITY.md).
