# Failure triage

## Triage test, CI, and run failures

Record the exact failure signature and the command, inputs, and revision
needed to identify it. Reproducing the same failure on the base only clears
the change as its cause. A passing rerun alone leaves the failure unexplained.

Show causal evidence before calling a failure flaky, pre-existing, unrelated,
environmental, a one-off, or a precision limit. Use evidence such as grouped
tracebacks, matched timestamps, an alternate start, or a different formulation
to distinguish causes. Keep unexplained failures open with their signatures.
State the hypothesis and what would distinguish it before each retry.

## Require a useful numerical result

Preserve the exact input, stopping point, and diagnostic in the
natural output of the analysis.

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

Close a negative numerical disposition only with evidence that the case lies
outside the stated physical domain or that diagnosis and a bounded root-cause
fix attempt showed no feasible correction. Report only values actually computed.
Keep valid partial results under
[Build's retention rule](../../skills/build/SKILL.md#result-retention) and
report useful values under [Tolerances](numerical-testing.md#tolerances).
A [review verdict](../../skills/review/SKILL.md#claim-verdicts) can record a
decisive miss while the cause remains open.

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

## Run cost plausibility

Before an expensive fit, sweep, engine build, or other run, estimate elapsed
time from a small representative timed probe or comparable prior runs. State
the evidence, workload, scaling assumptions, and uncertainty in the existing
task record. Check whether the estimate itself is plausible for the work; a
slow prior run is not sufficient justification.

Treat an expected or observed duration far beyond that estimate, or beyond
what the work plausibly needs, as a defect to diagnose before launching or
continuing the full run. Use bounded profiling to locate repeated work,
avoidable rebuilds, or a costly numerical step. Reuse an engine or wheel
already built for the current source and compatible build settings and
environment.

Revise the estimate only with evidence. Do not merely extend the wait or
relax scientific checks. An unexpectedly slow run needs diagnosis even when
its numerical result is useful; runtime alone does not invalidate that result.
