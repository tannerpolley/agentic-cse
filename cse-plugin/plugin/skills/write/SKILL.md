---
name: write
description: "Write scientific manuscripts, reports, and captions from accepted evidence. Use when acting as a writer sub-agent, or asked for \"manuscript revision\", \"revise the paper\", a rejected-draft rewrite, restructuring, or wording/citation edits. Critique goes to prose; compilation to latex or quarto."
metadata:
  cse-kind: "workflow"
  cse-family: "workflow"
  cse-order: "08"
  cse-tags: "workflow"
  cse-routing:
    direct: [operating-model, scientific-method, scientific-writing, writing-editorial]
    conditional: [manuscript-review, latex-article-profiles, failure-triage]
---

# Write papers

## Start

Read [operating-model](../../references/workflow/operating-model.md),
[scientific-method](../../references/workflow/scientific-method.md), and the
[scientific writing principles](../../references/workflow/scientific-writing.md)
in full. Follow the [project prose authorities](../../references/workflow/writing-editorial.md#project-prose-authorities)
and, before manuscript edits, the [standing editorial decisions procedure](../../references/workflow/writing-editorial.md#standing-editorial-decisions).
For manuscripts, use the triggers in [manuscript structure review](../../references/workflow/manuscript-review.md#manuscript-structure-review).
For an internal referee round, use the [brief, triage, and reporting procedure](../../references/workflow/manuscript-review.md#internal-referee-rounds).
For manuscript citations, use the [bibliography snapshot protocol](../../references/workflow/manuscript-review.md#bibliography-snapshot).

Inspect the accepted question, formulation, methods, evidence, retained results,
sources, audience, and intended endpoint. Before using any retained result, follow the
[investigator promotion procedure](../../references/workflow/operating-model.md#continuation-and-investigator-promotion).

**Complete when** the principles are read, the applicable editorial directions
and accepted evidence are identified, and the structure plan is accepted for
work that needs structure review.

## Draft

Draft from the accepted evidence using the writing principles. Apply
[verification, validation, and uncertainty](../../references/workflow/scientific-method.md#verification-validation-and-uncertainty).
Before writing about a numerical non-result, apply
[fix before a negative disposition](../../references/workflow/failure-triage.md#fix-before-a-negative-disposition).
If the record cannot support the disposition, return its locator as a blocker and
leave that sentence unwritten.

For routine wording, citation, formatting, and local clarity edits, follow
[routine corrections](../../references/workflow/writing-editorial.md#routine-corrections).
For other revisions, apply [Fixing a review finding](../../references/workflow/scientific-writing.md#fixing-a-review-finding)
and keep [emphasis in proportion](../../references/workflow/scientific-writing.md#emphasis-in-proportion).
When editing LaTeX manuscript source, use [manuscript source organization](../../references/visualize/latex-article-profiles.md#manuscript-writing-and-source-organization).

**Complete when** the edited passages and displays support the intended claim
within its tested domain, and any unresolved numerical non-result is reported
with its record locator.

## Finish

For any durable edit, follow the [source scan and advisory procedure](../../references/workflow/writing-editorial.md#reader-facing-identifiers).
For a manuscript or report draft or revision, check renderer
capability, render with the selected `cse:latex` or `cse:quarto`, inspect the
pages, then route the final read to `cse:prose`. Use `cse:beamer`, `cse:tikz`,
or `cse:plot` for their respective outputs. Route explicit wording, AI-pattern,
comparison, or final manuscript checks to `cse:prose`.

Apply the [story-spine triggers](../../references/workflow/manuscript-review.md#story-spine-read)
to manuscript revisions. For a rewrite that used structure
review or a round that triggers the post-rewrite pair, route the Prose read
through the reader-story reviewer in [post-rewrite review](../../references/workflow/manuscript-review.md#after-the-rewrite).
For a requested final check, submission, or named publication handoff, use
the [final manuscript checkpoint](../../references/workflow/manuscript-review.md#final-manuscript-checkpoint).
For a manuscript review round, hand off the assembled draft to the applicable reviewers for the
[storyline report](../../references/workflow/manuscript-review.md#storyline-report).
If rendering or source refresh is unavailable, retain accepted prose and report
the exact missing capability.

**Complete when** the source check and applicable render, page inspection,
and Prose read are accounted for, with any missing capability or unresolved
finding reported.
