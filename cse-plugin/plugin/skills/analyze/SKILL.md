---
name: analyze
description: "CSE Execute and deliver — Run and interpret an accepted numerical study, preserving failures, uncertainty, and claim limits."
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

Activate `numerical-testing` for reference, invariant, convergence, or
tolerance checks; `failure-triage` for incomplete or failed cases; and
`scientific-projects` for retained analysis ownership.
Use
`cse:plot` when an installed rendering capability is required and
`cse:data` after checking the data capability and retained-input authority, columns,
lineage, or a bounded query is unresolved; an authoritative retained input
needs no Data probe.

Inspect the accepted question, model, inputs, method, compute path, prior
results, and claim limits. Check balances, residuals, invariants, convergence,
and failed cases before interpretation. Separate data generation from
rendering, retain exact plotted values, run only analyses needed by the
question, and distinguish numerical error, source uncertainty, model
discrepancy, and named limits for the intended use.

Apply the claim-led figure rule in `scientific-projects` to retained comparisons.

Project-selected output formats are sufficient; do not require PDF, PNG, and
SVG together. Without CSE rendering, retain the numerical values and
interpretation and report the missing Plot capability when the central result
is plottable.

Require a useful, method-specific numerical result as defined by
`failure-triage`. Reported success, an exit code, completed preflight, placeholder,
empty result file, or empty plot is not a result. If no useful result exists,
state that plainly, preserve the exact stopping point and diagnostic, and
route the cause to `cse:diagnose`; do not report completion or create a
notebook. Otherwise send the retained results to `cse:summarize` so Review can
inspect the complete notebook and selected render.
