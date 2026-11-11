---
name: tikz
description: "Draw LaTeX-native TikZ diagrams or PGFPlots data plots from retained tables. Use when asked to \"draw a schematic\", \"make a TikZ diagram\", \"draw the mesh\", make \"a pgfplots figure\", or \"plot this table in LaTeX\". Python figures go to plot."
metadata:
  cse-kind: "tool"
  cse-family: "visualize"
  cse-tags: "latex-toolbox"
  cse-routing:
    direct: [rendering-guide, latex-figures]
    conditional: [latex-packages, latex-layout-and-qa, plotting]
---

# LaTeX-native figure tool

Read first: [rendering-guide](../../references/visualize/rendering-guide.md), [latex-figures](../../references/visualize/latex-figures.md).

Inherit core numerical, project, and language
decisions. Activate [latex-packages](../../references/visualize/latex-packages.md) for package or engine choices and
[latex-layout-and-qa](../../references/visualize/latex-layout-and-qa.md) for placement or collision review.

Use TikZ for paths, nodes, arrows, shapes, labels, and geometric relations;
use PGFPlots for table-driven quantitative plots. Put source under the
project's established figure owner, keep geometry explicit, load only used
libraries, and preserve units and claim boundaries. Externalization is allowed
only through the controlled LaTeX route.

Compile and inspect each selected project format. Return source, output,
provenance, and limitations to the owning core CSE workflow stage.

## Table-driven quantitative plots

Activate [plotting](../../references/visualize/plotting.md) for table-driven quantitative plots.

Inspect the exact table, columns, units, roles, and project formats. Use
explicit named `x` and `y` columns; lines represent retained relationships and
`o`/`x` marks represent observations or references. Keep fitting, filtering,
and data generation in analysis code. Avoid shell calls, arbitrary
`\write18`, unsupported precision, and continuous curves without retained
support. Compile and inspect the selected output, returning table path, source,
hashes, and checks.
