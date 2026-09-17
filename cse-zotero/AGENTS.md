# CSE Zotero agent contract

## Contributor routing

- Change Python behavior in `src/zotero_companion/` and keep LinkML/JSON
  schemas in `src/zotero_companion/schemas/`.
- Use controlled examples in `examples/`; do not treat `wiki/` or `data/` as
  package fixtures or delete them without checking their external owner.
- Build the native Zotero add-on from `zotero-plugin/` with
  `uv run python scripts/build_plugin.py`.
- Run `scripts/validate.sh` for offline package checks. Run
  `scripts/check-library.sh` only when the configured Zotero library, corpus,
  and Better BibTeX prerequisites are intentionally available.
- Use `CONTRIBUTING.md` for the edit/test/install map. Source-use guidance is
  retained in `.agent/skills/` for the later integrated-plugin transfer;
  runtime data contracts and operational commands remain here and in the
  product README.

Repository Profile: scientific-computing

This repository maintains the installable source-linked research companion for
the local Zotero library. Zotero remains the bibliographic authority. The
active corpus is configured user-owned state outside this package checkout.

For the reusable agent operating protocol, read
`.agent/skills/cse-zotero/SKILL.md` before a research task that crosses
Zotero evidence, equations, data, implementation, or validation.

The canonical full-library Better BibTeX export is the path reported by
`doctor`. Refresh it only with `bibliography-export --apply` after reviewing
the dry-run plan. The command enforces omission of local `file` paths and never
updates project consumers; consumer snapshots are separate project changes.

Use `zotero-search`, `zotero-children`, and `zotero-attachment-path` for live
source reads. Use `mathpix-convert` only after its dry-run proves that no usable
Markdown child exists and the consent denylist permits conversion. Attaching
the result is a distinct `zotero-attach-companion` write with its own approval.

## Start of a research task

Run `uv run cse-zotero doctor --json` first. Use the read-only wiki-triage
command to find relevant sources that still need a paper brief:

    uv run cse-zotero wiki-triage --queue unbriefed_relevant --json

For broader-corpus review, inspect sources whose domain/thread classification is
still unassigned:

    uv run cse-zotero wiki-triage --queue needs_classification --json

When a task crosses paper evidence, data, equations, implementation, or
validation boundaries, first read docs/cse-zotero-design.md and CONTEXT.md
in addition to `wiki/index.md` in the configured corpus. The current project
slugs are initial views, not the boundary of the Zotero corpus.

1. Read `wiki/index.md` and the relevant file under `wiki/projects/` in the
   configured corpus reported by `doctor`; CLI commands resolve it by default.
2. Use the local source index before searching the web:
   `uv run cse-zotero wiki-context <project> --query "<terms>" --json`.
   For cross-project questions start with
   `uv run cse-zotero wiki-context --global --query "<terms>" --json`.
3. Retrieve the full normalized source with
   `uv run cse-zotero wiki-source <ZOTERO_KEY> --json`.
4. Retrieve source passages from existing companions with
   `uv run cse-zotero wiki-evidence <ZOTERO_KEY> --query "<terms>" --json`.
   This searches only declared `.md`/`.mmd` evidence files and never converts
   PDFs.
5. Inspect the `freshness` object in `wiki-context`. A stale or unavailable
   live check must be reported; do not silently refresh or treat stale source
   metadata as current.
6. Treat `wiki/sources/`, `wiki/evidence/`, `catalog.json`, and
   `manifest.json` as generated or source-derived artifacts. Do not hand-edit
   them.
7. Use `wiki-record-search`, `wiki-record`, and `wiki-lineage` for typed
   equations, datasets, parameters, ideas, workflows, implementations, and
   validation records before opening a full PDF. Run `wiki-health` when a
   source or registry dependency may have changed; it is read-only.
8. Use `wiki-coverage --json` to choose bounded corpus work, and
   `wiki-record-template <record_type> --zotero-key <KEY> --json` or
   `wiki-paper-template <KEY> --json` when a new curated page is needed. These
   templates are read-only and must be filled with exact evidence before a
   record or brief is added.
9. Run `wiki-evidence-sync --json` to discover existing Zotero `.md`/`.mmd`
   companions across the whole corpus. Review the plan before using
   `wiki-evidence-sync --apply --json`; this copies only existing companions
   into the configured corpus, never reads or copies PDFs, never runs Mathpix, and
   never writes to Zotero. Changed or conflicting evidence is refused rather
   than overwritten.

## Evidence and curation

The generated triage.json and index.sqlite are rebuildable source-derived
artifacts. Do not hand-edit them; use the explicit wiki-index or wiki-refresh
commands. Deliberate source relevance/domain/research-thread decisions belong
in `wiki/curation/source-assignments.json` and should normally be planned with
`wiki-classify` (dry-run by default) before applying them. Metadata suggestions
in triage are not reviewed assignments.

- Zotero records and attached documents are source evidence, not validated
  project conclusions.
- Put paper-level interpretation in `wiki/papers/` or `wiki/graphs/`.
- Put reusable derived statements in `wiki/claims/`; every claim must name a
  `zotero_key` or `derived_from`, plus status and confidence.
- Preserve exact quotes, page/section locations, equations, tables, and
  limitations when converting or summarizing papers.
- Check the active Engineering repository and tests before promoting a
  literature statement to implementation truth.

## PDF and Mathpix workflow

Before converting a PDF, read `.agent/skills/mathpix/SKILL.md` and inspect the
Zotero parent's children and attachment paths. An existing `.md` or `.mmd`
child is the authoritative companion: use it directly or copy it exactly into
the evidence bundle, record its Zotero attachment key, and do not run the
converter. The companion filename may differ from the PDF filename and may be
stored in a different Zotero storage directory, so checking only for a
same-stem file beside the PDF is insufficient.

Only when Zotero has no usable Markdown companion may an agent use
`scripts/convert_with_mpx.py`, and the command must include
`--confirmed-no-companion`. The wrapper refuses PDF conversion without that
confirmation and refuses a same-stem `.md`/`.mmd` file. Use
`--force-reconvert` only for an explicitly requested comparison or re-OCR;
never use it for routine ingestion. Keep the source PDF immutable. Never
print, commit, or copy Mathpix authentication tokens.

## Paper acquisition and publisher access

Before external literature discovery, publisher access, remote paper
acquisition, or a Zotero Connector save, read `ZOTERO_ACQUISITION.md`. It owns
the local-first search, optional Undermind handoff, VPN gate, native approvals,
user-operated Connector flow, verification, and publisher hard stops. The
canonical `zotero` skill is the CSE adapter when it is installed.

## Maintenance

After a Zotero refresh, run `wiki-verify`, `wiki-stale`, and `wiki-coverage`.
Append significant
ingests, synthesis updates, and lint results to `wiki/log.md`; do not rewrite
old log entries. `wiki-refresh` is explicit and corpus-only: review its
dry-run output first, then use `wiki-refresh --apply` only when the generated
source layer should be updated. It never mutates Zotero and never refreshes
curated claims, graphs, or evidence companions automatically. Corpus-
generated source records may be rebuilt, but curated claims and synthesis
require deliberate review.
