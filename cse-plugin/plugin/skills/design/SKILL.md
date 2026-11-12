---
name: design
description: "Define and hand off a scientific plan: question, model, method, correctness checks, comparisons a result is reported against, and claim limits. Use when acting as a scientific design sub-agent, or planning a numerical study, model change, or scientific-tool correction (\"plan this study\")."
metadata:
  cse-kind: "workflow"
  cse-family: "workflow"
  cse-order: "03"
  cse-tags: "workflow"
  cse-routing:
    direct: [operating-model, scientific-method]
    conditional: [code-surface-review, github-and-git, decision-records, dependent-scientific-changes, numerical-testing]
---

# Design work

Read first: [operating-model](../../references/workflow/operating-model.md), [scientific-method](../../references/workflow/scientific-method.md).

Activate [code-surface-review](../../references/workflow/code-surface-review.md) for executable changes, replacement, or
deletion; establish its task budget before Build. Activate [decision-records](../../references/workflow/decision-records.md) for
a consequential alternative and [dependent-scientific-changes](../../references/workflow/dependent-scientific-changes.md) for real leaf
dependencies. Activate [github-and-git](../../references/workflow/github-and-git.md) when tracker publication or Git state is part of the
endpoint.

Define the question, model, assumptions, inputs, domain, method, sources,
reference cases, outputs, claims, limitations, and checks. Name a correctness
check where code correctness is at stake and the comparisons a result will be
reported against; do not invent an acceptance number for agreement with data
(see the [limit-origin rule](../../references/workflow/numerical-testing.md#tolerances)). Preserve
a physical finding that meets the [fix-before-negative rule](../../references/workflow/failure-triage.md#fix-before-a-negative-disposition). Trace each changed responsibility from public input
through mapping, numerical owner, result, failure, and output; restore accepted
ownership and failure meaning in the same issue.

Apply the shared [decision-frontier rule](../../references/workflow/operating-model.md#decision-frontier-handoff-and-reference-reuse) to question, method, scope, and
checks before Build; settled Design proceeds under authority without ritual
gate.

## Choose the work plan shape

Use a task's selected result or a capability shape when it settles the task. Only
otherwise map repository role: `analysis` → result, `tool` → capability. A
task-level opposite shape remains valid.

- **Experiment plan (result):** question, model, inputs, domain or sweep,
  named comparisons for the result, expected notebook outputs, and claim
  limits. It ends at Summarize and Review under the Result lens.
- **Tool plan (capability):** defect or missing capability stated as a
  correctness check with input, expected value or relation, tolerance and its
  origin, source, existing owner, passing reference cases, and what gets
  removed. It ends when that check and the reference cases pass under the
  Capability lens. Do not add
  software-product concerns to this shape.

The plan resolves consequential scientific and architectural decisions and
specifies the existing owners, interfaces, implementation sequence, numerical
checks, and stop conditions sufficiently for Build. Include equations,
algorithms, or pseudocode when they remove a real ambiguity. Leave ordinary
local coding choices to Build; do not prescribe unnecessary abstractions or
prewrite the implementation.

## Pre-Build review

Invoke `cse:review` for an independent design-readiness checkpoint against the
proposed plan. Review owns the readiness criteria and returns **Ready**,
**Revise**, or **Block**. Design resolves required findings and records one
concise disposition; only **Ready** permits Build. Reuse still-valid evidence
and refresh only conclusions affected by a material correction.

Activate [github-and-git](../../references/workflow/github-and-git.md) for plan
publication. When a tracker exists, publish the complete accepted plan through
the origin host's tracker and read it back before Build. When none exists, use
the reference's no-tracker handoff. The current accountable task performs
authorized publication.
