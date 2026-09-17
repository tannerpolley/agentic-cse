#!/usr/bin/env bash
set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
deploy_parent="$HOME/.codex/plugins"
marketplace="$HOME/.agents/plugins/marketplace.json"
runtime_target="$HOME/.local/share/cse/zotero"
runtime_bin_dir="$HOME/.local/bin"
runtime_commands=(cse-zotero zotero-companion)
legacy_names=(cse-sources cse-visualize scientific-codex)
expected_zotero_commit="2ec40ed1abe8eb63496f99d3d9e3f0575553453e"
codex_bin="${CSE_CODEX_BIN:-codex}"

usage() {
  echo "Usage: $0 --check [--zotero-source ABSOLUTE_CHECKOUT] | $0 --validate [--zotero-source ABSOLUTE_CHECKOUT]" >&2
}

mode=""
zotero_source=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --check|--validate)
      [[ -z "$mode" ]] || { usage; exit 2; }
      mode="${1#--}"
      ;;
    --zotero-source)
      [[ $# -ge 2 && "$2" = /* ]] || { echo "--zotero-source requires an absolute checkout" >&2; exit 2; }
      zotero_source="$2"
      shift
      ;;
    *) usage; exit 2 ;;
  esac
  shift
done
[[ -n "$mode" ]] || { usage; exit 2; }

if [[ -z "$zotero_source" && -d "$repository_root/../cse-zotero" ]]; then
  zotero_source="$(cd "$repository_root/../cse-zotero" && pwd)"
fi
if [[ -z "$zotero_source" || ! -d "$zotero_source" ]]; then
  echo "Zotero source capability unavailable; pass --zotero-source <absolute-checkout>." >&2
  exit 1
fi

if [[ ! -d "$zotero_source/.git" && ! -f "$zotero_source/.git" ]]; then
  echo "Zotero source capability unavailable: --zotero-source must be a Git checkout." >&2
  exit 1
fi
zotero_commit="$(git -C "$zotero_source" rev-parse HEAD 2>/dev/null || true)"
if [[ "$zotero_commit" != "$expected_zotero_commit" ]]; then
  echo "Zotero source revision mismatch: expected $expected_zotero_commit, got ${zotero_commit:-unavailable}." >&2
  exit 1
fi
if [[ ! -f "$zotero_source/pyproject.toml" ]]; then
  echo "Zotero source capability unavailable: pyproject.toml is missing." >&2
  exit 1
fi
command -v uv >/dev/null || { echo "Zotero runtime capability unavailable: uv is missing; install uv." >&2; exit 1; }
if [[ -z "${UV_CACHE_DIR:-}" ]]; then
  UV_CACHE_DIR="$(uv cache dir)"
fi
export UV_CACHE_DIR

if [[ "$mode" == validate && -n "$(git -C "$repository_root" status --porcelain)" ]]; then
  echo "Refusing to deploy an uncommitted source tree." >&2
  exit 1
fi

python3 "$repository_root/scripts/package_inventory.py" check cse
"$repository_root/scripts/validate.sh"

transaction="$(mktemp -d /tmp/cse-runtime.XXXXXX)"
export XDG_CACHE_HOME="$transaction/xdg-cache"
export XDG_DATA_HOME="$transaction/xdg-data"
runtime_source="$transaction/zotero-source"
runtime_wheels="$transaction/wheels"
runtime_venv="$transaction/venv"
unrelated="$transaction/unrelated"
mkdir -p "$runtime_source" "$runtime_wheels" "$unrelated"
trap 'rm -rf -- "$transaction"' EXIT

git -C "$zotero_source" archive "$expected_zotero_commit" | tar -x -C "$runtime_source"

uv build --wheel --out-dir "$runtime_wheels" "$runtime_source" >/dev/null
uv venv "$runtime_venv" >/dev/null
uv pip install --python "$runtime_venv/bin/python" "$runtime_wheels"/*.whl >/dev/null
schema_result="$(cd "$unrelated" && "$runtime_venv/bin/cse-zotero" schema-validate "$runtime_source/examples/core-records.yaml" --json)"
python3 -c 'import json,sys; value=json.load(sys.stdin); raise SystemExit(0 if value.get("ok") is True else 1)' <<<"$schema_result"
alias_result="$(cd "$unrelated" && "$runtime_venv/bin/zotero-companion" schema-validate "$runtime_source/examples/core-records.yaml" --json)"
python3 -c 'import json,sys; value=json.load(sys.stdin); raise SystemExit(0 if value.get("ok") is True else 1)' <<<"$alias_result"
explicit_result="$(cd "$unrelated" && "$runtime_venv/bin/cse-zotero" schema-validate "$runtime_source/examples/thermophysical-record.yaml" --schema "$runtime_source/src/zotero_companion/schemas/linkml/thermophysical.yaml" --class ThermophysicalRecord --json)"
python3 -c 'import json,sys; value=json.load(sys.stdin); raise SystemExit(0 if value.get("ok") is True else 1)' <<<"$explicit_result"

plugin_commit="$(git -C "$repository_root" rev-parse HEAD)"
plugin_identity="$(python3 "$repository_root/scripts/package_inventory.py" stage cse "$transaction/cse" --commit "$plugin_commit" --home "$HOME")"
payload_sha256="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["runtimeTreeSha256"])' <<<"$plugin_identity")"
identity_json() {
  python3 -c 'import json,sys; print(json.dumps({"payloadSha256":sys.argv[1],"pluginCommit":sys.argv[2],"runtime":sys.argv[3],"zoteroCommit":sys.argv[4]}, sort_keys=True))' "$payload_sha256" "$plugin_commit" "$1" "$zotero_commit"
}
if [[ "$mode" == check ]]; then
  identity_json "wheel and default/explicit schema checks passed"
  exit 0
fi

if ! command -v "$codex_bin" >/dev/null; then
  echo "Codex plugin capability unavailable: supported codex CLI is missing." >&2
  exit 1
fi
mkdir -p "$deploy_parent" "$(dirname "$runtime_target")"
previous="$transaction/previous"
mkdir -p "$previous"
committed=0
source_swap_started=0
candidate_installed=0
runtime_swap_started=0
runtime_installed=0
acquired_bin_commands=()
marketplace_changed=0
personal_marketplace_added=0
if [[ -f "$marketplace" ]]; then cp -- "$marketplace" "$previous/marketplace"; else touch "$previous/marketplace.absent"; fi
while IFS= read -r name; do
  target="$deploy_parent/$name"
  if [[ -e "$target" || -L "$target" ]]; then
    installed_name="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["name"])' "$target/.codex-plugin/plugin.json" 2>/dev/null || true)"
    if [[ "$installed_name" != "$name" ]]; then
      echo "Refusing unexpected directory at $target" >&2
      exit 1
    fi
  fi
done < <(printf '%s\n' cse "${legacy_names[@]}")
codex_before="$previous/codex-list.json"
"$codex_bin" plugin list --json > "$codex_before"
marketplaces_before="$previous/codex-marketplaces.json"
"$codex_bin" plugin marketplace list --json > "$marketplaces_before"
family_names() {
  python3 - "$1" <<'PY'
import json, sys
data = json.load(open(sys.argv[1]))
family = {"cse", "cse-sources", "cse-visualize", "scientific-codex"}
seen = set()
for entry in data.get("installed", []):
    name = str(entry.get("pluginId", "")).split("@", 1)[0]
    if name in family:
        if entry.get("pluginId") != f"{name}@personal" or name in seen:
            raise SystemExit(f"unexpected duplicate or marketplace for {name}")
        seen.add(name)
        print(name)
PY
}
family_file="$previous/family-names"
family_names "$codex_before" > "$family_file"
personal_was_configured="$(python3 - "$marketplaces_before" <<'PY'
import json, sys
data = json.load(open(sys.argv[1]))
print(int(any(item.get("name") == "personal" and item.get("marketplaceSource")
             for item in data.get("marketplaces", []))))
PY
)"

rollback() {
  local exit_status=$?
  if [[ "$committed" -eq 1 ]]; then
    rm -rf -- "$transaction"
    return "$exit_status"
  fi

  local rollback_failed=0
  local failed_roots="$transaction/failed-roots"
  mkdir -p "$failed_roots"

  if [[ "$candidate_installed" -eq 1 && ( -e "$deploy_parent/cse" || -L "$deploy_parent/cse" ) ]]; then
    if ! mv -- "$deploy_parent/cse" "$failed_roots/cse"; then
      echo "Rollback failed while preserving the candidate CSE source." >&2
      rollback_failed=1
    fi
  fi
  if [[ "$source_swap_started" -eq 1 ]]; then
    while IFS= read -r name; do
      [[ -z "$name" ]] && continue
      backup="$previous/plugin-roots/$name"
      if [[ -e "$backup" || -L "$backup" ]]; then
        current="$deploy_parent/$name"
        if [[ -e "$current" || -L "$current" ]]; then
          if ! mv -- "$current" "$failed_roots/$name-current"; then
            echo "Rollback failed while preserving the current $name source." >&2
            rollback_failed=1
            continue
          fi
        fi
        if ! mv -- "$backup" "$current"; then
          echo "Rollback failed while restoring the $name source." >&2
          rollback_failed=1
        fi
      fi
    done < <(printf '%s\n' cse "${legacy_names[@]}")
  fi

  if [[ "$runtime_installed" -eq 1 && ( -e "$runtime_target" || -L "$runtime_target" ) ]]; then
    if ! mv -- "$runtime_target" "$transaction/failed-runtime"; then
      echo "Rollback failed while preserving the installed Zotero runtime." >&2
      rollback_failed=1
    fi
  fi
  if [[ "$runtime_swap_started" -eq 1 && -e "$previous/runtime" ]]; then
    if ! mv -- "$previous/runtime" "$runtime_target"; then
      echo "Rollback failed while restoring the Zotero runtime." >&2
      rollback_failed=1
    fi
  fi

  if [[ "${#acquired_bin_commands[@]}" -gt 0 ]]; then
    mkdir -p "$transaction/failed-bin"
    for command in "${acquired_bin_commands[@]}"; do
      current="$runtime_bin_dir/$command"
      backup="$previous/bin/$command"
      if [[ -e "$current" || -L "$current" ]]; then
        if ! mv -- "$current" "$transaction/failed-bin/$command"; then
          echo "Rollback failed while preserving the new $command entry." >&2
          rollback_failed=1
          continue
        fi
      fi
      if [[ -e "$backup" || -L "$backup" ]]; then
        if ! mv -- "$backup" "$current"; then
          echo "Rollback failed while restoring the prior $command entry." >&2
          rollback_failed=1
        fi
      fi
    done
  fi

  if [[ "$marketplace_changed" -eq 1 ]]; then
    mkdir -p "$(dirname "$marketplace")"
    if [[ -e "$previous/marketplace" ]]; then
      if ! cp -- "$previous/marketplace" "$marketplace"; then
        echo "Rollback failed while restoring the personal marketplace manifest." >&2
        rollback_failed=1
      fi
    elif ! rm -f -- "$marketplace"; then
      echo "Rollback failed while removing the transaction marketplace manifest." >&2
      rollback_failed=1
    fi
  fi

  current_codex="$transaction/rollback-codex-list.json"
  current_family="$transaction/rollback-family-names"
  if ! "$codex_bin" plugin list --json > "$current_codex"; then
    echo "Rollback failed while reading the current Codex plugin state." >&2
    rollback_failed=1
  elif ! family_names "$current_codex" > "$current_family"; then
    echo "Rollback failed because the current Codex plugin state is invalid." >&2
    rollback_failed=1
  else
    while IFS= read -r name; do
      [[ -z "$name" ]] && continue
      if ! "$codex_bin" plugin remove "$name@personal" --json >/dev/null; then
        echo "Rollback failed while removing $name@personal." >&2
        rollback_failed=1
      fi
    done < "$current_family"
    while IFS= read -r name; do
      [[ -z "$name" ]] && continue
      if ! "$codex_bin" plugin add "$name@personal" --json >/dev/null; then
        echo "Rollback failed while re-adding $name@personal; transaction preserved at $transaction." >&2
        rollback_failed=1
      fi
    done < "$family_file"
  fi

  if [[ "$personal_marketplace_added" -eq 1 ]]; then
    if ! "$codex_bin" plugin marketplace remove personal --json >/dev/null; then
      echo "Rollback failed while removing the transaction marketplace registration; transaction preserved at $transaction." >&2
      rollback_failed=1
    fi
  fi

  if [[ "$rollback_failed" -ne 0 ]]; then
    echo "Rollback failed; transaction preserved at $transaction for recovery." >&2
    return "$exit_status"
  fi
  rm -rf -- "$transaction"
  return "$exit_status"
}
trap rollback EXIT

mkdir -p "$previous/plugin-roots"
source_swap_started=1
while IFS= read -r name; do
  if [[ -e "$deploy_parent/$name" || -L "$deploy_parent/$name" ]]; then
    mv -- "$deploy_parent/$name" "$previous/plugin-roots/$name"
  else
    touch "$previous/plugin-roots/$name.absent"
  fi
done < <(printf '%s\n' cse "${legacy_names[@]}")
runtime_swap_started=1
if [[ -e "$runtime_target" || -L "$runtime_target" ]]; then
  mv -- "$runtime_target" "$previous/runtime"
else
  touch "$previous/runtime.absent"
fi
mkdir -p "$previous/bin" "$runtime_bin_dir"
for command in "${runtime_commands[@]}"; do
  if [[ "${CSE_FAIL_AT:-}" == "bin-backup:before:$command" ]]; then
    echo "Injected failure at bin-backup:before:$command" >&2
    exit 1
  fi
  if [[ -e "$runtime_bin_dir/$command" || -L "$runtime_bin_dir/$command" ]]; then
    mv -- "$runtime_bin_dir/$command" "$previous/bin/$command"
  else
    touch "$previous/bin/$command.absent"
  fi
  acquired_bin_commands+=("$command")
done
mv -- "$transaction/cse" "$deploy_parent/cse"
candidate_installed=1

marketplace_changed=1
python3 "$repository_root/scripts/register_marketplace.py" --marketplace "$marketplace"
marketplace_add_result="$("$codex_bin" plugin marketplace add "$HOME" --json)"
if [[ "$personal_was_configured" -eq 0 ]]; then
  already_added="$(python3 -c 'import json,sys; print(int(json.load(sys.stdin).get("alreadyAdded", False)))' <<<"$marketplace_add_result")"
  if [[ "$already_added" -eq 0 ]]; then
    personal_marketplace_added=1
  fi
fi
marketplaces_after="$transaction/codex-marketplaces-after.json"
"$codex_bin" plugin marketplace list --json > "$marketplaces_after"
python3 - "$marketplaces_after" "$HOME" <<'PY'
import json, sys
from pathlib import Path
data = json.load(open(sys.argv[1]))
home = Path(sys.argv[2]).resolve()
if not any(item.get("name") == "personal" and Path(item.get("root", "")).resolve() == home
           for item in data.get("marketplaces", [])):
    raise SystemExit("personal marketplace is not registered at the home root")
PY

while IFS= read -r name; do
  [[ -z "$name" ]] || "$codex_bin" plugin remove "$name@personal" --json >/dev/null
done < "$family_file"
"$codex_bin" plugin add cse@personal --json >/dev/null

if [[ "${CSE_FAIL_AT:-}" == "runtime:before-install" ]]; then
  echo "Injected failure at runtime:before-install" >&2
  exit 1
fi
runtime_installed=1
uv venv "$runtime_target" >/dev/null
uv pip install --python "$runtime_target/bin/python" "$runtime_wheels"/*.whl >/dev/null
for command in "${runtime_commands[@]}"; do
  [[ -x "$runtime_target/bin/$command" ]] || {
    echo "Zotero runtime capability unavailable: installed $command entry point is missing." >&2
    exit 1
  }
  ln -s "$runtime_target/bin/$command" "$runtime_bin_dir/$command"
  [[ -x "$runtime_bin_dir/$command" ]] || {
    echo "Zotero runtime capability unavailable: $runtime_bin_dir/$command is not executable." >&2
    exit 1
  }
done
installed_result="$(cd "$unrelated" && "$runtime_bin_dir/cse-zotero" schema-validate "$runtime_source/examples/core-records.yaml" --json)"
python3 -c 'import json,sys; value=json.load(sys.stdin); raise SystemExit(0 if value.get("ok") is True else 1)' <<<"$installed_result"
installed_alias_result="$(cd "$unrelated" && "$runtime_bin_dir/zotero-companion" schema-validate "$runtime_source/examples/core-records.yaml" --json)"
python3 -c 'import json,sys; value=json.load(sys.stdin); raise SystemExit(0 if value.get("ok") is True else 1)' <<<"$installed_alias_result"
if [[ "${CSE_FAIL_AT:-}" == "late:after-runtime" ]]; then
  echo "Injected failure at late:after-runtime" >&2
  exit 1
fi

python3 "$repository_root/scripts/check-installed.py" --all --home "$HOME"
committed=1
identity_json "installed wheel and schema checks passed"
echo "Deployed unified CSE plugin through the supported Codex CLI."
