# Agentic Computational Science and Engineering

Agentic Computational Science and Engineering (`cse`) gives coding agents a disciplined working method for computational science and physical-world engineering. It supports mechanical, chemical, electrical, civil, and related work—not generic software engineering—by keeping attention on the scientific question, equations, numerical method, reference cases, uncertainty, interpretation, and supported writing.

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
- `quarto` manages shared `.qmd` source, ordinary HTML notebooks, and selected
  promoted PDF renders.
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
and HTML/PDF analysis research notebook live in
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

Validation uses Python 3.11 or later and the Codex Skill Creator validator.
Set `CSE_SKILL_VALIDATOR` to its `quick_validate.py` path if it is installed
outside the default Codex skills directory.

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

Install or deliberately update the stable hook runtime separately from plugin
updates, then opt each CSE repository into it:

```bash
python3 scripts/install_cse_hooks.py --agent codex --replace-runtime --repo /path/to/cse-repository
```

The shared runtime lives at `~/.local/share/cse/hooks`, outside either agent's
plugin cache. Plugin synchronization never replaces it. Installation merges
CSE handlers into `.codex/hooks.json` for Codex or `.claude/settings.json` for
Claude Code, preserving unrelated handlers and settings. It removes only exact
recognized CSE registrations, including the retired test-approval PostToolUse
and SubagentStop handlers, in the selected file. Other config layers require
inspection; old runtime files are retained for repositories not yet migrated.
Setup prepares scientific records and project guidance without creating or
changing hook configuration. CSE remains usable without hooks. After explicit
installation and host activation, hooks select the nearest
`docs/scientific/CONTEXT.md` at or above the working directory. They inject the
scientific stance at session/subagent entry and a short reminder at prompt entry.
Stop does not request an extra turn unless it finds a prose violation.
New, changed, and deleted test files are reported as advisory messages.
Changed Markdown, Quarto, and LaTeX prose is checked against `BANNED.md` at
Stop; violations block with the offending lines. Test-file growth stays advisory.
Review and trust repository hooks in the chosen host and start a fresh task
after installing. The commands here target POSIX systems with Python 3 and Git.

The four configured events serve different purposes:

| Event | Purpose | Limit |
| --- | --- | --- |
| SessionStart (`startup`, `resume`, `clear`, `compact`) | Restore the scientific stance; capture test/prose baselines on startup or clear, preserving them on resume/compaction | Refreshes instructions, not understanding; a fresh reviewer still needs evidence |
| SubagentStart | Give a child the same scientific stance | Does not supply its parent's research evidence or review its work |
| UserPromptSubmit | Briefly reinforce evidence-first answers on each user turn | Cannot prevent drift within a long turn |
| Stop | Check changed scientific prose and report test-file changes | Prose rules are mechanical; test changes are advisory, not scientific acceptance |

The prose check remains blocking on subsequent Stop attempts. Missing or invalid
prose baselines and unavailable checks report **not checked**, not acceptance, without repeatedly
blocking. Test-advisory failures likewise do not block. Hook execution
errors can skip checks with a warning, so silence is not proof of acceptance.
Hooks require loaded, trusted configuration in the task's actual checkout.
These mechanisms have no measured scientific-effectiveness score; the source
tests check event behavior, not the quality of an agent's judgment.

### Claude Code and installation diagnostics

The core plugin includes `.claude-plugin/plugin.json`; both hosts read the same
skills and scientific references. Load the source as a local Claude Code plugin
with `claude --plugin-dir /path/to/cse`. Hooks remain a separate opt-in:

```bash
python3 scripts/install_cse_hooks.py --agent claude --replace-runtime --repo /path/to/cse-repository
python3 scripts/install_cse_hooks.py --agent claude --diagnose --repo /path/to/cse-repository
```

For automatic project guidance in Claude Code, add `@AGENTS.md` to the root
`CLAUDE.md`, preserving existing instructions. The preparation script maintains
`AGENTS.md`; it does not create this host-specific import. Companion packaging,
marketplace synchronization, and installed-payload verification currently target
Codex only. The `$cse:...` examples are Codex syntax; Claude uses `/cse:...`.

Use `--agent codex` for the equivalent Codex diagnostic. Diagnosis writes
nothing and does not execute hooks. It lists CSE registrations and command
targets in user and project configuration, including legacy registrations,
missing or unsafe files, and saved Codex CSE plugin disables. It also reports
runtime hashes and source agreement, available CLI/Python/Git commands, and
uninspected layers. A saved plugin disable does not disable project hooks.
An `error` marks an incomplete source inspection; other sources and repositories
remain in the report. An unknown file existence value is reported as `null`.
Hooks resolve `python3` from the host's `PATH` and command targets from its
`HOME`; run diagnosis in that same environment. `--home` inspects another home
without changing the host's execution environment.
It cannot establish that the running host loaded or trusted those files;
inspect `/hooks` and verify a fresh-session event in the actual worktree.
Other config layers may add duplicate legacy handlers or disable hooks.

The shared runtime uses the common command-hook protocol: instruction injection
on entry, `decision: block` for prose violations, and system messages for test
advisories or unavailable checks. No host-specific model grader or transcript
parser is used. Source compatibility is implemented; actual Claude installation
and event execution remain unverified until an explicitly authorized trial.

## Source identity, not numbered releases

CSE uses Git commits and installed payload hashes to identify changes. The
plugin manifests omit release numbers; there is no version bump or tag gate.
Historical tags and result records remain evidence, not a release schedule.
`check-installed.py` distinguishes a changed payload hash, a different deployed
source commit, and an identity-format mismatch. An older deployment is not
evidence that it is broken. Identity-format changes, including removal of the
old `enabled` field, require a separately authorized source sync; do not edit
installed metadata by hand. Activation comes from the host, not payload identity.
Successful checks establish deployed file agreement and, unless `--deployed-only`
is selected, CLI installation and enablement. Active-task loaded state remains
unverified. Source edits alone do not update deployed or app-loaded content.

Plugin sync leaves the shared hook runtime unchanged. Runtime updates still
replace shared files individually; use only during an explicitly agreed pause
in affected hook execution. Non-disruptive runtime updates remain deferred.
Trial controllers now stage a candidate home and record launch identity; this
isolates configuration discovery, not filesystem access. Model trials require
an externally isolated runner and a separately authorized boundary smoke check;
see [the trial protocol](docs/testing/cooling-fit-workflow-benchmark.md).

Model-backed routing measurements and cooling-fit trials are opt-in and never
run automatically during validation, installation, or merge. Record any
explicitly requested measurement under `evaluation/results/<commit>-routing.md`.
