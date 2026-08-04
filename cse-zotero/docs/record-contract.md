# Typed knowledge-record contract

The generated Zotero source layer remains bibliographic evidence. Curated
scientific knowledge lives in `wiki/records/` as small JSON records with a
stable type-prefixed ID. A record is not accepted merely because an agent can
write it: the record must declare its provenance and status, and `wiki-lint`
must be able to trace its source.

## Stable IDs

Wiki-owned IDs use one of these prefixes:

```text
paper:<slug>
claim:<legacy-claim-id>
equation:<slug>
dataset:<slug>
parameter:<slug>
correlation:<slug>
idea:<slug>
insight:<slug>
workflow:<slug>
implementation:<slug>
validation:<slug>
rel:<slug>
```

Registry IDs are not renamed. A record refers to one with a `registry_refs`
entry containing the external ID, registry name, path, and version or commit.
Zotero parent keys remain the source identity and are never replaced by a
wiki slug.

## Common envelope

Every JSON record contains:

```json
{
  "schema_version": 1,
  "record_type": "equation",
  "record_id": "equation:example",
  "title": "Short human title",
  "status": "source-backed",
  "confidence": "high",
  "summary": "One sentence describing what this record means.",
  "provenance": {
    "derivation_kind": "source-reported",
    "sources": [
      {
        "zotero_key": "YEENX35P",
        "attachment_key": "2M74BKJG",
        "locator": {"kind": "equation", "value": "Eq. 8"}
      }
    ],
    "derived_from": [],
    "review": {"reviewer": "", "reviewed_at": "", "notes": ""}
  }
}
```

The `derivation_kind` distinguishes what a source says from a normalized value,
an agent inference, a project-derived result, or an implementation observation.
`sources` and `derived_from` may both be populated. A record with neither is
invalid because it cannot be audited.

## Typed relations

`wiki/relations.json` stores reasoned edges. A bare Markdown link is only
navigation; a scientific relation needs a type, rationale, and provenance when
it represents a conclusion. Relations can target a wiki record, a legacy claim
(`claim:<id>`), a generated Zotero source (`source:<key>`), or an external
registry reference (`registry:<id>`).

## Evidence policy

Source locators should identify a section, equation, table, figure, page, row,
or line range. Existing Zotero `.md`/`.mmd` companions are copied exactly into
`wiki/evidence/<zotero-key>/` when a record needs local searchable evidence.
The original PDF remains in Zotero. No record creation step converts or
re-OCRs a PDF.

## Commands

```bash
uv run zotero-wiki wiki-record equation:figiel-born-solvation-shell --json
uv run zotero-wiki wiki-lineage equation:figiel-born-solvation-shell --json
uv run zotero-wiki wiki-lint --registry-root ../thermophysical-data-registry --json
uv run zotero-wiki wiki-context --global --query "Born activity coefficients" --json
```

All commands are read-only. Record authoring is a deliberate repository
change; Zotero and the registry are not mutated by this interface.
