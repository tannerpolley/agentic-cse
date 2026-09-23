---
name: tikz
description: "Draw document-native TikZ diagrams, geometry, meshes, schematics, and annotations where paths and relationships carry the meaning. Use when asked to \"draw a schematic\", \"make a TikZ diagram\", or \"draw the mesh\". Data-driven plots go to pgfplots or plot."
metadata:
  cse-kind: "tool"
  cse-family: "visualize"
  cse-tags: "latex-toolbox"
  cse-routing:
    direct: [rendering-guide, latex-figures]
    conditional: [latex-packages, latex-layout-and-qa]
---

# TikZ diagram tool

Read first: [rendering-guide](../../references/visualize/rendering-guide.md), [latex-figures](../../references/visualize/latex-figures.md).

Inherit core project and language
decisions. Activate [latex-packages](../../references/visualize/latex-packages.md) for package or engine choices and
[latex-layout-and-qa](../../references/visualize/latex-layout-and-qa.md) for placement or collision review.

Use TikZ for paths, nodes, arrows, shapes, labels, and geometric relations;
use `cse:pgfplots` for table-driven quantitative plots. Put source under the
project's established figure owner, keep geometry explicit, load only used
libraries, and preserve units and claim boundaries. Externalization is allowed
only through the controlled LaTeX route.

Compile and inspect each selected project format. Return source, output,
provenance, and limitations to the owning core CSE workflow stage.
