---
name: tikz
description: "CSE — Create document-native diagrams, geometry, meshes, and annotations with TikZ when paths and relationships carry the meaning."
metadata:
  cse-kind: "tool"
  cse-family: "visualize"
  cse-tags: "latex-toolbox"
  cse-routing:
    direct: [rendering-guide, latex-figures]
    conditional: [latex-packages, latex-layout-and-qa]
---

# TikZ diagram tool

Inherit core project and language
decisions. Activate `latex-packages` for package or engine choices and
`latex-layout-and-qa` for placement or collision review.

Use TikZ for paths, nodes, arrows, shapes, labels, and geometric relations;
use `cse:pgfplots` for table-driven quantitative plots. Put source under the
project's established figure owner, keep geometry explicit, load only used
libraries, and preserve units and claim boundaries. Externalization is allowed
only through the controlled LaTeX route.

Compile and inspect each selected project format. Return source, output,
provenance, and limitations to the owning core CSE workflow stage.
