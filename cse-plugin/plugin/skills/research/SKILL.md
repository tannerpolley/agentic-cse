---
name: research
description: "Find and assess scientific sources, equations, correlations, data, and numerical methods. Use when acting as a scientific research sub-agent, or asked \"find the paper for this correlation\" or \"is this equation valid here\". Zotero library work goes to zotero; datasets to data."
metadata:
  cse-kind: "workflow"
  cse-family: "workflow"
  cse-order: "02A"
  cse-tags: "workflow"
  cse-routing:
    direct: [operating-model, scientific-method]
    conditional: []
---

# Research sources

Read first: [operating-model](../../references/workflow/operating-model.md), [scientific-method](../../references/workflow/scientific-method.md).

Use `cse:zotero`,
`cse:data`, or `cse:digitize` after checking the requested external capability
owns the unresolved source operation.

## Investigate

Apply the shared [decision-frontier rule](../../references/workflow/operating-model.md#decision-frontier-handoff-and-reference-reuse) after inspection to source applicability
and any unresolved evidence choice.

Confirm the claim or decision, intended use, source standard, domain limits,
and endpoint. Search an applicable local corpus with a bounded,
capability-aware plan; stop when the source question is answered, the corpus
is unavailable, or further results would not discriminate a real uncertainty.
Add a query only when it tests a named unresolved source question. Do not use a
fixed command or query count as a substitute for that stopping condition.

Prefer primary literature, standards, accepted experiments, analytic
derivations, and authoritative documentation. Record exact locators, equations,
units, bases, assumptions, validity bounds, transformations, and limitations.
Compare conflicting sources by model, convention, data, and intended use.
Core Research may use repository evidence, user-provided sources, and approved
ordinary research routes without a source tool. If a required Zotero, Mathpix,
lineage, or digitization capability is absent, report the exact missing
executable, corpus, or authentication rather than a scientific failure. Add each
relevant paper missing from the library through `cse:zotero` acquisition without
asking; other Zotero writes keep their approval route.

## Continue

Return findings, evidence quality, limitations, unresolved choices, and acquired
Zotero keys or hand-off links. Answer
directly for research-only work; otherwise route accepted sources to
`cse:design` without stopping merely because sources were found.
