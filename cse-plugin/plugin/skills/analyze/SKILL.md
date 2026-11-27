---
name: analyze
description: "Run accepted studies and interpret numerical results. Use when acting as a test sub-agent, or asked to \"analyze fit results\", \"run the study\", \"run the sweep\", or \"what do these results show\". Check balances, residuals, convergence, failed cases, and uncertainty."
metadata:
  cse-kind: "workflow"
  cse-family: "workflow"
  cse-order: "05"
  cse-tags: "workflow"
  cse-routing:
    direct: [operating-model, scientific-method]
    conditional: [numerical-testing, failure-triage, analysis-sets]
---

# Analyze results

Read first: [operating-model](../../references/workflow/operating-model.md), [scientific-method](../../references/workflow/scientific-method.md).

Activate [numerical-testing](../../references/workflow/numerical-testing.md) for reference, invariant, convergence, or
tolerance checks; [failure-triage](../../references/workflow/failure-triage.md) for incomplete or failed cases,
and its [run-cost rule](../../references/workflow/failure-triage.md#run-cost-plausibility)
for expensive or unexpectedly slow runs; and
[analysis-sets](../../references/workflow/analysis-sets.md) for retained analysis ownership.
Use
`cse:plot` when an installed rendering capability is required and
`cse:data` after checking the data capability and retained-input authority, columns,
lineage, or a bounded query is unresolved; an authoritative retained input
needs no Data probe.
For a registered source dataset moving into an analysis, follow the [Zotero
source/data handoff](../../references/sources/zotero-companion.md#source-and-data-handoff-to-analyze)
before running the calculation.
For an adopted analysis with a local Snakefile, use its optional `calculate`
entry for declared study-level work and `present` for selected displays from
retained results. Read the [Snakemake workflow reference](../../references/workflow/snakemake.md).

Inspect the accepted question, model, inputs, method, compute path, prior
results, and claim limits. Check balances, residuals, invariants, convergence,
and failed cases before interpretation. Separate data generation from
rendering, retain exact plotted values, run only analyses needed by the
question, and distinguish numerical error, source uncertainty, model
discrepancy, and named limits for the intended use. Show the best useful result
in numbers and a figure where applicable. Use the
[tolerance rule](../../references/workflow/numerical-testing.md#tolerances)
for agreement with data or a missed limit. Before interpreting or chasing a
residual, a deviation between runs or builds, or a convergence shortfall, apply
[fitness for purpose](../../references/workflow/numerical-testing.md#fitness-for-purpose). Follow
[Model adoption and comparison](../../references/workflow/scientific-method.md#model-adoption-and-comparison)
when comparing or deciding whether to adopt a candidate.

Apply the claim-led figure rule in [analysis-sets](../../references/workflow/analysis-sets.md) to retained comparisons.

Project-selected output formats are sufficient; do not require PDF, PNG, and
SVG together. Without CSE rendering, retain the numerical values and
interpretation and report the missing Plot capability when the central result
is plottable.

Require a useful, method-specific numerical result as defined by
[failure-triage](../../references/workflow/failure-triage.md). Reported success, an exit code, completed preflight, placeholder,
empty result file, or empty plot is not a result. If no useful result exists,
state that plainly, preserve the exact stopping point and diagnostic, and
ask `cse:diagnose` to establish the cause. A numerical non-result returns through
Diagnose to an attempted fix under
[failure-triage](../../references/workflow/failure-triage.md#fix-before-a-negative-disposition).
Otherwise summarize the result, evidence, interpretation, and limitations in
chat with retained paths, then hand the analysis set to `cse:review`.
