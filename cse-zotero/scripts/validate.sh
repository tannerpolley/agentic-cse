#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

registry_root="data/domains/thermophysical/source/registry"

uv run linkml-validate schema/companion.yaml schema/thermophysical.yaml
uv run zotero-companion schema-validate data/examples/core-records.yaml --json \
  | jq -e '.ok == true' >/dev/null
uv run zotero-companion schema-validate data/examples/thermophysical-record.yaml \
  --schema schema/thermophysical.yaml --class ThermophysicalRecord --json \
  | jq -e '.ok == true' >/dev/null
PYTHONDONTWRITEBYTECODE=1 uv run pytest -q -p no:cacheprovider

uv run zotero-companion wiki-verify --json \
  | jq -e '.ok == true' >/dev/null
uv run zotero-companion wiki-lint --registry-root "$registry_root" --json \
  | jq -e '.ok == true' >/dev/null
uv run zotero-companion wiki-manifest-lint --registry-root "$registry_root" --json \
  | jq -e '.ok == true' >/dev/null
uv run zotero-companion wiki-coverage --json \
  | jq -e '.ok == true' >/dev/null

uv run python scripts/benchmark_wiki.py --json \
  | jq -e '.summary.passed_count == .summary.task_count' >/dev/null
uv run python scripts/agent_smoke.py --json \
  | jq -e '.summary.passed_count == .summary.task_count' >/dev/null

plugin_package="$(mktemp --suffix=.xpi)"
trap 'rm -f -- "$plugin_package"' EXIT
uv run python scripts/build_plugin.py --output "$plugin_package" >/dev/null
node --test tests/test_plugin_plan.mjs

uv run zotero-companion data-query \
  data/domains/thermophysical/normalized/registry-records.csv \
  --sql 'SELECT record_type, count(*) AS count FROM records GROUP BY record_type ORDER BY record_type' \
  --json | jq -e '.rows | length == 5' >/dev/null

uv run datalad status --annex all >/dev/null

echo "Zotero Companion validation passed."
