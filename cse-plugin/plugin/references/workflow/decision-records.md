# Science-first decision records

Use a scientific decision record only when all four conditions hold:

1. changing the decision later has meaningful cost;
2. a future scientific developer cannot recover the reason from code and
   equations alone;
3. genuine alternatives were considered; and
4. the choice materially affects formulation, numerical behavior, scientific
   validity, reproducibility, ownership, interfaces, or retained evidence.

A reversible library choice does not pass this threshold. A numerical-method
choice that fixes an algorithm, independent reference case, and tolerance
rationale normally does. Offer the record; the authorized scientific owner
accepts the scientific judgment.

An analysis-local fit, transform, uncertainty estimate, or figure choice fully
owned by one accepted Design issue, its equations, and its implementation does
not need a separate record when it creates no shared default, public interface,
reusable solver, cross-analysis owner, or hard-to-reverse dependency.

## One owner and sequence

Store accepted records only under `docs/scientific/decisions/` in one numbered sequence
across all kinds. Use names such as `0001-one-equation-owner.md`.
Kinds do not create separate sequences. Superseded records stay in Git, link to
the replacement, and their numbers are never reused.

Every record starts with a title and states its `Kind:`. It records five facts:
the consequential setting, genuine alternatives, selected choice, evidence,
and validity boundary. Status, supersession, consequences, and verification
sections are optional until their information is needed.

The repository owns each decision and its scientific basis. CSE may expose a
contradiction and block completion, but it does not arbitrate scientific truth.

Setup establishes or migrates the one accepted record owner. Design reads
applicable records and includes a new or superseding record in the issue only
when the threshold is met. Build reads them before editing and returns a
conflict to Design and the authorized scientific owner. Review checks the
implementation, numerical evidence, and generated views against them; solver
convergence alone cannot establish compliance.
