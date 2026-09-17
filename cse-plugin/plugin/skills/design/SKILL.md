---
name: design
description: "CSE Research and design — Decide whether scientific work is a result or capability, define its bounded issue, and publish it before implementation when required."
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

Activate `code-surface-review` for executable changes, replacement, or
deletion; establish its task budget before Build. Activate `decision-records` for
a consequential alternative and `dependent-scientific-changes` for real leaf
dependencies. Activate `github-and-git` when issue or Git state is part of the
endpoint.

Define the question, model, assumptions, inputs, domain, method, sources,
reference cases, tolerances, outputs, claims, limitations, and checks. Preserve
a supported negative result. Trace each changed responsibility from public input
through mapping, numerical owner, result, failure, and output; restore accepted
ownership and failure meaning in the same issue.

Apply the shared decision-frontier rule to question, method, scope, and
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

When the repository uses GitHub issues, activate `github-and-git`, publish the
complete accepted plan, and read it back before Build. In baton mode, the
Architect supplies the issue-ready specification and the Manager performs the
authorized publication. A draft, chat summary, or reviewer opinion is not the
published handoff.
