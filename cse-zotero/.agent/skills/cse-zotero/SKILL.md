---
name: cse-zotero
description: Use for research questions that may cross the local Zotero library, paper evidence, equations, thermophysical data, model parameters, implementation, or validation. Start here before opening a full paper.
---

# CSE Zotero

Run `cse-zotero doctor --json`, then use the configured corpus wiki as
the first, read-only retrieval layer. Zotero owns
the documents and bibliographic metadata; the wiki owns evidence navigation,
curated records, relations, and synthesis. Each project selects the authority
for reusable numerical data and parameter packages; a separate
thermophysical-data-registry is optional, not a runtime requirement.

## Default retrieval recipe

1. Read `wiki/index.md` in the configured corpus, plus `CONTEXT.md` and the
   relevant parts of `docs/cse-zotero-design.md` from the installed
   package or source checkout.
2. Start globally for cross-project questions:
   `uv run cse-zotero wiki-context --global --query "<question>" --json`.
3. Inspect `matched_source_keys`, `briefs`, `evidence_hits`, and
   `evidence_coverage`; report stale or unavailable `freshness` and inspect
   evidence hashes, data integrity, and source locators. For a project view,
   follow `project_context` to existing research, data and result decisions
   before proposing another study.
4. Use `wiki-source KEY` for the bibliographic record and its `wiki.brief` /
   `wiki.evidence` routes, then `wiki-record-search`, `wiki-record`, and
   `wiki-lineage` for typed knowledge.
5. Use the project's selected data-authority front door to discover retained
   numerical packages. When that authority is the companion registry, use
   `data-search "<species or property>" --json` and then `data-query` on an
   exact returned resource path. Require verified integrity and inspect
   quality, units, basis and source locators; unreviewed data is not
   automatically an accepted project input.
6. Use `wiki-evidence KEY --query "<specific terms>"` for short,
   line-located companion passages before reading a full PDF.
7. Use `zotero-search`, `zotero-children`, and `zotero-attachment-path` when
   the live library is newer than the materialized corpus.
8. When retained evidence leaves a named literature gap, read the
   [acquisition contract](../../../ZOTERO_ACQUISITION.md) before any external
   discovery. For a user-requested paper or a relevant paper the work finds
   missing, follow that contract's eligibility and collection rules, check
   `doctor --json` acquisition readiness, and use
   `cse-zotero acquire <DOI-or-article-URL> --collection <key-or-name> --json`.
   That bounded route needs no per-save approval and starts Chrome without a
   startup window when needed. An idle not-ready status does not block an
   eligible call; acquire one identified paper per call.

## Evidence and authority

- Existing Zotero `.md`/`.mmd` children are authoritative companions. Run
  `wiki-evidence-sync --json` and review its plan before `--apply`.
- Evidence search reads only declared Markdown/Mathpix Markdown companions;
  it never reads PDFs or converts them.
- Do not treat generated source metadata, a paper brief, a selected-authority
  staging path, or an implementation pointer as a validated conclusion.
- Every promoted claim, equation, dataset, parameter, idea, workflow, or
  validation record needs exact source locators and status/confidence.
- Keep source-reported, normalized, inferred, and project-derived statements
  visibly separate. Preserve units, composition bases, assumptions, and limits.

## Curation and writes

Use `wiki-coverage`, `wiki-triage`, and the read-only templates to choose a
bounded curation task. Update an existing page or record before creating a
near-duplicate. Repository refreshes are explicit and never mutate Zotero.
Zotero writes other than eligible `acquire` calls remain separate, dry-run by
default, and require a later explicit user approval.

For deterministic periodic repository maintenance, run
`cse-zotero wiki-maintain --apply --json`. It refreshes source metadata,
resolves live attachment lists, syncs existing Markdown companions, rebuilds
the index once, and verifies the repository. Changed or unavailable evidence
is preserved and reported with concrete errors; PDFs are never converted, and
Zotero is never mutated.
Each registered project's Zotero collection tree is its reading list:
`wiki/projects/<slug>.md` shows it below the curated notes, and
`cse-zotero project-list --json` names the slug and collection. To reorganize
it, write a `project-organize` plan, show the user the dry-run preview, and
apply with `--apply` only after they approve; never edit the generated part of
a project page by hand.
For model-driving work, use `wiki/curation/model-driving-records.json` as a
small starting set before expanding through global search and lineage.

## Retention and recovery

Generated source metadata, triage data, SQLite indexes, and evidence-sync
indexes are rebuildable. Curated briefs, interpretations, relations,
classification decisions, Zotero attachments, and project-owned data are not.
Pushing this runtime repository does not back up the external corpus. Each
project records its own data authority, retention owner, and revision.

Use the project's existing ordinary copy/versioning mechanism: copy the
selected corpus, hash one curated record and one dataset with `sha256sum`, and
verify the hashes in an isolated copy. For example:

```bash
check=/path/to/isolated-recovery-check
mkdir -p "$check"
cp -a /path/to/selected-corpus/. "$check/"
(cd /path/to/selected-corpus && \
  sha256sum wiki/projects/<project>.md data/<dataset>.csv > "$check/expected.sha256")
(cd "$check" && sha256sum -c expected.sha256 \
  && test -s wiki/projects/<project>.md \
  && test -s data/<dataset>.csv)
uv run --project /path/to/cse-zotero cse-zotero data-query \
  "$check/data/<dataset>.csv" --sql "SELECT * FROM records LIMIT 1" --json
```

Run one read-only native data query against the copied dataset and compare one
known value with the copied record. Do not write the check into the live
corpus; no new backup product or scheduler is required.

## PDF, publisher, and acquisition gates

Never convert a PDF when a usable Zotero Markdown companion exists. If none
exists, read `.agent/skills/mathpix/SKILL.md` and follow its explicit
`--confirmed-no-companion` gate; keep the PDF immutable and never expose
credentials. The [acquisition contract](../../../ZOTERO_ACQUISITION.md) is the
repository-owned authority for external discovery, publisher access, and every
route that can add a paper to Zotero. Follow its eligibility and browser
boundaries; all Zotero writes other than eligible `acquire` calls retain their
reviewed-preview and approval steps.

## Validation

Run the bounded public contract check before handing off:

```bash
uv run python scripts/agent_smoke.py --json
uv run python scripts/benchmark_wiki.py --json
uv run cse-zotero wiki-verify --json
uv run cse-zotero wiki-health --json
```

Add `--registry-root` to lint or release commands only when the selected
project authority exposes that optional registry layout.

The smoke/benchmark workflows must remain read-only, report zero PDF reads,
and preserve attachment keys, hashes, and locators in their evidence path.
For answer-grounding and promotion criteria, read
`docs/agent-answer-rubric.md`.
