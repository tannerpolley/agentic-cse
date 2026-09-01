# CSE project guidance

Read [the scientific context](docs/scientific/CONTEXT.md) before changing equations, numerical methods,
tests, retained analyses, figures, or manuscript claims. This repository is an
executable scientific argument about FTCS and Crank-Nicolson for one
dimensionless heat-equation reference case.

Keep the chain explicit:

- `src/heat_verification/` owns the declared numerical methods and public
  scientific API;
- `tests/` protects distinct scientific failure meanings, not helper coverage;
- `analyses/heat_verification/` owns the retained input snapshot, tables, exact
  plotted data, SVG, PNG, and PDF figures, and analysis notebook;
- `docs/scientific/` owns shared formulation, method, evidence, uncertainty,
  decision records, and writing rules;
- `docs/scientific/latex/` owns the self-contained tutorial manuscript;
- `evaluation/` owns sanitized ten-skill behavioral evidence, never private
  transcripts.

All quantities are dimensionless. Keep the continuous reference, centered
space semidiscrete reference, and each scheme's amplification factor distinct.
Do not promote code or solution verification into physical model validation.

Zotero owns bibliographic metadata and attachments. Generate the project-only
snapshot from `/home/user/Zotero/exports/references.bib` with
`scripts/sync_bibliography.sh`. Never hand-edit
`docs/scientific/latex/references.bib`,
and never add local attachment paths to it.

Use the validation ladder:

```bash
uv run python scripts/validate_project.py quick
uv run python scripts/validate_project.py confidence
uv run python scripts/validate_project.py docs
uv run python scripts/validate_project.py full
```

Large data is not needed for this tutorial. Small generated CSV tables and
curated SVG, PNG, and PDF figures are Git-tracked evidence. If future work
needs large data, declare its authority, format, lineage, retention,
versioning, and recovery policy before retaining it.
