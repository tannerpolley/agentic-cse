---
name: audit
description: "Audit scientific repositories read-only for software ceremony, duplicated values, misplaced records, and unsourced scientific names. Use when asked \"what can I delete\" or \"audit this scientific repo\". Scientific support goes to review; writing to prose."
metadata:
  cse-kind: "supporting"
  cse-family: "supporting"
  cse-tags: "audit"
  cse-routing:
    direct: [operating-model, BANNED]
    conditional: [retrospective]
---

# Audit CSE practice

Read first: [operating-model](../../references/workflow/operating-model.md), [BANNED](../../BANNED.md).

For a requested session retrospective, read [retrospective](../../references/workflow/retrospective.md)
and use its session-based science categories with Matt's `/retro` when available.
Report candidates only; change nothing until the user picks one. CSE needs no
other plugin to read the reference.

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
- semantically distinct fields populated from one source without identity evidence;
- unique values, inputs, provenance, or interpretation stored under the wrong
  owner;
- lifecycle paperwork, pass/fail records, dead templates, wrappers, flags, and
  configuration with no scientific or user-facing reader;
- software-oriented checks or process-first notebooks that replace an actual
  calculation, result table, diagnostic, uncertainty, or interpretation; and
- existing generators, templates, or check seams that repeatedly recreate or
  permit the same problem.

Before reporting a change, establish the actual owner and readers or callers,
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

Group findings by the root generator or ownership mistake. Rank scientific
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
- `investigate`: state the unresolved ownership evidence.

Write each finding on one line:

`tag: <evidence>; <exact action, authoritative owner, and preservation check>. <estimated files or lines removed>. [paths]`

End with `net:` followed by estimated files and lines removed or renamed, unique
values preserved or moved, and unresolved investigations. Report no
score, compliance state, audit JSON, or new audit machinery. If nothing material
is found, say `CSE practice is lean.` When implementation is requested, route grouped
findings to `cse:design` as one bounded issue proposal.
