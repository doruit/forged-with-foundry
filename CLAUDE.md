# Forged with Foundry — Claude Code guidance

This repository's authoring rules were written for GitHub Copilot but are not
Copilot-specific in content — they are plain Markdown and apply identically
here. Read them; do not restate or fork them:

- **[.github/copilot-instructions.md](.github/copilot-instructions.md)** —
  mission, capability-first composition rule, one-authoritative-path and
  complexity budget, mandatory pre-implementation assessment, demo format
  selection, actionable implementation paths, evidence rules, root README
  navigation rules. Read this in full before touching `controls/**`.
- **`.github/instructions/*.instructions.md`** — path-scoped rules (frontmatter
  `applyTo`), all currently scoped to `controls/**/*`:
  - `governance-controls.instructions.md` — control README/ASSESSMENT scope,
    diagram conventions, Model/Foundry role classification, release-gate
    requirements.
  - `fwf-governance-contract.instructions.md` — checklist for wiring a new
    control into the governance-contract schema/fixtures/policy layer. Read
    `docs/governance-contract.md` first, as it says to.
  - `screenshot-capture-workflow.instructions.md` — protocol for
    large browser-screenshot sessions (batch, checkpoint, mask at capture
    time).
  - `upstream-contributions.local.instructions.md` — how to surface upstream
    Microsoft product/SDK issues found while building a control; never submit
    externally without explicit user approval.
- **`.github/prompts/assess-governance-control.prompt.md`** — mirrored as the
  Claude Code skill `assess-governance-control` (see below); the mirror must
  stay consistent with this original if either changes.

## Before implementing any control

Never write control code or infrastructure before `ASSESSMENT.md` exists and
is complete. Copy `docs/control-assessment-template.md` into the control's
folder, or invoke the `assess-governance-control` skill. Check the relevant
category's own `ARCHITECTURE.md` (for example
`controls/value_adoption_and_finops/ARCHITECTURE.md`) for shared data streams
and known duplication risks before proposing a design — these living design
notes exist specifically so a new control doesn't quietly redefine or
duplicate territory another control already claims.

## Available Claude Code skills for this repo

- `assess-governance-control` — pre-implementation assessment workflow
  (`.claude/skills/assess-governance-control/SKILL.md`).
- `linkedin-post-writer` — drafts LinkedIn announcement posts for shipped
  controls; symlinked from `.github/skills/linkedin-post-writer/SKILL.md`.
  Drafts go under `content/linkedin/` (gitignored), `status: draft` until the
  user confirms.
- `markdown-doc-quality` — AI-slop / doc-quality checklist for `.md` changes;
  symlinked from `.github/skills/coding-standards/markdown-doc-quality/SKILL.md`.
  Apply this before finalizing any control README, ASSESSMENT, or docs change.

The `.claude/skills/*` entries for the two Copilot-authored skills are
symlinks, not copies — editing either the `.github/skills/...` source or the
`.claude/skills/...` symlink target edits the same file. Only
`assess-governance-control` is a real Claude-native file (the Copilot prompt
frontmatter shape isn't directly skill-loadable) and needs manual sync if the
`.prompt.md` original changes.

## Repository tooling

- `scripts/validate_governance_contract.py` — validates
  `.fwf/agents/<agent-id>/governance.yaml` against
  `schemas/governance-contract/v1alpha1/`.
- `scripts/generate_roadmap.py` — regenerates `docs/roadmap.md`. **Never
  hand-edit `docs/roadmap.md`** (it has a generated-file header).
- `scripts/scaffold_controls.py` — generates a planned control's
  `controls/<category>/<ID>_<slug>/README.md` skeleton from the source
  catalog PDF when the folder doesn't exist yet.
- `tests/test_governance_contract_consistency.py` — mechanically checks the
  governance-contract integration checklist items; run this before
  considering a control's contract integration complete.
- Per-control tests: `.venv/bin/python -m pytest controls/<category>/<ID>_*/tests -q`.

## Status tracking, kept in sync on every control-status change

Whenever a control's status becomes `Implemented` or `Validated` in the same
change:

1. Update the control's own README status line.
2. Update the category's `ARCHITECTURE.md` status table and revision log, if
   one exists for that category.
3. Add it to root `README.md`'s "Recently added — community demos" table.
4. Regenerate `docs/roadmap.md` via `scripts/generate_roadmap.py`.

## Confidentiality and screenshots

This is a public, external-facing OSS repository authored by a Capgemini
employee in a personal capacity — it uses only synthetic data and fictional
agents/tenants (for example `helpdesk-tier1-triage`,
`it-service-desk-manager@contoso.example`). Never introduce a real client
name, tenant, subscription ID, or credential. Follow the existing screenshot
convention: mask account/tenant chrome, webhook URLs, subscription/tenant
IDs, and connection strings at capture time, and add a `[Privacy note: ...]`
caption stating exactly what was excluded and what remains visible, as seen
throughout `controls/value_adoption_and_finops/VAL-001_kpi_underperformance/`.

## LinkedIn drafts

`content/linkedin/*.md` is gitignored (local-only marketing drafts). Draft
posts stay `status: draft` until the user explicitly confirms they're ready;
never mark one `published` or post it on the user's behalf.
