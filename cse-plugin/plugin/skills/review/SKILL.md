---
name: review
description: "CSE Review — Independently assess design readiness or delivered scientific evidence."
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
table-only exceptions, activate the rule's owner, `scientific-projects`.

**Capability lens —** inspect the final implementation tree, complete changed functions,
and direct callers and callees using `code-surface-review`. Check
that calculations stay with the accepted numerical owner; each result field
has a named meaning, producer, unit or basis, and availability rule; distinct fields do not reuse one value without identity evidence; missing inputs and silent exits preserve causes and valid outputs; and repeated constants,
limits, defaults, and tolerances use their existing scientific owner. Confirm
the accepted falsifier fails without the fix. Passing tests or line accounting
cannot replace these checks.

Review advises on the stated use; it does not promote a notebook to manuscript
use. Optional hardening does not expand accepted scope. A correction invalidates
the affected final-tree conclusion and requires the complete applicable lens
again; preserve still-valid evidence.
