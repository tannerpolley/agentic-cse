---
name: beamer
description: "CSE — Build or revise a fixed-layout scientific Beamer presentation PDF."
metadata:
  cse-kind: "tool"
  cse-family: "visualize"
  cse-tags: "quarto-pipeline, latex-toolbox"
  cse-routing:
    direct: [rendering-guide, latex-layout-and-qa]
    conditional: [latex-packages, latex-figures, quarto-execution]
---

# Beamer presentation tool

Inherit core scientific, project, and
language decisions.

Activate `latex-packages` for package choices, `latex-figures` for shared
figures, and `quarto-execution` for a `.qmd`.

Inspect audience, purpose, source format, theme, aspect ratio, placement,
figures, notes, and build route. Give each frame one scientific purpose and
use overlays only when their sequence explains a relation. Design shared
figures at the narrower placement and use `cse:tikz` or `cse:pgfplots` as
appropriate. Do not repair crowding with automatic shrink.

Compile the selected PDF, run visual QA, inspect every frame at full size and
in grayscale, and reject errors, unresolved references, clipping, substitutions,
or unexplained overfull boxes. Material changes return to core CSE Review;
successful rendering is not Review Pass.
