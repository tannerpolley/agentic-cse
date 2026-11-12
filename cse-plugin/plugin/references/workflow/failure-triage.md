# Numerical failure triage

A missing value, status flag, successful process exit, or empty plot is not a
model result. Preserve the exact input, stopping point, and diagnostic in the
natural output of the analysis; do not require a key/value failure record.

## Require a useful numerical result

Judge completion by the method that actually ran:

- an iterative solve genuinely converged and returned the relevant values and
  diagnostics;
- a direct calculation evaluated and returned the requested quantity;
- a fit returned parameters and fit statistics appropriate to the question;
- an integration reached its interval or returned a scientifically useful,
  explicitly bounded partial interval; or
- another method returned equivalent values and diagnostics that address the
  question.

Generic success booleans, exit codes, preflight checks, placeholders, and
empty result files do not satisfy this rule. If no useful numerical result
exists, say so, identify the exact stopping point and diagnostic, route the
cause to `cse:diagnose`, and continue with the smallest evidence-driven probe.
Do not report the analysis complete or create a notebook or empty figure.

## Fix before a negative disposition

A result with no useful numerical value, or one that misses a limit with a
[named origin](numerical-testing.md#tolerances), may not close as refused,
failed, unavailable, reference unresolved, limit gated, or a supported
negative result until its cause is diagnosed and a root-cause fix has been
attempted and shown impossible, or the case is shown to lie outside the stated
physical domain, with retained evidence. An imperfect but useful result is not
a negative disposition: report it with its error and comparisons. Never invent
a value to avoid a negative outcome.

- **Physical finding.** A model that, after diagnosis and fix attempts, still
  does not reproduce data is a legitimate scientific result. It carries the
  diagnosis and the fixes tried.
- **Numerical non-result.** A conditioning, precision, solver, or
  reference-resolution failure is a defect to fix, for example by scaling or
  equilibrating the system, raising working precision, iterative refinement, or
  a better-resolved reference. A typed refusal remains only for genuinely
  singular or undefined mathematics, such as a phase or species inserted with
  zero amount, where the logarithm of composition is undefined, or a
  Jacobian that stays singular after scaling, and states why.

Review asks whether the outcome could be fixed, not only whether its label is
honest.

An input-readiness question may end with a supported input rejection. That
answers only the readiness question and is not a numerical disposition: it
establishes no model behavior and does not justify a results notebook.

## Bound the claim

A timeout, skipped case, subprocess failure, missing value, or solver message
does not establish that the formulation or physical model failed. A diagnostic
supports only what it directly identifies. Before generalizing from one case,
run a bounded direct or neighboring-state probe when safe and scientifically
relevant; if that is impossible, state why.

Once at least one useful result exists, failed or incomplete cases may remain
in the retained analysis to bound coverage. Distinguish execution boundaries,
numerical nonconvergence, invalid physical states, and disagreement with a
reference. A longer run is a deliberate numerical experiment, not an
automatic retry.
