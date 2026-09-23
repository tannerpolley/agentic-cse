---
name: analyze
description: "Run an accepted numerical study and interpret it, checking balances, residuals, convergence, and failed cases while keeping uncertainty and claim limits. Use when asked to \"run the study\", \"run the sweep\", or \"what do these results show\". The notebook write-up goes to summarize."
metadata:
  cse-kind: "workflow"
  cse-family: "workflow"
  cse-order: "05"
  cse-tags: "workflow"
  cse-routing:
    direct: [operating-model, scientific-method]
    conditional: [numerical-testing, failure-triage, scientific-projects]
---

# Analyze results

Read first: [operating-model](../../references/workflow/operating-model.md), [scientific-method](../../references/workflow/scientific-method.md).

Activate [numerical-testing](../../references/workflow/numerical-testing.md) for reference, invariant, convergence, or
tolerance checks; [failure-triage](../../references/workflow/failure-triage.md) for incomplete or failed cases; and
[scientific-projects](../../references/workflow/scientific-projects.md) for retained analysis ownership.
Use
`cse:plot` when an installed rendering capability is required and
`cse:data` after checking the data capability and retained-input authority, columns,
lineage, or a bounded query is unresolved; an authoritative retained input
needs no Data probe.
For a registered source dataset moving into an analysis, follow the [Zotero
source/data handoff](../../references/sources/zotero-companion.md#source-and-data-handoff-to-analyze)
before running the calculation.
For an adopted analysis with a local Snakefile, use its optional `calculate`
entry for declared study-level work and hand retained checked outputs to
Summarize; read the [Snakemake workflow reference](../../references/workflow/snakemake.md).
Run the calculation and handoff as two commands:

```bash
snakemake --cores 1 calculate
python3 analyses/manuscript.py refresh analyses analyses/<id>/notebook.qmd
```

Refresh runs the presentation-only `present` entry before the notebook/root
handoff; it never runs calculation, source acquisition, or model-backed
interpretation.

Inspect the accepted question, model, inputs, method, compute path, prior
results, and claim limits. Check balances, residuals, invariants, convergence,
and failed cases before interpretation. Separate data generation from
rendering, retain exact plotted values, run only analyses needed by the
question, and distinguish numerical error, source uncertainty, model
discrepancy, and named limits for the intended use.

Apply the claim-led figure rule in [scientific-projects](../../references/workflow/scientific-projects.md) to retained comparisons.

Project-selected output formats are sufficient; do not require PDF, PNG, and
SVG together. Without CSE rendering, retain the numerical values and
interpretation and report the missing Plot capability when the central result
is plottable.

Require a useful, method-specific numerical result as defined by
[failure-triage](../../references/workflow/failure-triage.md). Reported success, an exit code, completed preflight, placeholder,
empty result file, or empty plot is not a result. If no useful result exists,
state that plainly, preserve the exact stopping point and diagnostic, and
route the cause to `cse:diagnose`; do not report completion or create a
notebook. Otherwise send the retained results to `cse:summarize` so Review can
inspect the complete notebook and selected render.
