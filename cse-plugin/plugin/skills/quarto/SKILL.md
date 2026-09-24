---
name: quarto
description: "Render one Quarto (.qmd) source to project-selected HTML, PDF, or presentation views without rerunning the model. Use when asked to \"render the notebook\", \"preview the manuscript\", or when quarto render fails. Raw LaTeX documents go to latex; Beamer slides to beamer."
metadata:
  cse-kind: "tool"
  cse-family: "visualize"
  cse-tags: "quarto-pipeline"
  cse-routing:
    direct: [rendering-guide, quarto-execution]
    conditional: [latex-packages, latex-article-profiles, latex-figures]
---

# Quarto document manager

Read first: [rendering-guide](../../references/visualize/rendering-guide.md), [quarto-execution](../../references/visualize/quarto-execution.md).

Inherit core scientific, project, and
language decisions.

Activate [latex-packages](../../references/visualize/latex-packages.md) and [latex-article-profiles](../../references/visualize/latex-article-profiles.md) for promoted PDF or
article outputs, and [latex-figures](../../references/visualize/latex-figures.md) for shared figures.

Inspect the existing project, profiles, source, includes, filters, output
paths, and render command. Keep shared scientific content in one source.
Ordinary Quarto HTML is the default living view of one root Quarto analysis
site: a Quarto website whose home page is the synthesis article and whose other
pages are the included reports, all sharing one docked sidebar, navigation bar,
theme, and page layout. For a confirmed analysis repository, initialize it with
`python3 assets/visualize/project/quarto/manuscript.py init analyses/ --article-source
<populated.qmd> --source-commit <SHA> --runtime-tree-sha256 <SHA256>`, then include
each substantive report with `manuscript.py include analyses/ <report.qmd>
--title <title> [--group <heading>]`. The command records the sole ordered `project.render` and
`website.sidebar` memberships, with the title as the sidebar entry, refuses
unsafe adoption, and leaves unregistered `.qmd` files out of the render. The normal render uses `execute.enabled: false` and
`--no-execute`; Quarto never runs the scientific model or mutates retained
results.

For a selected HTML endpoint, completion requires the populated `index.qmd`,
registered report sources, and their rendered HTML. Select an optional native
PDF view with `render.sh --to pdf`; the standalone example retains its separate
`promoted-pdf` profile and header. After an adopted analysis completes, use
`python3 analyses/manuscript.py refresh analyses analyses/<id>/notebook.qmd`; it runs the
presentation-only `present` target, then refreshes the included notebook page and
home page with the presentation cache invalidated. Use `manuscript.py preview` to let
native Quarto serve and reload the local HTML without opening an external
browser; its small bridge watches retained and presentation sources that native
preview misses and asks the running preview to re-render only the affected registered
sources; pass a free `--port`. The
presentation profile's sole pre-render hook runs presentation-only preparation
and never calculation. Keep the full customizable LaTeX manuscript route
separate.
Follow [quarto-execution](../../references/visualize/quarto-execution.md) for JSON-compatible configuration adoption.

Render each selected format from the same source revision and compare values,
conditions, uncertainty, interpretation, limitations, citations, and figure
sources. Material output changes return to `cse:review`.
