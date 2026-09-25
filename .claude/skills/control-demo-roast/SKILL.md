---
name: control-demo-roast
description: "Adversarial pre-announcement review of a Forged with Foundry control demo -- run before linkedin-post-writer, not instead of it -- to catch overclaiming, unproven mechanisms, and stale estimates that would embarrass the team once a technical community actually tries the demo"
license: MIT
user-invocable: true
metadata:
  authors: "Douwe van de Ruit"
  spec_version: "1.0"
  last_updated: "2026-09-25"
---

# Control Demo Roast Skill

## Overview

A control can pass every automated test, satisfy `markdown-doc-quality`'s
checklist, and still not deserve a public announcement, because none of
that checks whether the thing being announced actually does what the
announcement will claim. This skill is a deliberately adversarial, skeptical
pass over one control's full state (README, ASSESSMENT, code, tests, and
what was actually run live) run **before** `linkedin-post-writer` drafts
anything, and before a maintainer marks a control `Implemented`/`Validated`
in a change intended to be announced. Its job is to find the exact
objection a sharp member of the tech community would raise within the first
five minutes of actually trying the demo, and surface it now instead of in
public.

This complements `markdown-doc-quality` rather than replacing it:
`markdown-doc-quality` catches writing-quality problems (hedging,
contradictions, missing evidence) in the prose itself. This skill catches a
different class of problem: prose that is well-written, internally
consistent, and passes every check, but describes a system whose central
claim has not actually been observed to hold. Apply both; a control can
fail this skill's checklist while passing every item in that one.

## When to use

- Before drafting a `linkedin-post-writer` announcement for any control.
- Before changing a control's `README.md` Status line to `Implemented` or
  `Validated` in a change that will be publicized.
- When a user asks to "roast," "sanity-check," or "review before announcing"
  a control demo.
- Not needed for a routine internal change that isn't headed toward a
  public announcement or a status change.

## The checklist

Work through every item against the control's actual current state --
README, ASSESSMENT.md, the real code, the real tests, and what was actually
run live this session -- not against what the control was designed to do.
Cite the exact file, section, or line each finding comes from; a finding
with no location is not actionable.

#### 1. Status vs. observed reality

Does `Implemented`/`Validated` describe what has actually been *observed
working*, or only what has been coded, unit-tested, and designed to work?
Find the control's own authoritative signal (the thing its Control contract
names as "Evidence / source") and ask: has this specific signal, from the
specific real service call the control depends on, ever actually been
observed producing its real output in a live run -- not a mocked, stubbed,
or synthetic substitute? If the demo has only ever produced the *fail-closed*
or *cannot-evaluate* branch of its own decision logic in every real run to
date, that is a specific, nameable gap: the control's core mechanism is
unproven, not merely "not yet exhaustively documented." State this
plainly and do not let confident prose elsewhere in the README soften it.

#### 2. Self-fulfilling or trivial proof

When the demo's evidence includes a deliberately misconfigured or
lower-quality component "catching" a problem, ask what was actually proven:
that the *monitoring/detection mechanism* caught a real, independently-scored
issue, or only that a component built to misbehave, in fact misbehaves. The
second is not evidence the control's actual detection machinery works --
it is evidence the demo's synthetic fixture is internally consistent. Name
this distinction explicitly when the "breach" scenario's detection came from
construction (the reviewer already knows which component will fail) rather
than from the control's own authoritative signal actually flagging it
independently.

#### 3. Unsubstantiated causal or outcome claims

Flag any claim that a mechanism "improves," "raises," "reduces," or "heals"
some real-world outcome over time, even when hedged ("can help," "may
raise"), when no experiment, measurement, or before/after comparison in the
same control backs the causal claim. A plausible-sounding UX idea (for
example, showing a self-reported confidence score to a user) is not the
same as a demonstrated mechanism, and confident framing ("a self-healing
mechanism") should not outrun what was actually measured. Recommend either
softening the claim to what is actually true (a hypothesis, a design
intent) or citing the actual evidence if it exists.

#### 4. Complexity and time-estimate drift

Compare the README's stated `Learning level` and `Estimated time` against
the *current* actual complexity: count real IAM role assignments, external
resources, undocumented prerequisites, and any external dependency with
unknown or open-ended latency (an async service that has never yet returned
its result, RBAC propagation delays hit during the same session's live
testing, etc.). An estimate written when the design was simpler and never
revisited after it grew is a stale claim, not a current one. Recommend a
revised, honest estimate or an explicit caveat about the open-ended
dependency.

#### 5. Tone risk when citing an upstream gap

When the control's writeup includes "found a bug in the vendor SDK" or "the
vendor's documentation has a gap," check whether the overall narrative could
read as blaming the platform for the demo's own core mechanism not working,
especially when that mechanism is still unproven (see item 1). A real,
independently-reproduced upstream finding is worth citing professionally and
factually; it reads very differently next to an honest "and our own
control doesn't fully work yet either" than next to confident
`Implemented` framing that omits it. Recommend adjusting emphasis, not
removing a legitimate finding.

#### 6. Test coverage vs. what a first-time user will actually witness

Check whether any automated test pins down the *specific outcome* a person
running the documented demo commands today will actually see -- not just
clean unit tests of internal functions with synthetic inputs. If the real,
current, only-ever-observed outcome of running the demo is a specific
decision (for example, always `cannot_evaluate`), and no test asserts that
outcome against the real integration point (not a mocked one), flag this as
a coverage gap distinct from "tests exist and pass": the tests do not
protect the one behavior most likely to surprise a new user.

#### 7. Borrowed assumptions never confirmed against the real integration

Flag any data shape, schema, or contract "confirmed" against a *different*
system, mode, or code path (a legacy mechanism, a different API, an earlier
design) and then assumed, without confirmation, to hold for the *new*
mechanism the control now claims to use. If the new integration's real
output has never actually been observed, say so explicitly rather than
letting a schema borrowed from elsewhere read as verified.

#### 8. Stale or unverified external citations

For every external link or issue reference presented as current evidence
(a GitHub issue, a vendor doc), confirm it was actually checked recently
enough to still be accurate -- not simply carried forward from when it was
first found. A citation whose status (open/closed/merged) has not been
re-verified in the same review is a live risk for a public post.

## Severity and output

Group findings as **Blocking** (would make the announcement actively
misleading -- typically items 1, 2, and 3), **Should fix before announcing**
(items 4, 5, 8), and **Worth tracking** (items 6, 7, if not independently
blocking). For each finding: cite the file/section, state the concrete
scenario in which a reader or user would notice the gap, and give one
specific, actionable fix (soften a claim, add a caveat, write a missing
test, revise an estimate) rather than a vague "consider clarifying."

Do not treat "the test suite passes" or "the doc-quality skill found
nothing" as evidence a control is ready to announce -- both are necessary,
neither is sufficient, and this skill exists specifically to check what
they don't.

## Troubleshooting

| Symptom | Check |
|---|---|
| Every finding feels the same as `markdown-doc-quality`'s | You are re-checking prose quality, not the underlying claim. Ask "has this actually been observed working," not "is this well-written." |
| No findings at all | Confirm you checked the control's actual authoritative signal against real, live-observed output, not against its test suite or design intent. A clean unit-test suite is not evidence here. |
| Unsure whether a finding is Blocking | Ask: would a technical reader who tries the demo within an hour of the announcement notice this gap themselves? If yes, it is Blocking. |

## Contributing

Checklist items belong in this file and must stay portable across
controls -- describe patterns by their behavior, not by a specific control
ID. Add a new item only after finding it live during an actual review, and
name the control and date in the commit/PR description, not in this file
itself (the checklist stays generic; specific findings belong in the
control's own docs).
