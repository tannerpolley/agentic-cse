---
name: build
description: "CSE Execute and deliver — Implement an agreed scientific model, method, data transformation, or document correction."
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

Activate `scientific-method` for equations, conventions, or validity;
`numerical-testing` for the result-level reference or invariant; and
`failure-triage` when failures or incomplete cases are in scope. Activate
`github-and-git` for
the issue, branch, or integration authority.

Inspect the complete current issue body, relevant comments and amendments,
formulation, reference case, implementation, callers, evidence, authority, and
Git state. For long issues, continue past truncated output and follow pagination;
do not implement from a search excerpt, summary, or stale local copy. Recheck
the issue before final handoff and after an interruption. Accepted amendments
replace superseded body instructions; comments do not silently override them.

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
performing a Git or GitHub action owns its authority and records the resulting
state in its handoff.

Activate `cse-pi-worker` only when a bounded Build worker adds value. Freeze the
accepted specification and permitted paths; inspect the retained candidate
diff and rerun important validation before any separate source application.
Worker output is evidence, never parent acceptance.

If the correction boundary is not established, return to `cse:diagnose` before
editing. Continue to `cse:analyze` when numerical evidence must be regenerated.
