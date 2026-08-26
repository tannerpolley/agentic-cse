# Agentic Computational Science and Engineering

Agentic Computational Science and Engineering (`cse`) gives Codex a disciplined working method for computational science and physical-world engineering. It supports mechanical, chemical, electrical, civil, and related work—not generic software engineering—by keeping attention on the scientific question, equations, numerical method, reference cases, uncertainty, interpretation, and supported writing.

The plugin has eight workflow stages and six supporting tools.

## Workflow spine

The default agent path is:

`setup → research → construct → build → analyze → summarize → write → review`

- `setup` establishes repository vocabulary and scientific conventions.
- `research` investigates literature, theory, and data.
- `construct` formulates substantive work and publishes a GitHub issue when the repository uses GitHub issues.
- `build` implements models and numerical methods.
- `analyze` runs numerical studies and interprets results.
- `summarize` records a complete analysis slice.
- `write` develops an evidence-supported manuscript.
- `review` examines the complete scientific reasoning chain when requested.

## Supporting tools

- `zotero` retrieves and manages source-linked Zotero evidence through Companion.
- `mathpix` extracts equation-rich Zotero PDFs only when no Markdown child exists.
- `plot` creates clear model-versus-data figures from retained values.
- `digitize` extracts calibrated values from source figures with QA evidence.
- `tikz` creates document-native LaTeX diagrams, schematics, and geometry.
- `pgfplots` creates table-driven LaTeX-native quantitative plots.

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
