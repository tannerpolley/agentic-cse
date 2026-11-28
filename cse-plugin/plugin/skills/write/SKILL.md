---
name: write
description: "Write scientific manuscripts, reports, and captions from accepted evidence. Use when acting as a writer sub-agent or asked to draft, rewrite, restructure, or edit scientific wording or citations. Route critique to prose and compilation to latex or quarto."
metadata:
  cse-kind: "workflow"
  cse-family: "workflow"
  cse-order: "08"
  cse-tags: "workflow"
  cse-routing:
    direct: [scientific-writing, writing-editorial]
    conditional: [operating-model, scientific-method, manuscript-review, latex-article-profiles, failure-triage]
---

# Write papers

## Start

For a local edit that leaves the argument intact, read only
[Revision fidelity](../../references/workflow/scientific-writing.md#revision-fidelity),
the applicable [standing editorial decisions](../../references/workflow/writing-editorial.md#standing-editorial-decisions),
and the passage being edited. Follow [routine corrections](../../references/workflow/writing-editorial.md#routine-corrections),
then go to [Finish](#finish).

For drafts, rewrites, and structural work, read [operating-model](../../references/workflow/operating-model.md),
[scientific-method](../../references/workflow/scientific-method.md), and
[scientific writing principles](../../references/workflow/scientific-writing.md) in full.
Follow the [project prose authorities](../../references/workflow/writing-editorial.md#project-prose-authorities)
and the applicable standing editorial decisions.
For manuscripts, follow [structure review](../../references/workflow/manuscript-review.md#manuscript-structure-review)
and use the [story-spine triggers](../../references/workflow/manuscript-review.md#story-spine-read)
to select reviews for revisions.
For an internal referee round, use the [brief, triage, and reporting procedure](../../references/workflow/manuscript-review.md#internal-referee-rounds).

Inspect the accepted question, formulation, methods, evidence, retained results,
sources, audience, and intended endpoint. Before using any retained result, follow the
[investigator promotion procedure](../../references/workflow/operating-model.md#continuation-and-investigator-promotion).

**Complete when** the applicable guidance is read, the editorial directions
and accepted evidence are identified, and the structure plan is accepted for
work that needs structure review.

## Draft

Draft from the accepted evidence using the writing principles. Apply
[verification, validation, and uncertainty](../../references/workflow/scientific-method.md#verification-validation-and-uncertainty).
Before writing about a numerical non-result, apply
[fix before a negative disposition](../../references/workflow/failure-triage.md#fix-before-a-negative-disposition).
If the record cannot support the disposition, return its locator as a blocker and
leave that sentence unwritten.

For revisions beyond routine corrections, apply [Fixing a review finding](../../references/workflow/scientific-writing.md#fixing-a-review-finding)
and keep [emphasis in proportion](../../references/workflow/scientific-writing.md#emphasis-in-proportion).
When editing LaTeX manuscript source, use [manuscript source organization](../../references/visualize/latex-article-profiles.md#manuscript-writing-and-source-organization).

**Complete when** the edited passages and displays support the intended claim
within its tested domain, and any unresolved numerical non-result is reported
with its record locator.

## Finish

For manuscript citations, apply the [bibliography snapshot protocol](../../references/workflow/manuscript-review.md#bibliography-snapshot).
For any durable edit, run
`python3 <plugin>/scripts/workflow/check_prose.py --root <project> <sources>`
and handle its advisories as the [source scan procedure](../../references/workflow/writing-editorial.md#reader-facing-identifiers) says.

For a routine edit without a final checkpoint, verify the changed passage and
run the project build only when the change affects rendering.

For a draft, rewrite, or endpoint named by the [final manuscript checkpoint](../../references/workflow/manuscript-review.md#final-manuscript-checkpoint),
check renderer capability, render the whole document, and inspect the pages.
Use `cse:latex` or `cse:quarto` for manuscript and report rendering, and
`cse:beamer`, `cse:tikz`, or `cse:plot` for their respective outputs. When the
[post-rewrite pair](../../references/workflow/manuscript-review.md#after-the-rewrite)
applies, hand off the assembled draft to the pair. Otherwise route the final
read to `cse:prose`. For manuscript review rounds, hand reviewer findings to
the lead for the [storyline report](../../references/workflow/manuscript-review.md#storyline-report).
If rendering or source refresh is unavailable, retain accepted prose and report
the exact missing capability.

**Complete when** the source check and the applicable finish path are
accounted for, with any missing capability or unresolved finding reported.
