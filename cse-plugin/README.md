# Scientific Codex

Scientific Codex gives Codex a science-first working method for computational research. It keeps attention on the scientific question, equations, numerical method, reference cases, uncertainty, interpretation, and supported writing.

The plugin exposes eight front doors:

- `setup` establishes repository vocabulary and scientific conventions.
- `research` investigates literature, theory, and data.
- `construct` formulates substantive work and publishes its GitHub issue.
- `build` implements models and numerical methods.
- `analyze` runs numerical studies and creates figures.
- `summarize` records a complete analysis slice.
- `write` develops an evidence-supported manuscript.
- `review` examines the complete scientific reasoning chain.

Every front door inspects the current state, asks at least one material question round, confirms its interpretation, and then continues to the requested endpoint or a precise blocker. Scientific Codex does not require Project Truss, Matt Pocock skills, Superpowers, GitHub Actions, issue hierarchy, or coverage targets.

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
