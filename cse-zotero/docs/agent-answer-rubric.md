# Agent answer and promotion rubric

This rubric keeps the wiki useful without turning compact summaries into
unreviewed model truth.

## Minimum answer contract

For a research or modeling answer, an agent should:

1. State the scope and freshness result. A stale or unavailable live Zotero
   check is visible, not silently repaired.
2. Separate direct source reporting, registry data, implementation behavior,
   and the agent's inference.
3. Name the relevant Zotero key, typed record ID, registry ID/path and version
   when present, and implementation/validation reference when present.
4. Give exact evidence locators for important equations, values, assumptions,
   and limitations. Prefer companion line/section locators returned by
   `wiki-evidence`.
5. Preserve model conventions, units, composition/activity basis, validity
   range, uncertainty, and unresolved review status.
6. Say what is missing before claiming that a model input or conclusion is
   validated.

Routine answers should normally use the compact context, brief, typed record,
and evidence passage. Open the full normalized source or PDF only for an
explicit audit, unresolved ambiguity, or missing context, and say why.

## Promotion rules

Do not promote a statement to a claim, equation, dataset, parameter,
workflow, implementation, validation, or synthesis record unless it has:

- a stable type-prefixed ID;
- a source Zotero key or an explicit `derived_from` chain;
- an attachment/evidence locator when the source is available;
- status, confidence, derivation kind, and limitations;
- compatible registry/model/code references where applicable.

Source-reported records may remain `proposed` or `source-backed`. Inferred or
project-derived records must not be written as quotations. Staging registry
paths are review inputs, not accepted portable parameter sets.

## Stop conditions

Stop and report the gap when evidence is missing, a hash is mismatched, a
source is stale, a registry path is unavailable, a parameter convention is
ambiguous, or sources contradict. Do not fill gaps by guessing, silently
converting PDFs, or searching a publisher page in a way that bypasses its
controls.

## Contract checks

The repository-level checks are the executable acceptance gate:

```bash
uv run python scripts/agent_smoke.py --json
uv run python scripts/benchmark_wiki.py --json
uv run cse-zotero wiki-lint --registry-root data/domains/thermophysical/source/registry --json
uv run cse-zotero wiki-manifest-lint --registry-root data/domains/thermophysical/source/registry --json
```

These checks validate retrieval and provenance plumbing; they do not replace
scientific review of a newly promoted record.
