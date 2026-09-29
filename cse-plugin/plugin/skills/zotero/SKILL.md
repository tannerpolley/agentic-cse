---
name: zotero
description: "Find, acquire, inspect, and cite sources in Zotero through Zotero Companion, previewing and approving every library write. Use when asked to \"add this paper to Zotero\", \"cite this\", \"sync the bibliography\", or search the library. Judging which source applies goes to research."
metadata:
  cse-kind: "tool"
  cse-family: "sources"
  cse-tags: "source-pipeline, zotero"
  cse-routing:
    direct: [source-operations, zotero-companion]
    conditional: []
---

# Zotero source tool

Read first: [source-operations](../../references/sources/source-operations.md), [zotero-companion](../../references/sources/zotero-companion.md).

Inherit core scientific, project, and
language decisions.

Inspect inherited decisions and required Companion capabilities, then perform
one bounded operation from the [zotero-companion](../../references/sources/zotero-companion.md) reference: incorporate
selected sources into the existing project view, query retained knowledge
read-only, or check and maintain corpus health. Search the configured corpus
before the live library, and use source, evidence, typed-record, lineage, and
live library commands only as the operation needs. Preserve parent and
attachment keys plus exact locators. A project's registered Zotero collection is its
reading list; reorganize it only through a previewed, approved `project-organize` plan. Treat metadata and generated summaries as
discovery aids, not claim support.

Preview every library, collection, attachment, metadata, or bibliography
mutation and use native approval immediately before the write, including after
a blanket correction or deletion request. For missing papers, give exact DOI
or official URLs for the investigator to open and save; do not automate
publisher pages or guess PDF URLs. Return keys, locators, authority, and
limitations to the invoking stage.
