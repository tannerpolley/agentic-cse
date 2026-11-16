---
name: plot
description: "Create, redesign, or review Python figures from retained values. Use when asked to \"redesign Figure N\", \"Figure 3 redesign\", \"fix unreadable plots\", \"plot this CSV\", or \"make a model-vs-data figure\". Lines show continuous relations; observations are points. LaTeX-native figures go to tikz."
metadata:
  cse-kind: "tool"
  cse-family: "visualize"
  cse-tags: "matplotlib, latex-toolbox"
  cse-routing:
    direct: [rendering-guide, plotting]
    conditional: [latex-figures, scientific-writing]
---

# Plotting tool

Read first: [rendering-guide](../../references/visualize/rendering-guide.md), [plotting](../../references/visualize/plotting.md).

Inherit core scientific, numerical,
project, and language decisions. Activate [latex-figures](../../references/visualize/latex-figures.md) only for a
document-native backend.

For manuscript/deck figures, activate [scientific-writing's standing-decision protocol](../../references/workflow/scientific-writing.md#standing-editorial-decisions)
before editing, including capture of new owner directions. Unrelated
exploratory plots do not load manuscript rules.

Name the question, intended use, units, data authority, and series roles. Add a
comparison limit only when a named authority supplies one. Use a line only for
a retained continuous relationship and
observations/reference points with distinct markers as needed; do not imply continuity
from observation coordinates alone. Keep model generation separate from
rendering, retain exact plotted values and provenance, and select only the
formats required by the project and intended use. Avoid bars for continuous
comparisons unless their categorical meaning is recorded.

Use the existing project style; otherwise adopt the shipped Matplotlib starter
following [plotting](../../references/visualize/plotting.md#matplotlib-style-and-sizing).
Apply that reference’s distinct-comparison and intended-size/grayscale checks.

Return the figure, actual comparison, visible disagreement, limitation, and
checks to the invoking stage. An unexplained disagreement or unsupported curve
returns to `cse:analyze` or `cse:diagnose`.
