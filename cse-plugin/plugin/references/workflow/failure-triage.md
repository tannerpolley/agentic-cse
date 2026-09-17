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

An input-readiness question may end with a supported input rejection. That
answers only the readiness question: it establishes no model behavior and
does not justify a results notebook.

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
