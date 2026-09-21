# Zotero Companion

Zotero owns bibliographic records, collections, PDFs, and attachments. Zotero Companion is the configured executable boundary for source retrieval, evidence navigation, bibliography export, optional Mathpix conversion, and a user-owned local corpus. CSE owns the scientific workflow and claim discipline; it does not reimplement Companion or depend on another skill family.

## Supported operations

Start with `cse-zotero doctor --json` (`zotero-companion` is an equivalent alias). Require only the capabilities needed by the task:

- `zotero-local-api-v1` for live item and attachment reads;
- `configured-local-corpus-v1` and `project-views-v1` for durable synthesis;
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

`wiki-verify` and `wiki-health` are read-only; `wiki-coverage --json` bounds curation work. Separate broken paths and hash drift from scientific disagreement and missing interpretation. `wiki-maintain` is deterministic: it refreshes generated metadata, existing companions, and indexes, and neither synthesizes papers nor replaces curated claims. New evidence never silently alters analysis snapshots or reviewed claims; a changed interpretation goes through explicit incorporation and Review. Report freshness and review state with every result.

## Evidence and data authority

Read repository context and the configured Companion corpus before remote search. Follow evidence back to the exact Zotero parent, child attachment, and page, section, equation, table, figure, or row. A note without an exact locator remains provisional and cannot support a promoted project claim.

The LinkML core describes sources, quantities, uncertainty, transformations, and lineage; optional domain packs add scientific concepts. DuckDB indexes and queries are rebuildable. Keep generated source layers separate from protected curated synthesis.

Companion's corpus is local and unversioned unless the user chooses another recovery policy. Each scientific project declares its own data authority, formats, lineage, retention, versioning, and recovery strategy. CSE and Companion do not prescribe a dataset versioning tool. Preserve alternate bases, standard states, model conventions, and parameter-set identities; quarantine unmappable records with stable identity and the missing evidence.

## Writes, acquisition, and bibliography

Preview every Zotero, Mathpix, or bibliography write and use the native approval gate immediately before applying it. Zotero corrections, companion attachments, and paper acquisition are separate operations.

For a missing paper, provide a bounded set of exact DOI or official article URLs. The user opens and saves each source through the normal browser and Zotero Connector. Never automate publisher pages, bypass controls, guess PDF URLs, or claim success without live verification.

The canonical full-library Better BibTeX export is reported by `doctor` and refreshed by `bibliography-export --apply`. Companion enforces omission of `file` fields. Project snapshots contain only cited records, flow one way from that export, and are never hand-edited. Do not update bibliography consumers until the new export has been verified.

When Companion or the export capability is unavailable, an existing committed project snapshot may still support read-only writing and compilation. First verify that it contains every already-approved citation key needed by the manuscript, contains no local attachment paths, and resolves in the rendered document. Disclose that the snapshot was not refreshed. Block only bibliography refreshes, metadata corrections, and claims that require a source absent from the verified snapshot.

Mathpix is on demand only after every Zotero child has been checked and no usable Markdown companion exists. Respect the configured consent denylist. Treat output as fallible transcription. Attaching it to Zotero requires a separate preview, approval, and verification.
