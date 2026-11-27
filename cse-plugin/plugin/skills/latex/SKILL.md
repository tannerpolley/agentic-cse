---
name: latex
description: "Build and check scientific LaTeX PDFs. Use when asked for \"manuscript revision\" in LaTeX, \"build the paper PDF\", \"fix the manuscript layout\", \"my LaTeX won't compile\", or overfull boxes. Prose edits use write; slides go to beamer; .qmd to quarto; native figures to tikz."
metadata:
  cse-kind: "tool"
  cse-family: "visualize"
  cse-tags: "quarto-pipeline, latex-toolbox"
  cse-routing:
    direct: [rendering-guide, latex-packages]
    conditional: [latex-layout-and-qa, latex-article-profiles, analysis-notebook-profile, scientific-writing, manuscript-review, quarto-execution, latex-figures]
---

# LaTeX document workflow

Read first: [rendering-guide](../../references/visualize/rendering-guide.md), [latex-packages](../../references/visualize/latex-packages.md).

Inherit core scientific, project, and
language decisions.

Activate [latex-layout-and-qa](../../references/visualize/latex-layout-and-qa.md) for layout defects, [latex-article-profiles](../../references/visualize/latex-article-profiles.md)
for a scientific article, the
[analysis-notebook profile](../../references/workflow/analysis-notebook-profile.md)
for notebook PDF layout, and [quarto-execution](../../references/visualize/quarto-execution.md) for a Quarto source.
Activate [latex-figures](../../references/visualize/latex-figures.md) for TikZ, PGFPlots,
or figure lineage.

For manuscript creation or revision, use the manuscript writing and
source-organization protocol in [LaTeX article profiles](../../references/visualize/latex-article-profiles.md#manuscript-writing-and-source-organization).
Route prose edits to `cse:write` and use the authoritative manuscript source and its stable paragraph identifiers.
For manuscript structure, use the [writing principles](../../references/workflow/scientific-writing.md#structure).

For final manuscript review, use the [manuscript checkpoint](../../references/workflow/manuscript-review.md#final-manuscript-checkpoint).

Resolve document type and selected outputs when ambiguous or material. Inspect
the repository's existing build route and use `cse:quarto`, `cse:beamer`,
or `cse:tikz` for their owned paths. Keep one
retained data authority and one interpretation; rendering never authorizes
model execution. Apply [latex-layout-and-qa](../../references/visualize/latex-layout-and-qa.md) to every selected PDF and inspect
the complete output at intended size.

For manuscript release completion, follow
[release build verification](../../references/visualize/rendering-guide.md#release-build-verification).
Verify embedded fonts are vector using the
[font check](../../references/visualize/latex-layout-and-qa.md#release-sequence),
and read the final log for undefined references and citations with its log check.
Return sources, outputs, commands, retained paths, and limitations. Material
document or figure changes return to core CSE Review.
