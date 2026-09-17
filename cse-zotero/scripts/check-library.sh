#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

config_root="${XDG_CONFIG_HOME:-${HOME}/.config}"
config_path="$config_root/zotero-companion/config.toml"
if [[ ! -f "$config_path" ]]; then
  echo "Live prerequisite missing: $config_path; run cse-zotero init --apply first." >&2
  exit 2
fi

doctor_status="$(uv run cse-zotero doctor --json || true)"
if ! jq -e 'type == "object"' <<<"$doctor_status" >/dev/null; then
  echo "Live prerequisite check failed: cse-zotero doctor did not return JSON." >&2
  exit 2
fi

missing=0
for capability in zotero better_bibtex; do
  if ! jq -e ".${capability}.ok == true" <<<"$doctor_status" >/dev/null; then
    detail="$(jq -r ".${capability}.error // \"unavailable\"" <<<"$doctor_status")"
    echo "Live prerequisite missing: ${capability}: ${detail}" >&2
    missing=1
  fi
done
if (( missing )); then
  exit 2
fi

wiki_root="$(jq -r '.wiki_root' <<<"$doctor_status")"
data_root="$(jq -r '.data_root' <<<"$doctor_status")"
registry_root="$data_root/domains/thermophysical/source/registry"
normalized_records="$data_root/domains/thermophysical/normalized/registry-records.csv"
for required_path in "$wiki_root" "$registry_root" "$normalized_records"; do
  if [[ ! -e "$required_path" ]]; then
    echo "Live prerequisite missing: configured corpus path $required_path" >&2
    exit 2
  fi
done

PYTHONDONTWRITEBYTECODE=1 uv run pytest -q -p no:cacheprovider
uv run cse-zotero wiki-verify --json | jq -e '.ok == true' >/dev/null
uv run cse-zotero wiki-lint --registry-root "$registry_root" --json | jq -e '.ok == true' >/dev/null
uv run cse-zotero wiki-manifest-lint --registry-root "$registry_root" --json \
  | jq -e '.ok == true' >/dev/null
uv run cse-zotero wiki-coverage --json | jq -e '.ok == true' >/dev/null
uv run python scripts/benchmark_wiki.py --json \
  | jq -e '.summary.passed_count == .summary.task_count' >/dev/null
uv run python scripts/agent_smoke.py --json \
  | jq -e '.summary.passed_count == .summary.task_count' >/dev/null

echo "CSE Zotero live library and corpus checks passed."
