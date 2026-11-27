---
name: review
description: "Independently check scientific design readiness (Ready, Revise, Block) or delivered numerical results and scientific code (Supported, Not supported). Use when reviewing scientific work as a sub-agent, or asked \"is this result supported\". Writing quality goes to prose."
metadata:
  cse-kind: "workflow"
  cse-family: "workflow"
  cse-order: "07"
  cse-tags: "workflow"
  cse-routing:
    direct: [operating-model]
    conditional: [code-surface-review, scientific-method, numerical-testing, failure-triage, scientific-writing, writing-editorial, manuscript-review, analysis-sets, dependent-scientific-changes, slide-decks]
---

# Review scientific work

Read first: [operating-model](../../references/workflow/operating-model.md).
Activate [scientific-method](../../references/workflow/scientific-method.md) for disputed equations or validity
and its [model adoption and comparison rule](../../references/workflow/scientific-method.md#model-adoption-and-comparison) for model choices,
[numerical-testing](../../references/workflow/numerical-testing.md) for reference cases and its [tolerance rule](../../references/workflow/numerical-testing.md#tolerances) when a limit is in question,
[failure-triage](../../references/workflow/failure-triage.md) for incomplete cases or [test, CI, or run failures](../../references/workflow/failure-triage.md#triage-test-ci-and-run-failures), and
[dependent-scientific-changes](../../references/workflow/dependent-scientific-changes.md) for leaf dependencies.

Review is independent of the two execution phases and occurs at two moments.
Use a fresh reviewer for design readiness before Build and a separate fresh
reviewer for delivered acceptance. Neither reviewer authored the material it
checks. CSE requires independence but selects no model, transport, staffing
pattern, or review cascade; the active coordination guidance owns those choices.
The [manuscript structure review](../../references/workflow/manuscript-review.md#manuscript-structure-review) specifies independent review jobs; host guidance assigns them.

## Design readiness

Inspect the proposed plan and decisive evidence for scientific justification
and unnecessary complexity. Check the named numerical owner; question and
intended use; equations or method; inputs, units, domain,
and assumptions; independent reference case or falsifiable relation; metric,
tolerance origin, and named comparisons for agreement with data; runnable checks; failure meaning; provenance, uncertainty,
claim limits, complete changed surface, removal, and integration as applicable.
An instruction-only change uses observable routing and preservation checks, not
invented numerical targets. Return **Ready**, **Revise**, or **Block** with the
affected owner, evidence, smallest correction, and checks to refresh. Passing
tests, line accounting, or a smaller diff cannot replace scientific support.

## Delivered review

Read the exact delivered result or capability from the project's `CONTEXT.md`
default and confirm it from the work at hand. If the implementer requests the
review, use a separate read-only reviewer against the identified final commit or
frozen tree and explicit merge base. If independent delegation is unavailable,
report the review as pending. Apply [claim verdicts](#claim-verdicts) in both
lenses.

**Result lens —** inspect the complete research notebook, retained values, and
selected renders. Establish whether each claim follows from the numbers,
provenance, units, uncertainty, and intended-use limits. For figures and
table-only exceptions, activate the rule's owner, [analysis-sets](../../references/workflow/analysis-sets.md).
Flag as **disproportion**, named as false precision, bikeshedding, or
gold-plating, any stop, gate, rerun, or claim that rests on an
[immaterial difference](../../references/workflow/numerical-testing.md#fitness-for-purpose),
such as "not converged" from an objective tolerance while the parameters are
unchanged at their standard error; the correction is to delete it, move it to
the record, or state it once.

For manuscripts/decks, the Result lens activates the
[standing decisions](../../references/workflow/writing-editorial.md#standing-editorial-decisions),
[editorial compliance](../../references/workflow/writing-editorial.md#editorial-compliance), and
[manuscript reference coverage](../../references/workflow/manuscript-review.md#manuscript-reference-coverage).
For a manuscript, also ask whether a reader could rebuild the calculation from the paper ([methods reproducibility](../../references/workflow/scientific-writing.md#methods-reproducibility)).
Ask whether each manuscript input-to-output result has its [conditions table and result plot](../../references/workflow/scientific-writing.md#argument).
At a deck's final checkpoint, inspect it read-only against [slide-decks](../../references/visualize/slide-decks.md) and the project's deck decisions.

**Capability lens —** inspect the final implementation tree, complete changed functions,
and direct callers and callees using [code-surface-review](../../references/workflow/code-surface-review.md). Check
that calculations stay with the accepted numerical owner; each result field
has a named meaning, producer, unit or basis, and availability rule; distinct fields do not reuse one value without identity evidence; and repeated constants,
limits, defaults, and tolerances use their existing scientific owner. Apply Build's
[result retention rule](../build/SKILL.md#result-retention) to every changed
path that produces, maps, or saves results, including refusals. Confirm
the accepted correctness check fails without the fix. Passing tests or line accounting
cannot replace these checks.

### Claim verdicts

Give each claim or component its own verdict, with evidence, limitations,
required corrections, and the next stage. Record each applicable gate as
**pass**, **decisive miss**, or **unresolved**. Apply
[Tolerances](../../references/workflow/numerical-testing.md#tolerances) before
using a missed limit as evidence against a claim.

Use **Supported** where the evidence establishes the stated claim and
**Not supported** only where the evidence shows that claim fails. Mark a verdict
**pending** when unresolved evidence prevents a decision. Keep independently
supported claims visible and list wording-only changes as required corrections.
For a proposed negative numerical disposition, or a limit, narrowing, or
provisional label resting on a numerical non-result, apply
[failure-triage](../../references/workflow/failure-triage.md#fix-before-a-negative-disposition).

Review advises on the stated use; it does not promote a notebook to manuscript
use. Optional hardening does not expand accepted scope. A correction invalidates
the affected final-tree conclusion and requires the complete applicable lens
again; preserve still-valid evidence.

For source, figure, and deck identifier advisories, follow the shared
[reader-facing identifier check](../../references/workflow/writing-editorial.md#reader-facing-identifiers).
