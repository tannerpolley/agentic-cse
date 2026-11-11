---
name: zotero
description: "Find, inspect, add, and cite Zotero sources. Use when asked to sync the bibliography, search the library, add a paper, \"extract the equations from this PDF\", or \"OCR this paper into Markdown\". Source selection goes to research; figure values to digitize."
metadata:
  cse-kind: "tool"
  cse-family: "sources"
  cse-tags: "source-pipeline, zotero"
  cse-routing:
    direct: [source-operations, zotero-companion]
    conditional: [mathpix-transcription]
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
reading list; reorganize it through a previewed `project-organize` plan. Treat metadata and generated summaries as
discovery aids, not claim support.

Run `cse-zotero doctor --json` first and inspect operation readiness and
`acquisition.tokens` for the configured token names and status. Never expose
token values.

Add a paper the user requests, or a relevant paper the work finds missing from
the library, without asking, through `cse-zotero acquire` as the
[acquisition section](../../references/sources/zotero-companion.md#writes-acquisition-and-bibliography)
directs. Each call adds one identified paper; finding papers belongs to
`cse:research`. Follow the canonical
[Zotero acquisition rules](https://github.com/tannerpolley/agentic-cse/blob/main/cse-zotero/ZOTERO_ACQUISITION.md)
for route eligibility and publisher/browser boundaries.

For metadata corrections and collection changes, preview each mutation, apply
it without asking, and report what changed. For deletions, bibliography
refreshes, and companion attachments, preview each mutation
and use native approval immediately before applying it, including after a
blanket deletion request. Return keys, locators, authority, and limitations to the
invoking stage.

For PDF transcription, activate [mathpix-transcription](../../references/sources/mathpix-transcription.md)
only when a transcription is needed.
