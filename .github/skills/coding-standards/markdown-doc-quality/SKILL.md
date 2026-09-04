---
name: markdown-doc-quality
description: "Detects AI-slop patterns in Markdown documentation: heading/body contradictions, unverified external claims, hedging filler, missing evidence examples, and inconsistent terminology across .md files"
license: MIT
user-invocable: false
metadata:
  authors: "Douwe van de Ruit"
  spec_version: "1.0"
  last_updated: "2026-09-04"
---

# Markdown Documentation Quality Skill

## Overview

Catches low-quality, generic, or unverified AI-generated writing patterns in
Markdown documentation (READMEs, control docs, ADRs, assessments) that read
as authoritative but are hollow, self-contradictory, repetitive, or
factually unverified. This skill is loaded for any `.md` change.

## Core Checklist

#### 1. Heading and body agreement

* A section's opening sentence should support its heading's claim, not
  contradict or hedge it. A "What this proves" section whose first bullet
  opens with a negation reads as if it disproves itself; lead with the
  positive claim of authority or ownership before any negation.
* Do not open a "why / what / how" section with an unrelated caveat before
  answering the question the heading asks.

#### 2. Repeated boilerplate that hides a real difference

* Flag identical or near-identical phrasing repeated verbatim across many
  files or sections when it papers over a difference the reader should see,
  such as inconsistent role names, or a conclusion that should vary by
  context but does not.
* Flag a house tagline or slogan copy-pasted onto content whose actual
  mechanism differs from what the slogan describes.

#### 3. Unverified external claims

* A citation to an external spec, ADR, API, or library capability must
  reflect its current state (accepted, proposed, deprecated), not just its
  existence. Flag a citation of a proposed or draft design presented as if
  it were shipped and usable today.
* Flag a specific capability name (function, field, endpoint, flag)
  attributed to an external system without evidence that system's current
  source or docs were actually read in the same change.

#### 4. Hedging and vague filler

* Flag "it's worth noting", "simply", "easily", "robust", "powerful",
  "seamless", and similar filler that adds no verifiable information.
* Flag meta-commentary about the document itself, such as "this section
  explains..." or "this document will show...".

#### 5. Unsupported claims of proof

* A "what this proves" or "what this demonstrates" section must list only
  claims the reader can independently verify from the artifact (code, test,
  screenshot, log) in the same change. Flag a claim with no accompanying
  evidence path.
* Flag a strong "proves" claim with no adjacent "does not prove" or
  limitations statement.

#### 6. Missing example evidence

* Flag a description of a data or evidence payload ("emits metadata
  containing X, Y, Z") with no accompanying concrete example (JSON, log
  line, screenshot) anywhere in the file.

#### 7. Visual and structural consistency

* Flag a diagram (Mermaid or otherwise) that uses color or shape coding
  with no legend or text explanation of what the coding means.
* Flag inconsistent terminology for the same role or actor across sibling
  documents in the same collection, with no note reconciling the two terms.

#### 8. Numeric and asset accuracy

* Flag a declared image width or dimension attribute that does not match
  the actual asset's real dimensions.
* Flag a count, date, or status claim (for example, "X of Y implemented")
  that is not verified against the current repository state in the same
  change.

## Severity Rubric

| Severity | Definition                                                                                                          |
|----------|----------------------------------------------------------------------------------------------------------------------|
| High     | An unverified external technical claim presented as fact, or a numeric/status claim contradicted by the current repository state |
| Medium   | A heading/body contradiction, a missing diagram legend, a missing limitations statement, or inconsistent terminology |
| Low      | Hedging language, filler words, meta-commentary, or a missing example payload                                        |

## Troubleshooting

| Symptom                | Check                                                                                                     |
|-------------------------|-------------------------------------------------------------------------------------------------------------|
| Skill not loaded        | Confirm the diff contains `.md` files. The agent matches skills against changed file extensions.            |
| No findings generated   | Verify the `Skills Loaded` footer lists `markdown-doc-quality`. If listed with no findings, the diff already satisfies the checklist. |
| Too many low-severity findings | Filter the review to Medium and High only when triaging a large batch of documentation changes.       |

## Contributing

* Checklist items belong in this file. Each bullet is a single, actionable
  check an agent or reviewer can apply to a diff. Keep bullets concise and
  code-free.
* Before adding a new checklist item, confirm it does not duplicate an
  existing bullet. Place it in the section matching its primary concern.
* Checklist items must be portable across repositories. Describe patterns
  by their behavior, not by specific file or control names.

---

*Authored for Forged with Foundry to make the documentation-quality issues
found during manual review sessions repeatable and skill-backed rather than
ad hoc.*
