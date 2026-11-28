---
name: prose
description: "Inspect scientific writing read-only. Use when acting as a manuscript review sub-agent, or checking clarity, banned language, revision meaning, a rejected draft, a report-like manuscript, or final cohesion. Routine wording or citation edits go to write; claim support to review."
metadata:
  cse-kind: "supporting"
  cse-family: "supporting"
  cse-tags: "writing-inspection"
  cse-routing:
    direct: [scientific-writing, writing-editorial]
    conditional: [operating-model, BANNED, manuscript-review, slide-decks]
---

# Inspect scientific prose

Identify the exact paragraph, section, manuscript, report, reviewer response, or
original-and-revision pair. For a local edit or paragraph review, read only
[Revision fidelity](../../references/workflow/scientific-writing.md#revision-fidelity),
the applicable [standing editorial decisions](../../references/workflow/writing-editorial.md#standing-editorial-decisions),
and the passage under review.
For broader inspections, including drafts, rewrites, and structural reviews, read [operating-model](../../references/workflow/operating-model.md),
[scientific-writing](../../references/workflow/scientific-writing.md) in full,
[writing-editorial](../../references/workflow/writing-editorial.md), and [BANNED](../../BANNED.md).
Consult [BANNED](../../BANNED.md) for an explicit banned-language inspection.

Follow the [prose inspection procedure](../../references/workflow/writing-editorial.md#prose-inspection)
for the assigned scope.
Check [editorial compliance](../../references/workflow/writing-editorial.md#editorial-compliance) against the applicable [standing decisions](../../references/workflow/writing-editorial.md#standing-editorial-decisions).
For a whole manuscript, apply [emphasis in proportion](../../references/workflow/scientific-writing.md#emphasis-in-proportion)
and the [display and caption principles](../../references/workflow/scientific-writing.md#shared-article-requirements).
Follow the [story-spine triggers](../../references/workflow/manuscript-review.md#story-spine-read) and use the
[manuscript structure review](../../references/workflow/manuscript-review.md#manuscript-structure-review)
and [internal referee procedure](../../references/workflow/manuscript-review.md#internal-referee-rounds)
when the manuscript assignment calls for them.

For an explicit final manuscript check, follow the
[final manuscript checkpoint](../../references/workflow/manuscript-review.md#final-manuscript-checkpoint).
When no routine finding remains, return `CSE prose is clear.` Prose does not edit.
Route corrections to `cse:write`, which may request the
[verification read](../../references/workflow/writing-editorial.md#routine-corrections).

At a deck's final checkpoint, inspect it read-only against [slide-decks](../../references/visualize/slide-decks.md) and the project's deck decisions.
