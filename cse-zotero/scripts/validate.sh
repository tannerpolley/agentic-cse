#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

companion_status="$(uv run zotero-companion doctor --json || true)"
wiki_root="$(jq -r '.wiki_root' <<<"$companion_status")"
data_root="$(jq -r '.data_root' <<<"$companion_status")"
registry_root="$data_root/domains/thermophysical/source/registry"
normalized_records="$data_root/domains/thermophysical/normalized/registry-records.csv"

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
  "$normalized_records" \
  --sql 'SELECT record_type, count(*) AS count FROM records GROUP BY record_type ORDER BY record_type' \
  --json | jq -e '.rows | length == 5' >/dev/null

echo "Zotero Companion validation passed."
