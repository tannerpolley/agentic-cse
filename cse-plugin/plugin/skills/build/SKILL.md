---
name: build
description: "Implement an agreed scientific model, numerical method, data transformation, or manuscript correction from an accepted Design handoff. Use when implementing a scientific issue as a sub-agent, or asked to \"code this model\". An unexplained numerical failure goes to diagnose first."
metadata:
  cse-kind: "workflow"
  cse-family: "workflow"
  cse-order: "04"
  cse-tags: "workflow"
  cse-routing:
    direct: [operating-model, code-surface-review]
    conditional: [scientific-method, numerical-testing, failure-triage, github-and-git, cse-pi-worker]
---

# Build methods

Read first: [operating-model](../../references/workflow/operating-model.md), [code-surface-review](../../references/workflow/code-surface-review.md).

Activate [scientific-method](../../references/workflow/scientific-method.md) for equations, conventions, or validity;
[numerical-testing](../../references/workflow/numerical-testing.md) for the result-level reference or invariant; and
[failure-triage](../../references/workflow/failure-triage.md) when failures or incomplete cases are in scope. Activate
[github-and-git](../../references/workflow/github-and-git.md) for
the issue, branch, or integration authority.

Use the accepted Design handoff as authority. Inspect its formulation,
reference case, implementation, callers, evidence, authority, and Git state.
When it points to a tracker issue, inspect the complete current issue body,
relevant comments, and amendments with the origin-host command in
[github-and-git](../../references/workflow/github-and-git.md). For long issues,
follow pagination; do not implement from search excerpts, summaries, or stale
copies. Recheck the issue before final handoff and after an interruption.
Accepted amendments replace superseded body instructions; comments do not
silently override them.

Establish the result-level expectation before editing; preserve units, bases,
uncertainty, scientific safeguards, and failure meaning. A failing numerical
case authorizes no new numerical method, tolerance, bound, start, retry,
fallback, or search budget; `cse:diagnose` classifies the cause first. A
demonstrated contradiction or missing consequential decision returns the exact
question and evidence to its owner and pauses only dependent work. Build may
make routine local coding choices but does not select new physics, inputs,
methods, tolerances, or owners.

Implement only accepted policy, remove superseded paths, and add only checks
that protect a distinct risk. Report the changed surface, focused validation,
and one change-accounting run against the final tree and active base. The stage
performing a Git or tracker action owns its authority and records the resulting
state in its handoff.

Activate [cse-pi-worker](../../references/workflow/cse-pi-worker.md) only when a bounded Build worker adds value. Freeze the
accepted specification and permitted paths. Use the host's native delegation
when it supports the worker integration; otherwise use the CLI, as that
reference describes. Inspect the retained candidate diff and rerun important
validation before any separate source application.
Worker output is evidence, never parent acceptance.

If the correction boundary is not established, return to `cse:diagnose` before
editing. Continue to `cse:analyze` when numerical evidence must be regenerated.
