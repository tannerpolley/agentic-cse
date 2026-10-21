#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

uv run linkml-validate src/zotero_companion/schemas/linkml/companion.yaml \
  src/zotero_companion/schemas/linkml/thermophysical.yaml
uv run cse-zotero schema-validate examples/core-records.yaml --json \
  | jq -e '.ok == true' >/dev/null
uv run cse-zotero schema-validate examples/thermophysical-record.yaml \
  --schema src/zotero_companion/schemas/linkml/thermophysical.yaml \
  --class ThermophysicalRecord --json \
  | jq -e '.ok == true' >/dev/null

PYTHONDONTWRITEBYTECODE=1 uv run pytest -q -p no:cacheprovider \
  -m 'not live'

plugin_package="$(mktemp --suffix=.xpi)"
trap 'rm -f -- "$plugin_package"' EXIT
uv run python scripts/build_plugin.py --output "$plugin_package" >/dev/null
node --test tests/test_plugin_plan.mjs

echo "CSE Zotero validation passed."
