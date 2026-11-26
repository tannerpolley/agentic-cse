---
name: write
description: "Write scientific manuscripts, reports, and captions from accepted evidence. Use when asked for \"manuscript revision\", \"revise the paper\", a rejected-draft rewrite, restructuring, or wording/citation edits. Read-only critique goes to prose; compilation to latex or quarto."
metadata:
  cse-kind: "workflow"
  cse-family: "workflow"
  cse-order: "08"
  cse-tags: "workflow"
  cse-routing:
    direct: [operating-model, scientific-method]
    conditional: [scientific-writing, numerical-testing]
---

# Write papers

Read first: [operating-model](../../references/workflow/operating-model.md), [scientific-method](../../references/workflow/scientific-method.md).

Activate [scientific-writing](../../references/workflow/scientific-writing.md) for project writing rules and retained paths.
Before manuscript edits, follow its [standing-decision read/update protocol](../../references/workflow/scientific-writing.md#standing-editorial-decisions).
Use its manuscript structure review before a new or rejected manuscript, a journal retarget, or a material restructure.
Use the committed bibliography snapshot read-only; an approved refresh belongs
to CSE source after the Zotero capability is checked.

Inspect the accepted question, formulation, methods, evidence, notebook,
sources, audience, and intended endpoint. Build one supported argument from
cited sources, equations, retained results, uncertainty, and limitations.
A limitation states a physical finding or the tested domain. Write a numerical
non-result (a refused, unfinished, or unconverged calculation, or a result
labelled provisional for that reason) only when its record shows it met
[fix before a negative disposition](../../references/workflow/failure-triage.md#fix-before-a-negative-disposition);
otherwise return it to the investigator as a blocker with its record locator
and leave that sentence unwritten.
Keep verification distinct from physical validation, follow project writing
rules, and remove internal workflow or repository language from scientific
prose. Check terminology and banned language on every durable edit: before
handing back, run `python3 <plugin>/scripts/workflow/check_prose.py --root <project> <sources>`
on the draft, where `<plugin>` is the directory holding `skills/`.

Draft or restructure a manuscript from the [argument](../../references/workflow/scientific-writing.md#argument) principles, the [structure](../../references/visualize/latex-article-profiles.md#structure), and the [skeletons by paper type](../../references/visualize/latex-article-profiles.md#skeletons-by-paper-type).
Report numerical work in [proportion](../../references/workflow/numerical-testing.md#fitness-for-purpose).
Write Methods for [methods reproducibility](../../references/workflow/scientific-writing.md#methods-reproducibility),
notation and numbers by [equations, quantities, and units](../../references/workflow/scientific-writing.md#equations-quantities-and-units),
availability statements by [data, code, and software](../../references/workflow/scientific-writing.md#data-code-and-software),
displays and captions by the [shared article requirements](../../references/visualize/latex-article-profiles.md#shared-article-requirements),
and referee responses and cover letters by [revision responses](../../references/workflow/scientific-writing.md#revision-responses-and-cover-letters).

Routine wording, citations, formatting, and local clarity edits remain here;
rendering does not require a Prose cohesion inspection. Apply the
minimal-intervention and fidelity rules in [scientific-writing](../../references/workflow/scientific-writing.md): change only
diagnosed spans, leave clear prose unchanged, invent no specificity, preserve
supported content, and perform one verification read. Route explicit wording,
AI-pattern, comparison, or final manuscript checks to `cse:prose`. A material
change to the central claims, abstract, conclusion, section order, or argument
spine makes the prior final inspection stale; inspect the updated argument at
the next final checkpoint.

Immediately before using a reviewed notebook in manuscript work, obtain native
investigator confirmation bound to the exact notebook commit, intended use,
and limitations. Ask about each numerical non-result in that notebook as its
own item, separate from the limitations. Record one plain sentence stating that the investigator
promoted that commit for that use subject to those limitations. Do not infer
promotion from Review Pass and do not create a status file or decision record.

After checking the renderer capability, use the selected `cse:latex`,
`cse:quarto`, `cse:beamer`, `cse:tikz`,
or `cse:plot` tool for rendering.
Synchronize a bibliography only through `cse:zotero` with its
approval gate, never by hand.
If rendering or source refresh is unavailable, retain accepted prose and report
the exact missing capability; neither becomes a hidden workflow gate.

For source, figure, and deck identifier advisories, follow the shared
[reader-facing identifier check](../../references/workflow/scientific-writing.md#reader-facing-identifiers).
