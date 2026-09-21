---
name: quarto
description: "CSE — Render one scientific Quarto source to project-selected PDF, presentation, or HTML views without rerunning the model."
metadata:
  cse-kind: "tool"
  cse-family: "visualize"
  cse-tags: "quarto-pipeline"
  cse-routing:
    direct: [rendering-guide, quarto-execution]
    conditional: [latex-packages, latex-article-profiles, latex-figures]
---

# Quarto document manager

Inherit core scientific, project, and
language decisions.

Activate `latex-packages` and `latex-article-profiles` for promoted PDF or
article outputs, and `latex-figures` for shared figures.

Inspect the existing project, profiles, source, includes, filters, output
paths, and render command. Keep shared scientific content in one source.
Ordinary Quarto HTML is the default living view of one root Quarto Manuscript. For a
confirmed analysis repository, initialize it with
`python3 assets/visualize/project/quarto/manuscript.py init analyses/ --article-source
<populated.qmd> --source-commit <SHA> --runtime-tree-sha256 <SHA256>`, then include
each substantive report with `manuscript.py include analyses/ <report.qmd>
--title <title>`. The command records the sole ordered `project.render` and
`manuscript.notebooks` memberships, refuses unsafe adoption, and leaves unregistered `.qmd` files
out of the render. The normal render uses `execute.enabled: false` and
`--no-execute`; Quarto never runs the scientific model or mutates retained
results.

For a selected HTML endpoint, completion requires the populated `index.qmd`,
registered report sources, and their rendered HTML. Select an optional native
PDF view with `render.sh --to pdf`; the standalone example retains its separate
`promoted-pdf` profile and header. After an adopted analysis completes, use
`python3 manuscript.py refresh <root> <notebook.qmd>`; it runs the
presentation-only `present` target, then refreshes the included notebook and
root article with the presentation cache invalidated. Use `manuscript.py preview` to let
native Quarto serve and reload the local HTML without opening an external
browser; its small bridge watches retained and presentation sources that native
preview misses and touches only the affected registered sources. The
presentation profile's sole pre-render hook runs presentation-only preparation
and never calculation. Keep the full customizable LaTeX manuscript route
separate.
Follow `quarto-execution` for JSON-compatible configuration adoption.

Render each selected format from the same source revision and compare values,
conditions, uncertainty, interpretation, limitations, citations, and figure
sources. Material output changes return to `cse:review`.
