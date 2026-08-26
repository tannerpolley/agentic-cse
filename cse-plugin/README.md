# Agentic Computational Science and Engineering

Agentic Computational Science and Engineering (`cse`) gives Codex a disciplined working method for computational science and physical-world engineering. It supports mechanical, chemical, electrical, civil, and related work—not generic software engineering—by keeping attention on the scientific question, equations, numerical method, reference cases, uncertainty, interpretation, and supported writing.

The plugin has nine workflow skills across eight normal levels and eleven
supporting tools.

## Workflow spine

The normal agent path is:

`setup → research or diagnose → design → build → analyze → review → summarize → write`

- `setup` establishes repository vocabulary and scientific conventions.
- `research` investigates literature, theory, and data.
- `diagnose` establishes why observed behavior disagrees with an expectation.
- `design` lays out the scientific work and publishes a GitHub issue when the repository uses GitHub issues.
- `build` implements models and numerical methods.
- `analyze` runs numerical studies and interprets results.
- `review` checks the Design-Build-Analyze set before accepted results advance.
- `summarize` admits an accepted analysis slice to its research journal.
- `write` develops an evidence-supported manuscript.

Research and Diagnose share level 02 and may both apply. Analyze routes an
unresolved core disagreement to Diagnose; otherwise it routes to Review. A
blocking review returns to the same Design and active issue before Build and
Analyze repeat. Review Pass continues to Summarize and is bounded to the stated
use and domain.

## Supporting tools

Sources tools:

- `zotero` retrieves and manages source-linked Zotero evidence through Companion.
- `mathpix` extracts equation-rich Zotero PDFs only when no Markdown child exists.
- `data` discovers, queries, validates, and traces retained scientific data.
- `digitize` extracts calibrated values from source figures with QA evidence.

Visualize tools:

- `plot` selects Matplotlib or PGFPlots for figures from retained values.
- `tikz` creates document-native LaTeX diagrams, schematics, and geometry.
- `pgfplots` creates table-driven LaTeX-native quantitative plots.
- `latex` is the explicit starting tool for a complete scientific document.
- `quarto` manages shared `.qmd` source and controlled multi-format rendering.
- `revealjs` creates interactive, scroll-capable scientific results views.
- `beamer` creates fixed-layout scientific presentation PDFs.

Invoke `$cse:latex` when you want one guided route through the document bundle.
It confirms the document type and outputs, uses the needed specialist tools,
builds every selected output, and completes visual inspection. Run
`scripts/check-latex-toolchain.sh` to verify the supported user toolchain:
TinyTeX as the TeX distribution and LuaLaTeX as its default PDF engine.

Document-producing workflows use the package and output-profile decisions in
[`references/latex-packages.md`](references/latex-packages.md), with curated
TikZ and PGF selections in
[`references/latex-extensions.md`](references/latex-extensions.md).
The distinct manuscript and research-journal contracts are in
[`references/latex-article-profiles.md`](references/latex-article-profiles.md).
[`references/revealjs.md`](references/revealjs.md) defines the interactive
research-journal view that shares retained results and figure sources with the
LuaLaTeX PDF.
Layout and visual acceptance rules are in
[`references/latex-layout-and-qa.md`](references/latex-layout-and-qa.md), and
[`references/latex-manuals.md`](references/latex-manuals.md) defines the
searchable user-level official-manual cache.

A runnable Quarto-managed chemical-engineering article, Moloch Beamer deck,
RevealJS example, and dual-output research journal live in
[`examples/quarto-chemical-engineering-showcase/`](examples/quarto-chemical-engineering-showcase/README.md).

The embedded [`heat-equation example`](examples/heat-equation/README.md) and
[`CSE Pi harness`](cse-pi-harness/README.md) are repository evidence and
project work, not installed plugin content. `scripts/sync-live.sh` excludes
both directories from deployment.

Tools support a workflow stage and return their evidence or files to that
stage; they are not additional steps in the workflow spine. A task may start at
the stage or tool that matches the user's request.

The plugin-wide language contract is in
[`references/terminology.md`](references/terminology.md), and vague agent
language to replace is collected in [`BANNED.md`](BANNED.md). Project-specific
terms belong in the user's `docs/scientific/CONTEXT.md`.

The starting workflow stage inspects current state, asks a material question round, confirms its interpretation, and then continues to the requested endpoint or a precise blocker. Internal continuations inherit confirmed decisions and ask only delta questions. CSE does not require Project Truss, Matt Pocock skills, Superpowers, generic Zotero or Mathpix skills, GitHub Actions, issue hierarchy, or coverage targets.

## Workbench research

Exploratory research into a standalone CSE application lives under
[`docs/workbench-research/`](docs/workbench-research/README.md). These documents
compare agent harnesses and examine Pi as a possible future runtime. That work
is paused while the Codex plugin matures through use on real CSE projects. It
does not change the accepted plugin behavior or select an implementation.

## Validate

```bash
./scripts/validate.sh
```

## Install a validated source revision

```bash
./scripts/sync-live.sh --validate
codex plugin add cse@personal --json
```

Start a fresh Codex task after installation so the task receives the new skills.
