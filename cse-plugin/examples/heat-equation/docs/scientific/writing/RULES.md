# Deterministic scientific writing rules

## Required

- Use the vocabulary and symbols from `CONTEXT.md`.
- Give every equation, method, and reference object a stable ID.
- State derivation or source status and exact locator when a source exists.
- Put grid conditions, final Fo, reference, metric, tolerance, and numerical
  uncertainty beside every reported numerical result.
- Use `abs(error) <= atol + rtol*abs(reference)` for direct value comparisons
  and justify both terms.
- Keep code verification, solution verification, model validation, and
  numerical uncertainty distinct.
- State that linear stability does not make Crank-Nicolson unconditionally
  monotone.
- Generate the bibliography from Zotero and keep it path-sanitized.

## Forbidden

- Em dashes.
- A measured claim without its retained data and generating calculation.
- Treating a scheme's own amplification factor as a continuous reference.
- Describing Crank-Nicolson as unconditionally monotone.
- A global unexplained epsilon or generic order band.
- Physical validation, material-property claims, experimental claims,
  dimensional prediction, physical input uncertainty, or model-form
  uncertainty.
- Hand editing the generated bibliography.
- Unsupported visual precision or a plot without exact retained plotted data.
