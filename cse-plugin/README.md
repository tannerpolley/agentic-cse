# Agentic Computational Science and Engineering

Agentic Computational Science and Engineering (`cse`) gives Codex a disciplined working method for computational science and physical-world engineering. It supports mechanical, chemical, electrical, civil, and related work—not generic software engineering—by keeping attention on the scientific question, equations, numerical method, reference cases, uncertainty, interpretation, and supported writing.

Core CSE has nine workflow skills across eight normal levels and one read-only
supporting `audit` skill. Optional
companions add Sources or Visualize capabilities when a project explicitly
needs them; core remains usable when neither is installed.

## Workflow spine

The normal agent path is:

`setup → research or diagnose → design → build → analyze → summarize → review → write`

- `setup` establishes or revises repository vocabulary and scientific conventions.
- `research` investigates literature, theory, and data.
- `diagnose` establishes why observed behavior disagrees with an expectation.
- `design` lays out the scientific work and publishes a GitHub issue when the repository uses GitHub issues.
- `build` implements models and numerical methods.
- `analyze` runs numerical studies and interprets results.
- `summarize` replaces one analysis research notebook with the current retained
  results and selected nonexecuting render.
- `review` checks the complete analysis, including that notebook and render.
- `write` develops an evidence-supported manuscript.

Research and Diagnose share level 02 and may both apply. Analyze routes an
unresolved core disagreement to Diagnose; otherwise it routes to Summarize. A
blocking review returns to the same Design and active issue before Build and
Analyze repeat. Review Pass is bounded to the stated use and domain. Only the
investigator may promote the reviewed notebook for manuscript use.

## Optional companion plugins

Install `cse-sources` with core `cse` for source evidence and retained-data
operations:

- `zotero` retrieves and manages source-linked Zotero evidence through Companion.
- `mathpix` extracts equation-rich Zotero PDFs only when no Markdown child exists.
- `data` discovers, queries, validates, and traces retained scientific data.
- `digitize` extracts calibrated values from source figures with QA evidence.

Install `cse-visualize` with core `cse` for figure and document rendering:

- `plot` selects Matplotlib or PGFPlots for figures from retained values.
- `tikz` creates document-native LaTeX diagrams, schematics, and geometry.
- `pgfplots` creates table-driven LaTeX-native quantitative plots.
- `latex` is the explicit starting tool for a complete scientific document.
- `quarto` manages shared `.qmd` source and controlled multi-format rendering.
- `revealjs` creates interactive, scroll-capable scientific results views.
- `beamer` creates fixed-layout scientific presentation PDFs.

Invoke `$cse-visualize:latex` when you want one guided route through the document bundle.
It confirms the document type and outputs, uses the needed specialist tools,
builds every selected output, and completes visual inspection. Run
`extensions/cse-visualize/scripts/check-latex-toolchain.sh` to verify the supported user toolchain:
TinyTeX as the TeX distribution and LuaLaTeX as its default PDF engine.

Document-producing workflows use the Visualize package's rendering references.
Shared scientific records and science-first decisions are defined in
[`references/scientific-projects.md`](references/scientific-projects.md) and
[`references/decision-records.md`](references/decision-records.md). Real
dependent leaves use the bounded sequence in
[`references/dependent-scientific-changes.md`](references/dependent-scientific-changes.md).
Visualize owns interactive analysis views, layout checks, and the official
LaTeX-manual cache. Core retains the authoritative notebook source and claim
order; rendering is conditional on the selected companion.

A runnable Quarto-managed chemical-engineering article, Moloch Beamer deck,
RevealJS example, and dual-output analysis research notebook live in
[`examples/quarto-chemical-engineering-showcase/`](examples/quarto-chemical-engineering-showcase/README.md).

The embedded [`heat-equation example`](examples/heat-equation/README.md) and
[`CSE Pi harness`](cse-pi-harness/README.md) are repository evidence and
project work, not installed plugin content. The deployment inventory omits both
directories.

Tools support a workflow stage and return their evidence or files to that
stage; they are not additional steps in the workflow spine. A task may start at
the stage or tool that matches the user's request.

The plugin-wide glossary is in
[`references/terminology.md`](references/terminology.md), and vague agent
language to replace is collected in [`BANNED.md`](BANNED.md). Project-specific
terms belong in the user's `docs/scientific/CONTEXT.md`; confirmed personal
preferences belong in `~/.config/cse/config.toml`.

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
codex plugin add cse-sources@personal --json
codex plugin add cse-visualize@personal --json
python3 scripts/check-installed.py --all
```

For repositories containing `docs/scientific/CONTEXT.md`, the CSE hooks inject
the persistent-test policy, seal the session-start test inventory outside the
repository, report test growth after write-capable tools, and block Stop or
SubagentStop until the exact current test fingerprint has explicit approval or
is removed. The gate does not claim OS-level write prevention or scientific
validity. Start a fresh Codex task after installation, verify the hook behavior,
and record representative routing results in `evaluation/results/<version>.md`.

Release versions follow semantic versioning: patches preserve skill and hook
behavior, minor versions add a skill, supporting tool, hook behavior, or
material workflow improvement, and major versions make an incompatible rename,
removal, or CSE repository-detection change. Tag `v<version>` only after source
validation, synchronization, installation, installed verification, hook trust
review, and the fresh-task routing pass succeed.
