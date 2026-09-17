---
name: plot
description: "CSE — Create or review claim-led figures from retained scientific values."
metadata:
  cse-kind: "tool"
  cse-family: "visualize"
  cse-tags: "matplotlib, latex-toolbox"
  cse-routing:
    direct: [rendering-guide, plotting]
    conditional: [latex-figures]
---

# Plotting tool

Inherit core scientific, numerical,
project, and language decisions. Activate `latex-figures` only for a
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
