---
name: design
description: "Define and publish the bounded issue for scientific work: question, model, method, reference case, tolerance, falsifier, and claim limits. Use when planning a study, model change, or tool fix before implementation (\"plan this study\", \"write the issue for this\")."
metadata:
  cse-kind: "workflow"
  cse-family: "workflow"
  cse-order: "03"
  cse-tags: "workflow"
  cse-routing:
    direct: [operating-model, scientific-method]
    conditional: [code-surface-review, github-and-git, decision-records, dependent-scientific-changes]
---

# Design work

Read first: [operating-model](../../references/workflow/operating-model.md), [scientific-method](../../references/workflow/scientific-method.md).

Activate [code-surface-review](../../references/workflow/code-surface-review.md) for executable changes, replacement, or
deletion; establish its task budget before Build. Activate [decision-records](../../references/workflow/decision-records.md) for
a consequential alternative and [dependent-scientific-changes](../../references/workflow/dependent-scientific-changes.md) for real leaf
dependencies. Activate [github-and-git](../../references/workflow/github-and-git.md) when issue or Git state is part of the
endpoint.

Define the question, model, assumptions, inputs, domain, method, sources,
reference cases, tolerances, outputs, claims, limitations, and checks. Preserve
a physical finding that meets the [fix-before-negative rule](../../references/workflow/failure-triage.md#fix-before-a-negative-disposition). Trace each changed responsibility from public input
through mapping, numerical owner, result, failure, and output; restore accepted
ownership and failure meaning in the same issue.

Apply the shared [decision-frontier rule](../../references/workflow/operating-model.md#decision-frontier-handoff-and-reference-reuse) to question, method, scope, and
falsifier before Build; settled Design proceeds under authority without ritual
gate.

## Choose the issue shape

Use a task's selected result or a capability shape when it settles the task. Only
otherwise map repository role: `analysis` → result, `tool` → capability. A
task-level opposite shape remains valid.

- **Experiment issue (result):** question, model, inputs, domain or sweep,
  independent reference comparison, expected notebook outputs, and claim
  limits. It ends at Summarize and Review under the Result lens.
- **Tool issue (capability):** defect or missing capability stated as a
  numerical falsifier with input, expected value or relation, tolerance, source,
  existing owner, passing reference cases, and what gets removed. It ends when
  the falsifier and reference cases pass under the Capability lens. Do not add
  software-product concerns to this shape.

The issue resolves consequential scientific and architectural decisions and
specifies the existing owners, interfaces, implementation sequence, numerical
checks, and stop conditions sufficiently for Build. Include equations,
algorithms, or pseudocode when they remove a real ambiguity. Leave ordinary
local coding choices to Build; do not prescribe unnecessary abstractions or
prewrite the implementation.

## Pre-Build review

Invoke `cse:review` for an independent design-readiness checkpoint against the
proposed issue. Review owns the readiness criteria and returns **Ready**,
**Revise**, or **Block**. Design resolves required findings and records one
concise disposition; only **Ready** permits Build. Reuse still-valid evidence
and refresh only conclusions affected by a material correction.

When the repository uses GitHub issues, activate [github-and-git](../../references/workflow/github-and-git.md), publish the
complete accepted plan, and read it back before Build. In baton mode, the
Architect supplies the issue-ready specification and the Manager performs the
authorized publication. A draft, chat summary, or reviewer opinion is not the
published handoff.
