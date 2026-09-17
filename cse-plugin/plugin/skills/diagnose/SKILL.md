---
name: diagnose
description: "CSE Research and design — Establish the cause of an unexplained numerical result or failure before implementation changes."
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

Apply the shared decision-frontier rule after inspection to an unresolved causal
distinction or the smallest bounded next probe.

Activate `scientific-method` when equations, units, basis, validity, or claim
limits are in dispute. Activate `numerical-testing` when a reference case,
invariant, tolerance, or convergence check is needed.
Record the exact case, inputs, units, basis, model and method versions,
expected behavior, metric, tolerance, observed result, solver termination reason,
residuals, feasibility, and retained output. Reproduce the disagreement with
the narrowest runnable command. A skipped case, timeout, subprocess failure,
missing value, or solver message is not evidence that the physical model or
formulation is wrong.

Use `failure-triage` to decide whether the method returned a useful numerical
result and to bound what an incomplete case can establish. Rank a small set of
falsifiable explanations, test them with bounded probes, and preserve the exact
stopping point and diagnostics without imposing a fixed record template.
Do not change implementation, weaken a tolerance, or
reinterpret a claim until the cause or accepted correction boundary is
established. Route an established correction to `cse:design`; route an
unresolved scientific disagreement to the smallest additional probe.
