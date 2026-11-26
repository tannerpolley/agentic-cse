---
name: audit
description: "Audit scientific repos and owner history read-only: ceremony, duplicated values, misplaced records, unsourced names, untraced limits. Use when asked \"what can I delete\", \"audit this repo\", \"audit owner history\", or \"find hard-coded tolerances\". Scientific support goes to review; writing to prose."
metadata:
  cse-kind: "supporting"
  cse-family: "supporting"
  cse-tags: "audit"
  cse-routing:
    direct: [operating-model, BANNED]
    conditional: [retrospective, numerical-testing]
---

# Audit CSE practice

Read first: [operating-model](../../references/workflow/operating-model.md), [BANNED](../../BANNED.md).
When inspecting limits, read [Tolerances](../../references/workflow/numerical-testing.md#tolerances), the sole limit-origin rule owner.

For a requested session retrospective, read [retrospective](../../references/workflow/retrospective.md)
and use its science categories. If `/retro` is available, pair it with those
categories. For a requested cross-session or owner-history audit, follow
[Cross-session history audit](../../references/workflow/retrospective.md#cross-session-history-audit)
and use that section’s report, without cleanup removal estimates. Report
candidates only; change nothing until the user picks one.

For an ordinary audit, inspect the requested repository or folder read-only. This is a CSE-practice
audit, not scientific Review: judge whether the work stays centered on the
question, model, method, calculation, retained values, numerical behavior, and
interpretation. Do not grade scientific truth or apply edits.

Inspect active source, tests, instructions, configuration, analyses, and documentation. Skip vendored, generated, cache, and historical result archives
unless the user includes them. Use `rg`, file and row counts, callers, and Git
history when ownership or origin is unclear. Project vocabulary belongs in
root `GLOSSARY.md` or the glossaries linked by `GLOSSARY-MAP.md`,
not glossary tables in the scientific context. Scoped or exception-bearing
writing rules belong in `CONTEXT.md` under `## Prose avoid rules`.
Inspect `Source:` lines; missing or `sourceless` sources remain findings. Shared glossary files are not duplicate CSE records to remove.

Hunt for:

- `replace`: durable names or glossary terms without a domain source, unless
  the name is the quantity, equation, or operation itself; propose the precise
  scientific name and source without renaming code during this audit;
- duplicated scientific values or whole result tables retained under multiple
  owners;
- scientific calculations or transformations outside the designated owner;
- result mapping that duplicates, fabricates, drops, or changes the meaning of a produced value; silent exits that erase failure or unavailability causes;
- duplicated equations, physical limits, constants, defaults, or tolerances;
- numerical limits with no traced origin, using the procedure below;
- semantically distinct fields populated from one source without identity evidence;
- unique values, inputs, provenance, or interpretation stored under the wrong
  owner;
- lifecycle paperwork, pass/fail records, dead templates, wrappers, flags, and
  configuration with no scientific or user-facing reader;
- software-oriented checks or process-first notebooks that replace an actual
  calculation, result table, diagnostic, uncertainty, or interpretation;
- disproportion: owner questions, stage stops, gates, or reruns whose options
  or outcomes differed by less than the
  [materiality scale](../../references/workflow/numerical-testing.md#fitness-for-purpose); and
- existing generators, templates, or check seams that repeatedly recreate or
  permit the same problem.

## Trace numerical limits

Inventory active languages; search semantic names (tol, eps, max_iter, bounds,
floors, ceilings, cutoffs, retries) and control sites: comparisons, loops/ranges,
solver arguments/defaults, min/max/clip, and numeric tables. Include integers
such as 7, signed/scientific notation, expressions, and named/default/derived
values controlling convergence, counts, bounds, clipping, or thresholds.
Searches yield candidates; read surrounding functions and trace definitions,
configuration overrides, and consumers with available code-navigation tools.

For each candidate, establish quantity/units where discoverable, actual stopping
or admission predicate, definition/use sites, and the record supporting that
value for that use. Follow comments, policy entries, upstream expressions,
methods/equations, source locators, and owner decisions. A name, constants file,
issue number, source field, or nearby citation alone is insufficient; inspect
the evidence and applicability, including every derived multiplier.

Apply the linked rule: distinguish **traced limit** (applicable origin and exact
locator; provenance, not scientific endorsement), **untraced limit** (say “no
named origin found in the inspected scope,” with searched evidence and missing
justification), and **unresolved** (ambiguous role or unavailable evidence;
retain `investigate` and name what is missing). Documented guesses/provisional
values remain visible, not justified by being recorded. Establish physical
constants' roles, units, and sources where present; exclude ordinary equation
constants and unit conversions from untraced-limit findings. Equation-imposed
domain bounds are limits traced to their derivation; physical constants do not
justify unexplained threshold multipliers. Report evidence without replacement
numbers, automatic safeguard changes, or scientific correctness verdicts.

## Report

For cleanup suggestions, establish the actual owner and readers or callers,
whether the suspect path contains unique scientific values, the duplication or
absence evidence, the exact authoritative destination or replacement, and the
smallest check that proves preservation. For a repeated problem, identify the
single existing generator or check seam that should prevent reintroduction.
File size, wording, or a familiar software pattern alone is not proof. Use
`investigate` when ownership remains unresolved and name the exact missing
evidence.

Preserve exact build-system requirements, real data structures, named external
limits, source provenance, units, numerical safeguards, method diagnostics,
uncertainty, and approved persistent behavior checks when they serve an actual
need. An exact official filename or code identifier is not a finding by itself.

Group cleanup findings by the root generator or ownership mistake. Rank scientific
displacement first, then estimated removable files or lines; put wording-only
findings last. Use these tags:

- `delete`: remove administrative machinery with no scientific value;
- `dedupe`: retain one authoritative copy and derive any secondary view;
- `move`: relocate unique values to their scientific owner;
- `replace`: substitute an actual calculation, result table, diagnostic, or
  notebook interpretation for software ceremony;
- `prevent`: change one existing generator or check seam that caused repeated
  findings;
- `keep`: record why a tempting construct is scientifically necessary; and
- `investigate`: state missing origin or unresolved ownership/tracing evidence.

Write each cleanup finding on one line:

`tag: <evidence>; <exact action, authoritative owner, and preservation check>. <estimated files or lines removed>. [paths]`

Add a separate limits section grouped by definition file (use file for inline
literals), combining repeated uses and citing consumers. Use `investigate` for
untraced/unresolved limits and `keep` for traced exclusions:

`tag: <definition path:line>; <symbol, literal/expression, resolved value if available>; <use path:line and effect>; <trace classification>; <origin locator or searched/missing evidence>.`

Briefly summarize traced and physical-constant exclusions with representative
evidence. Limits need no removal estimate or deletion recommendation.

End with inspected scope/exclusions and unresolved tracing. For cleanup, include
`net:` estimates of files/lines removed or renamed, unique values preserved or
moved, and unresolved investigations. Report no score, compliance state, audit
JSON, or new audit machinery. A limits-only audit without findings says “no
untraced limits found in the inspected scope.” Say `CSE practice is lean.` only
for a completed ordinary cleanup audit without material findings; never give an
all-clear with unchecked files or origins. When implementation is requested,
route grouped findings to `cse:design` as one bounded plan proposal.
