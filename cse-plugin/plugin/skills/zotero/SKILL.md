---
name: zotero
description: "Find and inspect Zotero sources. Use when asked to add one specified paper, cite, sync the bibliography, or search the library. Specific-paper requests use bounded acquisition; other library writes require preview and approval. Source selection goes to research."
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

Run `cse-zotero doctor --json` first and inspect operation readiness and
`acquisition.tokens` for the configured token names and status. Never expose
token values.

When the user requests one specific paper and supplies its DOI or article URL,
use the bounded acquisition route:

```bash
cse-zotero acquire <DOI-or-article-URL> --collection <key-or-name> --json
```

That explicit request authorizes this `acquire` route without a separate
per-save approval. Its browser route runs only when `doctor --json` shows `acquisition.connector.ready`;
otherwise, and whenever a publisher needs a person, `acquire` returns a hand-off
link. Give that link to the user instead of retrying.

Do not broaden acquisition into a paper search or collection task. Follow the
canonical
[Zotero acquisition rules](https://github.com/agentic-cse/cse-zotero/blob/main/ZOTERO_ACQUISITION.md)
for route eligibility and publisher/browser boundaries.

For corrections, collection changes, bibliography refreshes, Mathpix
conversions, and companion attachments, preview each mutation and use native
approval immediately before applying it, including after a blanket correction
or deletion request. Return keys, locators, authority, and limitations to the
invoking stage.
