---
name: quarto
description: "Render one Quarto (.qmd) source to project-selected HTML, PDF, or presentation views without rerunning the model. Use when asked to \"render this Quarto document\", or when quarto render fails. Raw LaTeX documents go to latex; Beamer slides to beamer."
metadata:
  cse-kind: "tool"
  cse-family: "visualize"
  cse-tags: "quarto-pipeline"
  cse-routing:
    direct: [rendering-guide, quarto-execution]
    conditional: [latex-packages, latex-article-profiles, scientific-writing, latex-figures, slide-decks]
---

# Quarto document manager

Read first: [rendering-guide](../../references/visualize/rendering-guide.md), [quarto-execution](../../references/visualize/quarto-execution.md).

Inherit core scientific, project, and
language decisions.

Activate [latex-packages](../../references/visualize/latex-packages.md) and [latex-article-profiles](../../references/visualize/latex-article-profiles.md) for PDF or article outputs.
For article displays and captions, use the [writing principles](../../references/workflow/scientific-writing.md#shared-article-requirements).
Activate [latex-figures](../../references/visualize/latex-figures.md) for shared figures.

Inspect the existing project, profiles, source, includes, filters, output
paths, and render command. Keep shared scientific content in one source.
Use the project's existing render command with document execution disabled.
The plugin's `assets/visualize/project/quarto/render.sh` renders HTML by default.
Pass `--to pdf` for a configured PDF view. Verify the selected outputs from
the populated sources.

For presentation views, follow [slide-decks](../../references/visualize/slide-decks.md) for deck defaults and the delivery check.
For a selected `.pptx` presentation view, build with the project's own route (including its reference deck and finishing scripts when configured) and load the `pptx` skill to inspect and validate the rendered file.

Render each selected format from the same source revision and compare values,
conditions, uncertainty, interpretation, limitations, citations, and figure
sources. For manuscript/deck releases, follow
[release build verification](../../references/visualize/rendering-guide.md#release-build-verification);
TeX diagnostics apply only to TeX outputs, not HTML-only previews.
Material output changes return to `cse:review`.
