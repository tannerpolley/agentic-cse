# Agentic Computational Science and Engineering

Agentic Computational Science and Engineering (`cse`) gives Codex a disciplined working method for computational science and physical-world engineering. It supports mechanical, chemical, electrical, civil, and related work—not generic software engineering—by keeping attention on the scientific question, equations, numerical method, reference cases, uncertainty, interpretation, and supported writing.

The plugin has eight workflow stages and six supporting tools.

## Workflow spine

The default agent path is:

`setup → research → construct → build → analyze → summarize → write → review`

- `setup` establishes repository vocabulary and scientific conventions.
- `research` investigates literature, theory, and data.
- `construct` formulates substantive work and publishes its GitHub issue.
- `build` implements models and numerical methods.
- `analyze` runs numerical studies and interprets results.
- `summarize` admits an accepted analysis slice to its research journal.
- `write` develops an evidence-supported manuscript.
- `review` examines the complete scientific reasoning chain when requested.

## Supporting tools

- `zotero` retrieves and manages source-linked Zotero evidence through Companion.
- `mathpix` extracts equation-rich Zotero PDFs only when no Markdown child exists.
- `plot` creates clear model-versus-data figures from retained values.
- `digitize` extracts calibrated values from source figures with QA evidence.
- `tikz` creates document-native LaTeX diagrams, schematics, and geometry.
- `pgfplots` creates table-driven LaTeX-native quantitative plots.

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

Tools support a workflow stage and return their evidence or files to that
stage; they are not additional steps in the workflow spine. A task may start at
the stage or tool that matches the user's request.

The plugin-wide language contract is in
[`references/terminology.md`](references/terminology.md). Project-specific
terms belong in the user's `docs/scientific/CONTEXT.md`.

The starting workflow stage inspects current state, asks a material question round, confirms its interpretation, and then continues to the requested endpoint or a precise blocker. Internal continuations inherit confirmed decisions and ask only delta questions. CSE does not require Project Truss, Matt Pocock skills, Superpowers, generic Zotero or Mathpix skills, GitHub Actions, issue hierarchy, or coverage targets.

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
