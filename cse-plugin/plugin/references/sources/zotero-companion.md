# Zotero Companion

Zotero owns bibliographic records, collections, PDFs, and attachments. Zotero Companion is the configured executable boundary for source retrieval, evidence navigation, bibliography export, optional Mathpix conversion, and a user-owned local corpus. CSE owns the scientific workflow and claim discipline; it does not reimplement Companion or depend on another skill family.

## Supported operations

Start with `zotero-companion doctor --json`. Require only the capabilities needed by the task:

- `zotero-local-api-v1` for live item and attachment reads;
- `configured-local-corpus-v1` and `project-views-v1` for durable synthesis;
- `exact-source-locators-v1` for evidence promoted into claims;
- `better-bibtex-library-export-v1` for the central path-sanitized bibliography;
- `mathpix-on-demand-v1` for last-resort PDF conversion;
- `zotero-linked-companion-v1` for separately approved Markdown attachment writes.

If the executable, configuration, or capability is absent, report that exact condition. Do not fall back to Project Truss, Superpowers, Matt Pocock skills, or generic Zotero/Mathpix skills at runtime.

Before commissioning new research, retrieve Companion's project view:

```bash
zotero-companion wiki-context <project> --query <terms> --json
```

Follow its research, data, and result links. Repeat with `--global` when the
project view is absent or incomplete; an empty project result does not establish
that the library lacks evidence. For retained data discovery, use `data-search
<terms> --json` before `data-query` on an exact returned table. Report freshness
and review state with the result.

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
