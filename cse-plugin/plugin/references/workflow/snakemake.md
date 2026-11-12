# Snakemake for adopted analyses

Setup offers Snakemake as an optional capability for a populated analysis
workspace. Analyze uses the calculation entry for declared study-level work;
Summarize uses the presentation entry for deterministic tables, figures, and
Quarto include files. Adoption is local to an analysis and does not make
Snakemake a CSE-wide requirement.

## Calculation and presentation

The `calculate` entry reads declared local inputs, parameter files, scripts,
imported helpers, and the selected environment, then writes named files under
`results/` and `figures/`. A calculation job represents one study or
independently executable batch, not a function evaluation or solver iteration.

The `present` entry is loaded without calculation rules. It reads the retained
result set, verifies its completion identity and file hashes, and writes the
table or include fragment. Missing, incomplete, or mismatched retained results
fail with a diagnostic; presentation never manufactures a result or runs a
model. A converged result with poor physical agreement remains retained and
reported with its error and comparisons as a physical finding under
[failure-triage](failure-triage.md#fix-before-a-negative-disposition).

Calculation writes to a temporary staging location and promotes the validated
named result set and its selection identity only after all required files are
ready, rolling back the previous set if replacement fails. The presentation
step accepts only a hash-coherent set. A workflow rerun may read declared local
inputs and run the selected entry; it must never query Zotero, alter source
files, or make a presentation rerun run models.

Use the adopted project's existing `uv` environment and lockfile when one is
present. Declare that lockfile, or an exact runtime identity when the project
uses a prepared `uv` environment, as a calculation input and fail on a
mismatch. The workflow has no Conda requirement:

```bash
snakemake --cores 1 calculate
snakemake present
snakemake --cores 1 --dry-run calculate
snakemake --dry-run present
```

The dry-run commands show the execution plan without running a job. Run each
entry separately so the presentation boundary remains visible.

Snakemake 9 requires an explicit local core count; for that version use
`snakemake --cores 1 present` when the bare presentation command rejects local
execution.

After `calculate` completes with its required checks, run the adopted manuscript
manager's `refresh <root> <notebook.qmd>` command. Refresh runs the
presentation-only `present` entry before rendering; it never calls `calculate`.
A missing, partial, or hash-mismatched retained set fails the render and leaves
no new success page.

Snakemake still executes top-level Python in a Snakefile while parsing it. That
is inherent to Snakemake and remains outside this presentation safety boundary;
the dry-run check only permits execution when the planned job is `present`.
