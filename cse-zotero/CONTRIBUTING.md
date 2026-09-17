# Contributing to CSE Zotero

## Edit the right owner

- Python CLI and library behavior: `src/zotero_companion/`
- Packaged LinkML and JSON schemas: `src/zotero_companion/schemas/`
- Controlled package examples: `examples/`
- Native Zotero add-on: `zotero-plugin/`
- Build and validation entry points: `scripts/`
- Source-use guidance and acquisition safeguards: `.agent/skills/` and
  `ZOTERO_ACQUISITION.md`

The configured `wiki/` and `data/` trees represent retained or generated
corpus state. They are not package fixtures. Zotero remains the bibliographic
authority, and no software check should require a personal library or corpus.

## Offline checks

From the repository root, run:

```bash
scripts/validate.sh
```

This validates packaged schemas, controlled examples, Python behavior, and
the native add-on without contacting Zotero, reading the configured corpus,
assuming a registry row count, or calling a model. Use
`scripts/check-library.sh` separately for explicit live-library/corpus checks;
it reports missing prerequisites before running them.

For a focused change, use the smallest relevant existing test, for example:

```bash
uv run pytest -q tests/test_scientific_data.py
uv run node --test tests/test_plugin_plan.mjs
```

## Package and add-on checks

The CLI default schema is packaged and works from any working directory:

```bash
uv run cse-zotero schema-validate examples/core-records.yaml --json
uv run cse-zotero schema-validate examples/thermophysical-record.yaml \
  --schema src/zotero_companion/schemas/linkml/thermophysical.yaml \
  --class ThermophysicalRecord --json
uv run python scripts/build_plugin.py
```

Keep the add-on manifest and XPI identity unchanged when editing
`zotero-plugin/`. Do not install it or mutate Zotero as part of routine tests.
