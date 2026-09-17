---
name: latex
description: "CSE — Route and verify a requested scientific document or standalone LaTeX figure/table."
metadata:
  cse-kind: "tool"
  cse-family: "visualize"
  cse-tags: "quarto-pipeline, latex-toolbox"
  cse-routing:
    direct: [rendering-guide, latex-packages]
    conditional: [latex-layout-and-qa, latex-article-profiles, quarto-execution, latex-figures]
---

# LaTeX document workflow

Inherit core scientific, project, and
language decisions.

Activate `latex-layout-and-qa` for layout defects, `latex-article-profiles`
for an article or notebook, and `quarto-execution` for a Quarto source.
Activate `latex-figures` for TikZ, PGFPlots,
or figure lineage.

For manuscript creation or revision, use the manuscript writing and
source-organization protocol in `latex-article-profiles.md`; do not create a
parallel writing skill or prose map.

Resolve document type and selected outputs when ambiguous or material. Inspect
the repository's existing build route and use `cse:quarto`, `cse:beamer`,
`cse:tikz`, or `cse:pgfplots` for their owned paths. Keep one
retained data authority and one interpretation; rendering never authorizes
model execution. Apply `latex-layout-and-qa` to every selected PDF and inspect
the complete output at intended size.

Compile, reject material warnings, run the selected visual checks, and inspect
the complete output at intended size. Return sources, outputs, commands,
retained paths, and limitations. Material document or figure changes return to
core CSE Review.
