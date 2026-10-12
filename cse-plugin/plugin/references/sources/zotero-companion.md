# Zotero Companion

Zotero owns bibliographic records, collections, PDFs, and attachments. Zotero Companion is the configured executable boundary for source retrieval, evidence navigation, bibliography export, optional Mathpix conversion, and a user-owned local corpus. CSE owns the scientific workflow and claim discipline; it does not reimplement Companion or depend on another skill family.

## Supported operations

Start with `cse-zotero doctor --json` (`zotero-companion` is an equivalent alias). Require only the capabilities needed by the task:

- `zotero-local-api-v1` for live item and attachment reads;
- `configured-local-corpus-v1` and `project-views-v1` for durable synthesis;
- `project-libraries-v1` for a project's registered Zotero collection and its generated page;
- `exact-source-locators-v1` for evidence promoted into claims;
- `better-bibtex-library-export-v1` for the central path-sanitized bibliography;
- `mathpix-on-demand-v1` for last-resort PDF conversion;
- `zotero-linked-companion-v1` for separately approved Markdown attachment writes.

If the executable, configuration, or capability is absent, report that exact condition. Do not fall back to Project Truss, Superpowers, Matt Pocock skills, or generic Zotero/Mathpix skills at runtime. A green `doctor` result certifies the software path, not a populated project view, an intact dataset, or scientific suitability.

## Three ordinary operations

### Incorporate selected sources

Read the existing project view before searching anew:

```bash
cse-zotero wiki-context <project> --query "<terms>" --json
```

Repeat with `--global` when the project view is absent or incomplete; an empty project result does not establish that the library lacks evidence. For each selected source, read `wiki-source <KEY> --json` and `wiki-evidence <KEY> --query "<terms>" --json`; evidence search reads existing Markdown companions only and never converts a PDF. Decide whether the source adds knowledge, updates existing knowledge, disputes a claim, or adds nothing material, then update the affected paper brief, concept page, and cross-links rather than writing a parallel summary for every visit. Scaffold only a genuinely new page with `wiki-paper-template <KEY> --json` or `wiki-record-template <record_type> --zotero-key <KEY> --json`, then run `wiki-lint`. Keep source statements, unit and basis transformations, derived insights, hypotheses, and project adoption distinct, and surface incompatible conventions instead of merging them. Registering a dataset is a separate explicit Companion operation; synchronizing an attachment does not register its tables.

### Query retained knowledge

Use the project view command above first and `--global` as the fallback, then `wiki-record-search`, `wiki-record`, and `wiki-lineage` for typed equations, datasets, parameters, and validation records. For retained data, use `data-search <terms> --json` before `data-query` on one exact returned table. Return the known result, supporting source locators, relevant datasets and existing project decisions, uncertainty, and the precise remaining gap. Query-only work is read-only: file no new page, reclassify no source, and write nothing to the library unless retention is requested. A synthesized page is navigation and interpretation, not independent experimental evidence.

### Check and maintain

`wiki-verify` and `wiki-health` are read-only corpus checks; `wiki-coverage --json` bounds curation work. A green result does not establish evidence Markdown hash integrity. Read the exact passage with `wiki-evidence <KEY> --query "<terms>" --json` and inspect `hash_matches` and mismatch warnings. Use `doctor --json` to check capability and configuration state. Separate broken paths and verified content-hash drift from scientific disagreement and missing interpretation. `wiki-maintain` is deterministic: it refreshes generated metadata, existing companions, and indexes, and neither synthesizes papers nor replaces curated claims. New evidence never silently alters analysis snapshots or reviewed claims; a changed interpretation goes through explicit incorporation and Review. Report freshness and review state with every result.

### Project library

A project that adopts Zotero owns one collection under the Companion's root project collection. The Companion registry is the only record of that binding; CSE does not copy it. Use `cse-zotero project-list --json` to find the slug and collection. `wiki/projects/<slug>.md` keeps curated notes above its generated marker and shows the live collection tree below it. Reorganize papers in Zotero or with a `project-organize` plan: show the dry-run preview, get native approval, then apply with `--apply`. Never hand-edit the generated part. Setup registers the project with `project-register`; a dry run first, then `--apply` after approval. It links an existing collection with `--collection <key>` (the first registration also names the root with `--root <key>`) or, once a root is registered, creates one under it with `--create "<name>"`. With the Companion add-on installed, Zotero refreshes the page after a collection change. `project-sync --json` lists pages that no longer match Zotero, and `project-sync --apply` rewrites them.

## Evidence and data authority

Read repository context and the configured Companion corpus before remote search. Follow evidence back to the exact Zotero parent, child attachment, and page, section, equation, table, figure, or row. A note without an exact locator remains provisional and cannot support a promoted project claim.

The LinkML core describes sources, quantities, uncertainty, transformations, and lineage; optional domain packs add scientific concepts. DuckDB indexes and queries are rebuildable. Keep generated source layers separate from protected curated synthesis.

Companion's corpus is local and unversioned unless the user chooses another recovery policy. Each scientific project declares its own data authority, formats, lineage, retention, versioning, and recovery strategy. CSE and Companion do not prescribe a dataset versioning tool. Preserve alternate bases, standard states, model conventions, and parameter-set identities; quarantine unmappable records with stable identity and the missing evidence.

## Source and data handoff to Analyze

When a selected source dataset is ready for project use, register it only in the
project's declared registry and with the project's retention authority. Then
copy the chosen, hash-verified resource into the analysis input directory with
`data-select`; the generated `.lineage.json` records the registered identity,
source locator, metadata, and resource hash. Review that lineage and the copied
input before Analyze uses them. Query the analysis-local copy or read it with
the analysis's native reader, so the calculation uses a fixed input snapshot
rather than a changing registry resource.

```bash
# Preview registration and review the planned record, source locator, metadata, and hashes.
cse-zotero data-register <package> --registry-root <project-registry> --json

# Use the reviewed record ID; preview selection and review the copied resource and lineage.
cse-zotero data-select <record-id> --resource <resource-path> \
  --analysis analyses/<id> --registry-root <project-registry> --json

# Apply only after reviewing both previews.
cse-zotero data-register <package> --registry-root <project-registry> --apply --json
cse-zotero data-select <record-id> --resource <resource-path> \
  --analysis analyses/<id> --registry-root <project-registry> --apply --json
cse-zotero data-query analyses/<id>/inputs/<resource-name> \
  --sql "SELECT * FROM records" --json
```

Registration and selection write only when `--apply` is supplied. Querying is
read-only. Use the project's declared authority and verify the source, version,
locator, units, composition basis, conditions, uncertainty, and hash before
interpreting the result. `doctor` reports software capabilities; a file-shape check confirms only the
fields and columns. Neither establishes scientific acceptance.

## Writes, acquisition, and bibliography

Run `doctor --json` before operating and inspect operation readiness and
`acquisition.tokens` without exposing token values.

Add a paper with the bounded route when the user requests it, or when any
stage finds a relevant paper with a DOI or article URL that the library lacks:
a source the work cites or studies, the origin of an equation, data, method or
reference case, or other literature relevant to the project's question.

```bash
cse-zotero acquire <DOI-or-article-URL> --collection <key-or-name> --json
```

Either case authorizes `acquire` without asking or a per-save approval. File an
agent-found paper in the collection that `cse-zotero project-list --json`
registers for the current repository; when none is registered, do not acquire
it and list its DOI or link in the report. Acquire one paper per call, in
sequence; the command deduplicates against the library. Its browser route runs
only when `doctor --json` shows `acquisition.connector.ready`; otherwise, and
whenever a publisher needs a person, `acquire` returns a hand-off link. Never
retry; continue the task and report acquired item keys and hand-off links. An
acquired paper is evidence to assess, not claim support.

The canonical
[Zotero acquisition rules](https://github.com/agentic-cse/cse-zotero/blob/main/ZOTERO_ACQUISITION.md)
owns route eligibility and publisher/browser boundaries; do not duplicate its
safety rules here.

Other writes still require a reviewed preview and native approval immediately
before applying them. This includes Zotero corrections, collection changes,
bibliography refreshes, Mathpix conversions, and companion attachments. Treat
paper acquisition as its own operation, separate from those writes.

The canonical full-library Better BibTeX export is reported by `doctor` and refreshed by `bibliography-export --apply`. Companion enforces omission of `file` fields. Project snapshots contain only cited records, flow one way from that export, and are never hand-edited. Do not update bibliography consumers until the new export has been verified.

When Companion or the export capability is unavailable, an existing committed project snapshot may still support read-only writing and compilation. First verify that it contains every already-approved citation key needed by the manuscript, contains no local attachment paths, and resolves in the rendered document. Disclose that the snapshot was not refreshed. Block only bibliography refreshes, metadata corrections, and claims that require a source absent from the verified snapshot.

Mathpix is on demand only after every Zotero child has been checked and no usable Markdown companion exists. Respect the configured consent denylist. Treat output as fallible transcription. Attaching it to Zotero requires a separate preview, approval, and verification.
