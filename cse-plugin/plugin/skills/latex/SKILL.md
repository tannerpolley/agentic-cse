---
name: latex
description: "Compile and check scientific LaTeX PDFs. Use when building a paper PDF, fixing manuscript layout or overfull boxes, or debugging LaTeX compilation. Route prose to write, slides to beamer, .qmd to quarto, and native figures to tikz."
metadata:
  cse-kind: "tool"
  cse-family: "visualize"
  cse-tags: "quarto-pipeline, latex-toolbox"
  cse-routing:
    direct: [rendering-guide]
    conditional: [latex-packages, latex-layout-and-qa, latex-article-profiles, scientific-writing, manuscript-review, quarto-execution, latex-figures]
---

# LaTeX document workflow

Read [rendering-guide](../../references/visualize/rendering-guide.md).
Activate [latex-packages](../../references/visualize/latex-packages.md) when
choosing or debugging packages.

Inherit core scientific, project, and
language decisions.

Activate [latex-layout-and-qa](../../references/visualize/latex-layout-and-qa.md) for layout defects, [latex-article-profiles](../../references/visualize/latex-article-profiles.md)
for a scientific article,
and [quarto-execution](../../references/visualize/quarto-execution.md) for a Quarto source.
Activate [latex-figures](../../references/visualize/latex-figures.md) for TikZ, PGFPlots,
or figure lineage.

For manuscript creation or revision, use the manuscript writing and
source-organization protocol in [LaTeX article profiles](../../references/visualize/latex-article-profiles.md#manuscript-writing-and-source-organization).
Route prose edits to `cse:write`.
For manuscript structure work, read the [writing principles](../../references/workflow/scientific-writing.md) in full.

For final manuscript review, use the [manuscript checkpoint](../../references/workflow/manuscript-review.md#final-manuscript-checkpoint).

Resolve document type and selected outputs when ambiguous or material. Inspect
the repository's existing build route and use `cse:quarto`, `cse:beamer`,
or `cse:tikz` for their owned paths. Keep one
retained data authority and one interpretation. Apply [latex-layout-and-qa](../../references/visualize/latex-layout-and-qa.md) to every selected PDF and inspect
the complete output at intended size.

For manuscript release completion, follow
[release build verification](../../references/visualize/rendering-guide.md#release-build-verification).
Follow the [rendering handoff](../../references/workflow/operating-model.md#decision-frontier-handoff-and-reference-reuse)
for reporting commands and returning material outputs to Review.
