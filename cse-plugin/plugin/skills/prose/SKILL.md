---
name: prose
description: "Inspect scientific writing read-only. Use when checking clarity, banned language, revision meaning, a rejected draft, a manuscript that reads like a report and needs restructuring, or final cohesion. Routine wording or citation edits go to write; claim support to review."
metadata:
  cse-kind: "supporting"
  cse-family: "supporting"
  cse-tags: "writing-inspection"
  cse-routing:
    direct: [operating-model, scientific-writing, BANNED]
    conditional: []
---

# Inspect scientific prose

Read first: [operating-model](../../references/workflow/operating-model.md), [scientific-writing](../../references/workflow/scientific-writing.md), [BANNED](../../BANNED.md).

Identify the exact paragraph, section, manuscript, report, reviewer response, or
original-and-revision pair and apply the shared rules in [scientific-writing](../../references/workflow/scientific-writing.md).
For a new or rejected manuscript, journal retarget, or material restructure, use its manuscript structure review.
Default to inspection only. For file-backed input, run the existing deterministic
prose check with available repository and personal authorities before semantic
inspection. For pasted text without a declared repository-relative path, state
that path-scoped rules were not checked and create no surrogate file.

Report the smallest exact span, `required correction` or `contextual judgment
call`, rule source, and scientific or communication consequence. Preserve the
legitimate academic usages and protected scientific meaning named by the shared
reference. Do not infer authorship, emit an AI probability or detector score,
or claim that semantic equivalence has been proved. Route unresolved scientific
support to Review's Result lens and unresolved source authority to Research.

When no routine finding remains, return `CSE prose is clear.` If the user asks
for corrections, route them to `cse:write`; Prose does not edit. Write may
request one verification inspection after its minimum effective change.

For an explicit final manuscript check, inspect the authoritative assembled
source and use the source-identity, complete identifier coverage,
sentence-to-paragraph-to-section judgments, and argument-spine checkpoint in
[scientific-writing](../../references/workflow/scientific-writing.md). Return **Revise** with exact identifiers for stale
identity, missing coverage, or unresolved weak or broken relationships. The
routine clear message is not a final-check result.
