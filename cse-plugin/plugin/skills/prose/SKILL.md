---
name: prose
description: "Inspect scientific writing read-only. Use when acting as a manuscript review sub-agent, or checking clarity, banned language, revision meaning, a rejected draft, a report-like manuscript, or final cohesion. Routine wording or citation edits go to write; claim support to review."
metadata:
  cse-kind: "supporting"
  cse-family: "supporting"
  cse-tags: "writing-inspection"
  cse-routing:
    direct: [operating-model, scientific-writing, writing-editorial, BANNED]
    conditional: [manuscript-review, slide-decks]
---

# Inspect scientific prose

Read first: [operating-model](../../references/workflow/operating-model.md), [scientific-writing](../../references/workflow/scientific-writing.md), [writing-editorial](../../references/workflow/writing-editorial.md), [BANNED](../../BANNED.md).

Identify the exact paragraph, section, manuscript, report, reviewer response, or
original-and-revision pair and follow the [prose inspection procedure](../../references/workflow/writing-editorial.md#prose-inspection).
Check [editorial compliance](../../references/workflow/writing-editorial.md#editorial-compliance) against the applicable [standing decisions](../../references/workflow/writing-editorial.md#standing-editorial-decisions).
For manuscripts, apply [emphasis in proportion](../../references/workflow/scientific-writing.md#emphasis-in-proportion)
and the [display and caption principles](../../references/workflow/scientific-writing.md#shared-article-requirements).
Follow the [story-spine triggers](../../references/workflow/manuscript-review.md#story-spine-read) and use the
[manuscript structure review](../../references/workflow/manuscript-review.md#manuscript-structure-review)
and [internal referee procedure](../../references/workflow/manuscript-review.md#internal-referee-rounds)
when the assignment calls for them. Close manuscript review rounds with the
[storyline report](../../references/workflow/manuscript-review.md#storyline-report).

For an explicit final manuscript check, follow the
[final manuscript checkpoint](../../references/workflow/manuscript-review.md#final-manuscript-checkpoint).
When no routine finding remains, return `CSE prose is clear.` Prose does not edit.
Route corrections to `cse:write`, which may request the
[verification read](../../references/workflow/writing-editorial.md#routine-corrections).

At a deck's final checkpoint, inspect it read-only against [slide-decks](../../references/visualize/slide-decks.md) and the project's deck decisions.
