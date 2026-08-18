# Scientific Codex

Scientific Codex gives Codex a science-first working method for computational research. It keeps attention on the scientific question, equations, numerical method, reference cases, uncertainty, interpretation, and supported writing.

The plugin has eight workflow stages and four supporting tools.

## Workflow spine

The default agent path is:

`setup → research → construct → build → analyze → summarize → write → review`

- `setup` establishes repository vocabulary and scientific conventions.
- `research` investigates literature, theory, and data.
- `construct` formulates substantive work and publishes its GitHub issue.
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

Tools support a workflow stage and return their evidence or files to that
stage; they are not additional steps in the workflow spine. A task may start at
the stage or tool that matches the user's request.

The initial workflow entrypoint inspects current state, asks a material question round, confirms its interpretation, and then continues to the requested endpoint or a precise blocker. Internal handoffs inherit confirmed decisions and ask only delta questions. Scientific Codex does not require Project Truss, Matt Pocock skills, Superpowers, generic Zotero or Mathpix skills, GitHub Actions, issue hierarchy, or coverage targets.

## Validate

```bash
./scripts/validate.sh
```

## Install a validated source revision

```bash
./scripts/sync-live.sh --validate
codex plugin add scientific-codex@personal --json
```

Start a fresh Codex task after installation so the task receives the new skills.
