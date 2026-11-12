---
name: diagnose
description: "Diagnose unexpected scientific or numerical results through reproduction and bounded probes before changing a calculation. Use when asked \"why does my solver diverge\" or \"why doesn't this match the reference\", or about numerical NaNs and non-convergence. Software bugs go to diagnosing-bugs."
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

When a result misses a limit, first trace where the limit came from (file,
commit, issue, or source). If it has no named origin under
[numerical-testing](../../references/workflow/numerical-testing.md#tolerances)
and the number is physically plausible in units, sign, magnitude, trend, and
balances, stop diagnosing and report the result with its error and
comparisons. An implausible number is diagnosed regardless of any limit:
Diagnose is for wrong or missing numbers, not imperfect ones.

Use [failure-triage](../../references/workflow/failure-triage.md) to decide whether the method returned a useful numerical
result and to bound what an incomplete case can establish. Rank a small set of
falsifiable explanations, test them with bounded probes, and preserve the exact
stopping point and diagnostics without imposing a fixed record template.
Do not change implementation, silently loosen a limit with a named origin, or
reinterpret a claim until the cause or accepted correction boundary is
established. Test a candidate root-cause fix, such as scaling, higher
precision, or a better-resolved reference, as a disposable bounded probe that
leaves the retained implementation unchanged, before any negative disposition; a closing negative outcome must meet
[failure-triage](../../references/workflow/failure-triage.md#fix-before-a-negative-disposition).
Route an established correction to `cse:design`; route an
unresolved scientific disagreement to the smallest additional probe.
