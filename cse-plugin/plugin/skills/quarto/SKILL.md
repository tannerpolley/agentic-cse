---
name: quarto
description: "Render one Quarto (.qmd) source to project-selected HTML, PDF, or presentation views without rerunning the model. Use when asked to \"render the notebook\", or when quarto render fails. Raw LaTeX documents go to latex; Beamer slides to beamer."
metadata:
  cse-kind: "tool"
  cse-family: "visualize"
  cse-tags: "quarto-pipeline"
  cse-routing:
    direct: [rendering-guide, quarto-execution]
    conditional: [latex-packages, latex-article-profiles, analysis-notebook-profile, scientific-writing, latex-figures, slide-decks]
---

# Quarto document manager

Read first: [rendering-guide](../../references/visualize/rendering-guide.md), [quarto-execution](../../references/visualize/quarto-execution.md).

Inherit core scientific, project, and
language decisions.

Activate [latex-packages](../../references/visualize/latex-packages.md) and [latex-article-profiles](../../references/visualize/latex-article-profiles.md) for promoted PDF or
article outputs. For an analysis notebook, use its [output profile](../../references/workflow/analysis-notebook-profile.md).
For article displays and captions, use the [writing principles](../../references/workflow/scientific-writing.md#shared-article-requirements).
Activate [latex-figures](../../references/visualize/latex-figures.md) for shared figures.

Inspect the existing project, profiles, source, includes, filters, output
paths, and render command. Keep shared scientific content in one source.
For a confirmed analysis repository, place the synthesis at `analyses/index.qmd`.
Run the plugin asset's `manuscript.py init analyses/`, then register each
report with `python3 analyses/manuscript.py include analyses/ <report.qmd>
--title <title> [--group <heading>]`. The report path is relative to the working
directory. Pages share one website sidebar and theme. Quarto lists sections
on each page.

Run `bash analyses/render.sh` for HTML, or pass `--to pdf` for a configured
PDF view. Rendering leaves model execution outside the build. Use
`python3 analyses/manuscript.py refresh analyses/ <report.qmd>` to run the
report folder's `present` rule if it has a Snakefile, then rebuild the report
and home page. Verify the selected outputs from the populated sources.

For presentation views, follow [slide-decks](../../references/visualize/slide-decks.md) for deck defaults and the delivery check.
For a selected `.pptx` presentation view, build with the project's own route (including its reference deck and finishing scripts when configured) and load the `pptx` skill to inspect and validate the rendered file.

Render each selected format from the same source revision and compare values,
conditions, uncertainty, interpretation, limitations, citations, and figure
sources. For manuscript/deck releases, follow
[release build verification](../../references/visualize/rendering-guide.md#release-build-verification);
TeX diagnostics apply only to TeX outputs, not HTML-only previews.
Material output changes return to `cse:review`.
