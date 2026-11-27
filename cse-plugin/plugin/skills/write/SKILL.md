---
name: write
description: "Write scientific manuscripts, reports, and captions from accepted evidence. Use when acting as a writer sub-agent, or asked for \"manuscript revision\", \"revise the paper\", a rejected-draft rewrite, restructuring, or wording/citation edits. Critique goes to prose; compilation to latex or quarto."
metadata:
  cse-kind: "workflow"
  cse-family: "workflow"
  cse-order: "08"
  cse-tags: "workflow"
  cse-routing:
    direct: [operating-model, scientific-method, scientific-writing]
    conditional: [writing-editorial, manuscript-review, latex-article-profiles, failure-triage]
---

# Write papers

## Start

Read [operating-model](../../references/workflow/operating-model.md),
[scientific-method](../../references/workflow/scientific-method.md), and the
[scientific writing principles](../../references/workflow/scientific-writing.md)
in full. Follow the [project prose authorities](../../references/workflow/writing-editorial.md#project-prose-authorities)
and, before manuscript edits, the [standing editorial decisions procedure](../../references/workflow/writing-editorial.md#standing-editorial-decisions).
For a new or rejected manuscript, journal retarget, or material restructure,
follow [manuscript structure review](../../references/workflow/manuscript-review.md#manuscript-structure-review).
For manuscript citations, use the [bibliography snapshot protocol](../../references/workflow/manuscript-review.md#bibliography-snapshot).

Inspect the accepted question, formulation, methods, evidence, retained results,
sources, audience, and intended endpoint. Before relying on reviewed results, follow the
[investigator promotion procedure](../../references/workflow/operating-model.md#continuation-and-investigator-promotion).

**Complete when** the principles are read, the applicable editorial directions
and accepted evidence are identified, and the structure plan is accepted for
work that needs structure review.

## Draft

Build one supported argument from the accepted evidence using the writing
principles. Keep numerical verification distinct from physical validation.
A limitation states a physical finding or the tested domain. Write a numerical
non-result (a refused, unfinished, or unconverged calculation, or a result
labelled provisional for that reason) only when its record shows it met
[fix before a negative disposition](../../references/workflow/failure-triage.md#fix-before-a-negative-disposition).
Otherwise, return its record locator to the investigator as a blocker and
leave that sentence unwritten.

For routine wording, citation, formatting, and local clarity edits, follow
[routine corrections](../../references/workflow/writing-editorial.md#routine-corrections)
and preserve [revision fidelity](../../references/workflow/scientific-writing.md#scientific-prose).
When editing LaTeX manuscript source, use [manuscript source organization](../../references/visualize/latex-article-profiles.md#manuscript-writing-and-source-organization).

**Complete when** the edited passages and displays support the intended claim
within its tested domain, and any unresolved numerical non-result is reported
with its record locator.

## Finish

For any durable edit, run
`python3 <plugin>/scripts/workflow/check_prose.py --root <project> <sources>`,
where `<plugin>` is the directory holding `skills/`. Use the printed reference
for each advisory. For a manuscript or report draft or revision, check renderer
capability, render with the selected `cse:latex` or `cse:quarto`, inspect the
pages, then route the final read to `cse:prose`. Use `cse:beamer`, `cse:tikz`,
or `cse:plot` for their respective outputs. Route explicit wording, AI-pattern,
comparison, or final manuscript checks to `cse:prose`. Routine wording,
citation, formatting, and local clarity edits need no cohesion inspection.

For a rewrite that used structure review, the reader-story reviewer performs that
Prose read in the [post-rewrite review](../../references/workflow/manuscript-review.md#after-the-rewrite).
For a requested final check, submission, or named publication handoff, use
[manuscript reference coverage](../../references/workflow/manuscript-review.md#manuscript-reference-coverage)
and the [final manuscript checkpoint](../../references/workflow/manuscript-review.md#final-manuscript-checkpoint).
If rendering or source refresh is unavailable, retain accepted prose and report
the exact missing capability.

**Complete when** the source check and applicable render, page inspection,
and Prose read are accounted for, with any missing capability or unresolved
finding reported.
