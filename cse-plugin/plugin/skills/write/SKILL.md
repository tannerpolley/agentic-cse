---
name: write
description: "CSE Execute and deliver — Turn accepted scientific evidence into a manuscript, report, appendix, caption, or equation narrative."
metadata:
  cse-kind: "workflow"
  cse-family: "workflow"
  cse-order: "08"
  cse-tags: "workflow"
  cse-routing:
    direct: [operating-model, scientific-method]
    conditional: [scientific-projects]
---

# Write papers

Activate `scientific-projects` for project writing rules and retained paths.
Use the committed bibliography snapshot read-only; an approved refresh belongs
to CSE source after the Zotero capability is checked.

Inspect the accepted question, formulation, methods, evidence, notebook,
sources, audience, and intended endpoint. Build one supported argument from
cited sources, equations, retained results, uncertainty, and limitations.
Keep verification distinct from physical validation, follow project writing
rules, and remove internal workflow or repository language from scientific
prose. Check terminology and banned language on every durable edit.

Routine wording, citations, formatting, and local clarity edits remain here;
rendering does not require a Prose cohesion inspection. Apply the
minimal-intervention and fidelity rules in `scientific-projects`: change only
diagnosed spans, leave clear prose unchanged, invent no specificity, preserve
supported content, and perform one verification read. Route explicit wording,
AI-pattern, comparison, or final manuscript checks to `cse:prose`. A material
change to the central claims, abstract, conclusion, section order, or argument
spine makes the prior final inspection stale; inspect the updated argument at
the next final checkpoint.

Immediately before using a reviewed notebook in manuscript work, obtain native
investigator confirmation bound to the exact notebook commit, intended use,
and limitations. Record one plain sentence stating that the investigator
promoted that commit for that use subject to those limitations. Do not infer
promotion from Review Pass and do not create a status file or decision record.

After checking the renderer capability, use the selected `cse:latex`,
`cse:quarto`, `cse:beamer`, `cse:tikz`,
`cse:pgfplots`, or `cse:plot` tool for rendering.
Synchronize a bibliography only through `cse:zotero` with its
approval gate, never by hand.
If rendering or source refresh is unavailable, retain accepted prose and report
the exact missing capability; neither becomes a hidden workflow gate.
