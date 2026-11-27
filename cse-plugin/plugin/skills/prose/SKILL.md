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
For manuscripts, read for [emphasis in proportion](../../references/workflow/scientific-writing.md#emphasis-in-proportion)
and [display interpretation](../../references/workflow/scientific-writing.md#shared-article-requirements).
Apply the [story-spine triggers](../../references/workflow/manuscript-review.md#story-spine-read)
across revisions, including routine edits, and use the
[manuscript structure review](../../references/workflow/manuscript-review.md#manuscript-structure-review)
and [internal referee procedure](../../references/workflow/manuscript-review.md#internal-referee-rounds)
when the assignment calls for them.
When no routine finding remains, return `CSE prose is clear.` If the user asks
for corrections, route them to `cse:write`. Prose does not edit. Write may
request one verification inspection after its minimum effective change.

For an explicit final manuscript check, inspect the authoritative assembled
source and use the source-identity, whole-manuscript inspection, exact weak
links, and argument-spine checkpoint in
[manuscript review procedures](../../references/workflow/manuscript-review.md#final-manuscript-checkpoint). Return **Revise** with exact identifiers for stale
identity, missing coverage, or unresolved weak or broken relationships. The
routine clear message is not a final-check result. Report exact
[editorial violations](../../references/workflow/writing-editorial.md#editorial-compliance) and follow the shared
[final-check coordination](../../references/workflow/manuscript-review.md#final-manuscript-checkpoint).

At a deck's final checkpoint, inspect it read-only against [slide-decks](../../references/visualize/slide-decks.md) and the project's deck decisions.

For source, figure, and deck identifier advisories, follow the shared
[reader-facing identifier check](../../references/workflow/writing-editorial.md#reader-facing-identifiers).
