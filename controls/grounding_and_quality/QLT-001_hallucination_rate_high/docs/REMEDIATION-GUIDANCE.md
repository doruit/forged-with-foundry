---
title: QLT-001 remediation guidance and why it stays out of scope
description: Where a Product Owner should look after a Quality review, and why this control does not automate any of it.
ms.date: 2026-09-25
---

## After a Quality review: where to actually improve groundedness

This control's own scope stops at **detecting** a hallucination-rate breach
for any fleet agent and notifying the Product Owner — it deliberately does
not change any agent, knowledge base, or retrieval pipeline itself (see
`README.md` "Control objective"). The Product Owner still needs a next step
once the Teams card arrives. `evaluator.py`'s own evidence deliberately stops
at the minimized rate/threshold/critical-item record — it does not carry an
evaluator's per-item `reason` or `properties.dimension_scores`, since those
can quote fragments of the actual response (see `README.md` "Evidence and
observability"'s data minimization rule). For root-cause diagnosis, a
reviewer opens the real evaluation results in the Foundry portal instead.
From there, root-cause remediation generally falls into one of these
directions, depending on what the diagnosis points to:

- **The source content is stale, incomplete, or missing** (the Regional and
  Contractor Teams' own scenario in this demo). Fix the content at its
  source and re-run to confirm the rate recovers. There is no single
  Microsoft tool for this — it is a knowledge-ownership and
  content-freshness process question; if this repository later implements a
  `data_and_knowledge` category control for knowledge/content freshness,
  cross-reference it here instead of duplicating the guidance.
- **The retrieval step is surfacing the wrong or insufficient context**, if
  an agent's tool is backed by real search rather than this control's
  simple fixed lookup. Tune retrieval relevance (hybrid search, semantic
  ranking, scoring profiles) per [RAG and generative AI — Azure AI
  Search](https://learn.microsoft.com/en-us/azure/search/retrieval-augmented-generation-overview)
  and the [classic RAG relevance-tuning
  tutorial](https://docs.azure.cn/en-us/search/tutorial-rag-build-solution-maximize-relevance),
  and re-evaluate with the [RAG groundedness/relevance
  evaluators](https://learn.microsoft.com/en-us/azure/ai-foundry/concepts/evaluation-evaluators/rag-evaluators?view=foundry-classic)
  to confirm the fix.
- **The model has good context but still answers ungrounded, or has weak
  instructions that permit speculation** (the Contractor Team's own scenario
  in this demo). Strengthen the system instructions — explicit "answer only
  from the tool result; say so if information is missing" framing, few-shot
  grounded/ungrounded examples — per general [Azure OpenAI prompt
  engineering
  guidance](https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/prompt-engineering),
  or let Microsoft's own [Prompt Optimizer
  (preview)](https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/prompt-optimizer)
  restructure the instructions automatically and re-evaluate before and
  after.
- **Systematic, ongoing improvement rather than a one-off fix.** [Agent
  Optimizer in Foundry Agent Service
  (preview)](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/agent-optimizer-overview)
  is built specifically to consume evaluation results like the ones this
  control already produces, generate ranked candidate prompt/skill changes,
  and show a before/after comparison with full diff, lineage, and rollback —
  a more systematic option than manually iterating on the instructions.
- **Inline mitigation for the specific response, not the underlying cause.**
  Azure AI Content Safety's groundedness detection includes an automatic
  **correction** feature that rewrites an ungrounded span to match the
  supplied grounding source before it reaches the user — see [Groundedness
  detection — Azure AI Content
  Safety](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/groundedness)
  (preview). This treats a symptom per response; it does not replace fixing
  the content or retrieval gap that caused it, and pairs naturally with
  `RUN-001`'s inline enforcement extension (see `README.md` "Further
  exploration") rather than with this control's own Continuous Evaluation
  path.

None of the above is implemented by this control — they are the documented,
cited next steps for whoever receives the Quality review, kept out of this
control's own bite-sized scope on purpose.

## Why this control does not automate remediation

It would be tempting to close the loop entirely — detect a breach and fix it
without a human — but that does not hold up once the three ways to
"automate" it are separated out:

1. **Inline correction of one response.** Azure AI Content Safety's
   groundedness detection can automatically rewrite an ungrounded span to
   match the grounding source already supplied (see "After a Quality review"
   above). This only works when a grounding source exists but was ignored or
   misused — it has nothing to correct against for the Regional and
   Contractor Teams' own scenario (an article removed or never populated),
   and it treats one response, not the recurring cause.
2. **Automatically rewriting the knowledge base.** Not viable as an
   unsupervised process: deciding what the correct, current organizational
   content should say is a human/business judgment, not a technical one.
   Having a model auto-generate "corrected" official content reintroduces
   the same hallucination risk this control exists to catch, one layer
   removed — an ungrounded fix for an ungrounded answer.
3. **Automatically containing exposure** (pausing an agent or falling back
   to a safe mode once a breach is confirmed) is the one form of automation
   that stays defensible, because it removes access rather than asserting a
   judgment. It is also explicitly out of this control's own scope — that is
   what an emergency-stop control (`AUT-004`, planned in this repository's
   `autonomy_and_human_oversight` category) is for, not a quality-monitoring
   control. The self-reported confidence and follow-up questions this
   control does display (see `README.md` "Overview") are a deliberately
   narrower, softer mechanism than any of these three — a nudge the user can
   act on, not an automated action this control takes on anyone's behalf.

This follows the same authority boundary this repository applies
everywhere: an agent, or an automated pipeline acting on its behalf, may
explain or orchestrate a decision, but must not grant its own approval or
claim an action succeeded without independent, human-accountable
verification. `PRI-002`, `PRI-003`, and `PRI-004` in this repository apply
the identical pattern for a different signal — a deterministic policy
detects the issue, but the actual remediating action stays behind an
explicit human or independently-verified approval boundary. Automatic
content remediation would break that boundary for a decision that is
squarely a human one.
