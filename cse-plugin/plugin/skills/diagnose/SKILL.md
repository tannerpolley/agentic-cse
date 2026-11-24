---
name: diagnose
description: "Diagnose scientific failures or implausible run times through reproduction and bounded probes. Use when asked \"why does my solver diverge\", \"why is this run so slow\", or \"why doesn't this match the reference\", or about numerical NaNs and non-convergence. Other software bugs go to diagnosing-bugs."
metadata:
  cse-kind: "workflow"
  cse-family: "workflow"
  cse-order: "02B"
  cse-tags: "workflow"
  cse-routing:
    direct: [operating-model, failure-triage]
    conditional: [scientific-method, numerical-testing]
---

# Diagnose numerical behavior

Read first: [operating-model](../../references/workflow/operating-model.md), [failure-triage](../../references/workflow/failure-triage.md).

For expensive or unexpectedly slow runs, apply the
[run-cost rule](../../references/workflow/failure-triage.md#run-cost-plausibility).

Apply the shared [decision-frontier rule](../../references/workflow/operating-model.md#decision-frontier-handoff-and-reference-reuse) after inspection to an unresolved causal
distinction or the smallest bounded next probe.

Activate [scientific-method](../../references/workflow/scientific-method.md) when equations, units, basis, validity, or claim
limits are in dispute. Activate [numerical-testing](../../references/workflow/numerical-testing.md) for a reference case,
invariant, or convergence check. Apply its [tolerance rule](../../references/workflow/numerical-testing.md#tolerances)
before diagnosing a missed limit.

For [test, CI, or run failures](../../references/workflow/failure-triage.md#triage-test-ci-and-run-failures),
apply the shared triage rule. For a numerical case, reproduce the disagreement
with the narrowest runnable command.
Record the exact case, inputs, units, basis, model and method versions,
expected behavior, metric, tolerance, observed result, solver termination reason,
residuals, feasibility, and retained output.

Use [failure-triage](../../references/workflow/failure-triage.md) to decide whether the method returned a useful numerical
result and to bound what an incomplete case can establish. Rank a small set of
falsifiable explanations, test them with bounded probes, and preserve the exact
stopping point and diagnostics without imposing a fixed record template.
Use disposable probes until the cause or accepted correction boundary is
established. Follow [fix before a negative disposition](../../references/workflow/failure-triage.md#fix-before-a-negative-disposition)
for the required evidence and [Build's retention rule](../build/SKILL.md#result-retention)
when a correction would change how results are saved.
Route an established correction to `cse:design`; route an
unresolved scientific disagreement to the smallest additional probe.
