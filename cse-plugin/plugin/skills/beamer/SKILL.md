---
name: beamer
description: "Build or revise scientific Beamer PDFs with frame-by-frame checks. Use when asked to \"revise the slide deck\", \"update the presentation\", \"make slides\", \"build a Beamer talk\", or \"fix this overflowing slide\". Route article PDFs to latex, HTML .qmd views to quarto, and PowerPoint .pptx decks to pptx."
metadata:
  cse-kind: "tool"
  cse-family: "visualize"
  cse-tags: "quarto-pipeline, latex-toolbox"
  cse-routing:
    direct: [rendering-guide, latex-layout-and-qa]
    conditional: [latex-packages, latex-figures, quarto-execution, scientific-writing]
---

# Beamer presentation tool

For PowerPoint decks (`.pptx` or `.potx`), use the `pptx` skill to read slides, generate thumbnails, validate the file, or make edits.

Read first: [rendering-guide](../../references/visualize/rendering-guide.md), [latex-layout-and-qa](../../references/visualize/latex-layout-and-qa.md).

Inherit core scientific, project, and
language decisions.

Activate [latex-packages](../../references/visualize/latex-packages.md) for package choices, [latex-figures](../../references/visualize/latex-figures.md) for shared
figures, and [quarto-execution](../../references/visualize/quarto-execution.md) for a `.qmd`.

For deck work, activate [scientific-writing's standing-decision read/update protocol](../../references/workflow/scientific-writing.md#standing-editorial-decisions)
before editing.

Inspect audience, purpose, source format, theme, aspect ratio, placement,
figures, notes, and build route. Give each frame one scientific purpose and
use overlays only when their sequence explains a relation. Design shared
figures at the narrower placement and use `cse:tikz` as
appropriate. Do not repair crowding with automatic shrink.

For release completion, follow
[release build verification](../../references/visualize/rendering-guide.md#release-build-verification)
and [frame-by-frame visual QA](../../references/visualize/latex-layout-and-qa.md#release-sequence).
Material changes return to core CSE Review; successful rendering is not Review Pass.

For source, figure, and deck identifier advisories, follow the shared
[reader-facing identifier check](../../references/workflow/scientific-writing.md#reader-facing-identifiers).
