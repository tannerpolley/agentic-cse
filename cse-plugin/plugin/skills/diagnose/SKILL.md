---
name: diagnose
description: "Establish the cause of an unexpected numerical result or failure through reproduction and bounded probes, before any code change. Use when asked \"why does my solver diverge\", \"why doesn't this match the reference\", or about NaNs, non-convergence, or a result that looks wrong."
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

Apply the shared [decision-frontier rule](../../references/workflow/operating-model.md#decision-frontier-handoff-and-reference-reuse) after inspection to an unresolved causal
distinction or the smallest bounded next probe.

Activate [scientific-method](../../references/workflow/scientific-method.md) when equations, units, basis, validity, or claim
limits are in dispute. Activate [numerical-testing](../../references/workflow/numerical-testing.md) when a reference case,
invariant, tolerance, or convergence check is needed.
Record the exact case, inputs, units, basis, model and method versions,
expected behavior, metric, tolerance, observed result, solver termination reason,
residuals, feasibility, and retained output. Reproduce the disagreement with
the narrowest runnable command. A skipped case, timeout, subprocess failure,
missing value, or solver message is not evidence that the physical model or
formulation is wrong.

Use [failure-triage](../../references/workflow/failure-triage.md) to decide whether the method returned a useful numerical
result and to bound what an incomplete case can establish. Rank a small set of
falsifiable explanations, test them with bounded probes, and preserve the exact
stopping point and diagnostics without imposing a fixed record template.
Do not change implementation, weaken a tolerance, or
reinterpret a claim until the cause or accepted correction boundary is
established. Test a candidate root-cause fix, such as scaling, higher
precision, or a better-resolved reference, as a disposable bounded probe that
leaves the retained implementation unchanged, before any negative disposition; a closing negative outcome must meet
[failure-triage](../../references/workflow/failure-triage.md#fix-before-a-negative-disposition).
Route an established correction to `cse:design`; route an
unresolved scientific disagreement to the smallest additional probe.
