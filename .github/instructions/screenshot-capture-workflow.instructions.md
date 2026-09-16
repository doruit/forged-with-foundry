---
applyTo: "controls/**/*"
---

# Browser screenshot capture protocol (large sessions)

When a task requires capturing more than roughly 8-10 browser screenshots in
one conversation (for example, a step-by-step Copilot Studio, Azure Portal,
or similar UI walkthrough), each captured image is added to conversation
context and accumulates quickly. Follow this protocol to avoid exhausting the
context window mid-task.

1. **Save directly, don't re-display.** After each screenshot capture, write
   it straight to its final destination path in the repository. Do not view
   a screenshot you have already reviewed once, and do not re-attach a
   screenshot that was already captured earlier in the same turn or a prior
   turn.
2. **Batch by phase, checkpoint between phases.** Group screenshots into
   logical phases (for example: "create agent", "add tool/connection", "live
   test"). After finishing a phase, write a short session-memory checkpoint
   (files captured so far, their purpose, and what phase comes next) before
   starting the next phase, so a fresh conversation can resume without
   re-deriving anything.
3. **Verify pixel details programmatically, not visually.** Use `sips`/PIL
   (image size, pixel sampling for mask-boundary calibration) to confirm
   dimensions, crop boundaries, or mask placement. Reserve viewing an image
   for a final, minimal spot-check only when a programmatic check cannot
   answer the question.
4. **Mask sensitive UI chrome at capture time.** If a screenshot will show
   real personal names, tenant names, or internal URLs, crop/mask it
   immediately after capture, in the same tool-call sequence, rather than
   deferring cleanup to a later pass across many already-committed files.
5. **Proactively flag context growth.** Once roughly 15-20 screenshots have
   been captured in a single conversation, tell the user explicitly and
   recommend starting a fresh conversation for the remaining screenshots,
   after writing a complete session-memory checkpoint. Do not wait until the
   context window is actually exhausted to raise this.
6. **A fresh conversation cannot be started by the agent.** Only the user can
   open a new chat session. The agent's role is limited to keeping
   session and repository memory current enough that a new conversation can
   resume immediately from a short prompt such as "continue the CR-001 A2A
   screenshot walkthrough."
