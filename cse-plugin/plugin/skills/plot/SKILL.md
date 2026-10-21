---
name: plot
description: "Create or review claim-led Python figures from retained scientific values, with lines for continuous relations and points for observations. Use when asked to \"plot this CSV\" or \"make a model-vs-data figure\". LaTeX-native plots go to pgfplots; diagrams to tikz."
metadata:
  cse-kind: "tool"
  cse-family: "visualize"
  cse-tags: "matplotlib, latex-toolbox"
  cse-routing:
    direct: [rendering-guide, plotting]
    conditional: [latex-figures]
---

# Plotting tool

Read first: [rendering-guide](../../references/visualize/rendering-guide.md), [plotting](../../references/visualize/plotting.md).

Inherit core scientific, numerical,
project, and language decisions. Activate [latex-figures](../../references/visualize/latex-figures.md) only for a
document-native backend.

Name the question, intended use, units, data authority, and series roles. Add a
comparison limit only when a named authority supplies one. Use a line only for
a retained continuous relationship and
`o`/`x` points for observations or reference values; do not imply continuity
from observation coordinates alone. Keep model generation separate from
rendering, retain exact plotted values and provenance, and select only the
formats required by the project and intended use. Avoid bars for continuous
comparisons unless their categorical meaning is recorded.

Return the figure, actual comparison, visible disagreement, limitation, and
checks to the invoking stage. An unexplained disagreement or unsupported curve
returns to `cse:analyze` or `cse:diagnose`.
