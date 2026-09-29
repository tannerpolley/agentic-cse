---
name: review
description: "Independently check a design issue before build (Ready, Revise, Block) or delivered results or code (Supported, Not supported). Use when acting as a reviewer or review sub-agent, or asked to \"review this plan\", \"is this result supported\", or \"review this change\". Writing quality goes to prose."
metadata:
  cse-kind: "workflow"
  cse-family: "workflow"
  cse-order: "07"
  cse-tags: "workflow"
  cse-routing:
    direct: [operating-model]
    conditional: [code-surface-review, scientific-method, numerical-testing, failure-triage, scientific-projects, dependent-scientific-changes]
---

# Review scientific work

Read first: [operating-model](../../references/workflow/operating-model.md).
Activate [scientific-method](../../references/workflow/scientific-method.md) for disputed equations or validity,
[numerical-testing](../../references/workflow/numerical-testing.md) for reference cases or tolerances,
[failure-triage](../../references/workflow/failure-triage.md) for failed or incomplete cases, and
[dependent-scientific-changes](../../references/workflow/dependent-scientific-changes.md) for leaf dependencies.

Review is independent of the two execution phases and occurs at two moments.
Use a fresh reviewer for design readiness before Build and a separate fresh
reviewer for delivered acceptance. Neither reviewer authored the material it
checks. CSE requires independence but selects no model, transport, staffing
pattern, or review cascade; the active coordination guidance owns those choices.

## Design readiness

Inspect the proposed issue and decisive evidence for scientific justification
and unnecessary complexity. Check the named numerical owner; question and
intended use; equations or method; inputs, units, domain,
and assumptions; independent reference case or falsifiable relation; metric and
justified tolerance; runnable checks; failure meaning; provenance, uncertainty,
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
report the review as pending. Return
**Supported** or **Not supported**, the limitations, required corrections, and
the next stage: Write, Diagnose, Research, Design, or stop.

**Result lens —** inspect the complete research notebook, retained values, and
selected renders. Establish whether each claim follows from the numbers,
provenance, units, uncertainty, and intended-use limits. For figures and
table-only exceptions, activate the rule's owner, [scientific-projects](../../references/workflow/scientific-projects.md).

**Capability lens —** inspect the final implementation tree, complete changed functions,
and direct callers and callees using [code-surface-review](../../references/workflow/code-surface-review.md). Check
that calculations stay with the accepted numerical owner; each result field
has a named meaning, producer, unit or basis, and availability rule; distinct fields do not reuse one value without identity evidence; missing inputs and silent exits preserve causes and valid outputs; and repeated constants,
limits, defaults, and tolerances use their existing scientific owner. Confirm
the accepted falsifier fails without the fix. Passing tests or line accounting
cannot replace these checks.

For any refused, failed, unavailable, unresolved, tolerance-gated, or negative
disposition in either lens, ask whether it could be fixed: return **Not
supported** unless the retained evidence shows the diagnosis and attempted
root-cause fix required by
[failure-triage](../../references/workflow/failure-triage.md#fix-before-a-negative-disposition).

Review advises on the stated use; it does not promote a notebook to manuscript
use. Optional hardening does not expand accepted scope. A correction invalidates
the affected final-tree conclusion and requires the complete applicable lens
again; preserve still-valid evidence.
