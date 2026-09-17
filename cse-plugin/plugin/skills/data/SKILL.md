---
name: data
description: "CSE — Discover, query, validate, and trace retained scientific data when authority or lineage is unresolved."
metadata:
  cse-kind: "tool"
  cse-family: "sources"
  cse-tags: "source-pipeline, data"
  cse-routing:
    direct: [source-operations]
    conditional: [zotero-companion]
---

# Scientific data tool

Inherit core scientific, project, and
language decisions. Activate `zotero-companion` only for Companion authority.

Use this tool only for a bounded data need. A repository-owned file with a
matching retained snapshot and provenance hash needs no Companion probe.
Search project records first; query or validate only the required table or
record. Preserve source, transformation, parameter-set, uncertainty, unit,
and basis identity. Use `data-query`, `schema-validate`, `wiki-manifest`, and
`wiki-lineage` only for the corresponding bounded authority or lineage need.
Report rejected fields and missing evidence rather than repairing values
silently, and never promote a review-stage record to a project conclusion.

Read-only requests do not mutate datasets, manifests, registries, or generated
source layers. Return approved configuration or migration to `cse:setup`, and
use `cse:zotero` for Zotero records or acquisition.
