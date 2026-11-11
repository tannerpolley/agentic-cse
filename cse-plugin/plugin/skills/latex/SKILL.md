---
name: latex
description: "Choose the build path for a scientific LaTeX document or standalone figure or table, then compile and verify it. Use when asked to \"build the paper PDF\", \"my LaTeX won't compile\", or about overfull boxes. Slides go to beamer; .qmd sources to quarto; figures to tikz."
metadata:
  cse-kind: "tool"
  cse-family: "visualize"
  cse-tags: "quarto-pipeline, latex-toolbox"
  cse-routing:
    direct: [rendering-guide, latex-packages]
    conditional: [latex-layout-and-qa, latex-article-profiles, quarto-execution, latex-figures]
---

# LaTeX document workflow

Read first: [rendering-guide](../../references/visualize/rendering-guide.md), [latex-packages](../../references/visualize/latex-packages.md).

Inherit core scientific, project, and
language decisions.

Activate [latex-layout-and-qa](../../references/visualize/latex-layout-and-qa.md) for layout defects, [latex-article-profiles](../../references/visualize/latex-article-profiles.md)
for an article or notebook, and [quarto-execution](../../references/visualize/quarto-execution.md) for a Quarto source.
Activate [latex-figures](../../references/visualize/latex-figures.md) for TikZ, PGFPlots,
or figure lineage.

For manuscript creation or revision, use the manuscript writing and
source-organization protocol in [latex-article-profiles](../../references/visualize/latex-article-profiles.md); do not create a
parallel writing skill or prose map.

Resolve document type and selected outputs when ambiguous or material. Inspect
the repository's existing build route and use `cse:quarto`, `cse:beamer`,
or `cse:tikz` for their owned paths. Keep one
retained data authority and one interpretation; rendering never authorizes
model execution. Apply [latex-layout-and-qa](../../references/visualize/latex-layout-and-qa.md) to every selected PDF and inspect
the complete output at intended size.

Compile, reject material warnings, verify embedded fonts are vector using the
[font check](../../references/visualize/latex-layout-and-qa.md#release-sequence), run the selected visual checks, and inspect
the complete output at intended size. Return sources, outputs, commands,
retained paths, and limitations. Material document or figure changes return to
core CSE Review.
