#!/usr/bin/env bash
set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
runtime_target="$HOME/.local/share/cse/zotero"
runtime_bin_dir="$HOME/.local/bin"
runtime_commands=(cse-zotero zotero-companion)
codex_bin="${CSE_CODEX_BIN:-codex}"

usage() {
  echo "Usage: $0 --check | $0 --validate" >&2
}

mode=""
case "${1:-}" in
  --check|--validate) [[ $# -eq 1 ]] || { usage; exit 2; }; mode="${1#--}" ;;
  *) usage; exit 2 ;;
esac

# The Zotero runtime is built from the sibling cse-zotero/ folder at the same
# commit as this plugin.
zotero_commit="$(git -C "$repository_root" rev-parse HEAD)"
if ! git -C "$repository_root/.." cat-file -e HEAD:cse-zotero/pyproject.toml 2>/dev/null; then
  echo "Zotero source capability unavailable: cse-zotero/pyproject.toml is not committed beside cse-plugin/." >&2
  exit 1
fi
command -v uv >/dev/null || { echo "Zotero runtime capability unavailable: uv is missing; install uv." >&2; exit 1; }
if [[ -z "${UV_CACHE_DIR:-}" ]]; then
  UV_CACHE_DIR="$(uv cache dir)"
fi
export UV_CACHE_DIR

if [[ "$mode" == validate && -n "$(git -C "$repository_root" status --porcelain -- .)" ]]; then
  echo "Refusing to deploy an uncommitted source tree." >&2
  exit 1
fi

if [[ "$mode" == validate ]]; then
  command -v "$codex_bin" >/dev/null || { echo "Codex plugin capability unavailable: supported codex CLI is missing." >&2; exit 1; }
  # Read-only preflight: the `cse` marketplace must be absent or already rooted at this checkout.
  codex_state="$(python3 - "$repository_root" "$("$codex_bin" plugin marketplace list --json)" "$("$codex_bin" plugin list --json)" <<'PY'
import json, sys
from pathlib import Path
root = Path(sys.argv[1]).resolve()
marketplaces = [item for item in json.loads(sys.argv[2]).get("marketplaces", []) if item.get("name") == "cse"]
if marketplaces and Path(marketplaces[0].get("root", "")).resolve() != root:
    raise SystemExit(f"Codex marketplace 'cse' is rooted at {marketplaces[0].get('root')}, not {root}; remove it with `codex plugin marketplace remove cse` first.")
entries = [entry for entry in json.loads(sys.argv[3]).get("installed", []) if entry.get("installed")]
others = sorted({entry.get("pluginId") for entry in entries
                 if str(entry.get("pluginId", "")).split("@", 1)[0] == "cse" and entry.get("pluginId") != "cse@cse"})
if others:
    raise SystemExit(f"Another cse install would duplicate every skill: {others}; remove each with `codex plugin remove <id>` first.")
installed = any(entry.get("pluginId") == "cse@cse" for entry in entries)
print(int(bool(marketplaces)), int(installed))
PY
)"
  read -r marketplace_was_present cse_was_installed <<<"$codex_state"
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

git -C "$repository_root/.." archive "$zotero_commit:cse-zotero" | tar -x -C "$runtime_source"

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
plugin_identity="$(python3 "$repository_root/scripts/package_inventory.py" stage cse "$transaction/cse" --commit "$plugin_commit")"
payload_sha256="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["runtimeTreeSha256"])' <<<"$plugin_identity")"
report_preview_roots() {
  python3 - "$repository_root/plugin" "$transaction/cse" "$plugin_commit" "$payload_sha256" <<'PY'
import json
from pathlib import Path
import runpy
import shlex
import subprocess
import sys

plugin, payload, commit, digest = sys.argv[1:]
assets = Path(payload) / "assets/visualize/project/quarto"
tooling = [name for name in runpy.run_path(str(assets / "manuscript.py"))["TOOLING_FILES"]
           if name != ".cse-quarto-source.json"]
try:
    units = subprocess.run(["systemctl", "--user", "list-units", "--all", "--type=service",
                            "cse-preview-*.service", "--no-legend", "--plain"],
                           text=True, capture_output=True, check=True).stdout
except (OSError, subprocess.CalledProcessError):
    raise SystemExit(0)
for line in units.splitlines():
    unit = line.split()[0]
    root = None
    try:
        details = subprocess.run(["systemctl", "--user", "show", unit, "-p", "WorkingDirectory", "-p", "ExecStart"],
                                 text=True, capture_output=True, check=True).stdout
        fields = dict(item.split("=", 1) for item in details.splitlines() if "=" in item)
        argv = shlex.split(fields["ExecStart"].split("argv[]=", 1)[1].split(" ;", 1)[0])
        root = Path(fields["WorkingDirectory"]) / argv[argv.index("preview") + 1]
        json.loads((root / ".cse-quarto-source.json").read_text())
        changed = [name for name in tooling if not (root / name).is_file()
                   or (root / name).read_bytes() != (assets / name).read_bytes()]
        if not changed:
            continue
        reason = "older tooling: " + ", ".join(changed)
    except (OSError, ValueError, KeyError, IndexError, AttributeError, subprocess.CalledProcessError):
        if root is None:
            print(f"Preview {unit}: unreadable unit or root")
            continue
        reason = "unreadable or missing source record"
    command = shlex.join(["python3", str(Path(plugin) / "assets/visualize/project/quarto/manuscript.py"),
                          "init", str(root), "--article-source", str(root / "index.qmd"),
                          "--source-commit", commit, "--runtime-tree-sha256", digest])
    print(f"Preview {root}: {reason}; upgrade: {command}")
PY
}
identity_json() {
  python3 -c 'import json,sys; print(json.dumps({"payloadSha256":sys.argv[1],"pluginCommit":sys.argv[2],"runtime":sys.argv[3],"zoteroCommit":sys.argv[4]}, sort_keys=True))' "$payload_sha256" "$plugin_commit" "$1" "$zotero_commit"
}
if [[ "$mode" == check ]]; then
  registry_root="$transaction/data-registry/thermophysical/source/registry"
  analysis_dir="$transaction/analysis"
  mkdir -p "$registry_root"
  registration_result="$("$runtime_venv/bin/cse-zotero" data-register "$runtime_source/examples/data-register/package" --registry-root "$registry_root" --apply --json)"
  selection_result="$("$runtime_venv/bin/cse-zotero" data-select ds:registered-mea-density --resource observations.csv --analysis "$analysis_dir" --registry-root "$registry_root" --apply --json)"
  query_result="$("$runtime_venv/bin/cse-zotero" data-query "$analysis_dir/inputs/observations.csv" --sql "SELECT value, value_unit FROM records" --json)"
  python3 - "$registration_result" "$selection_result" "$query_result" "$analysis_dir" <<'PY'
import hashlib
import json
from pathlib import Path
import sys

registration, selection, query = (json.loads(value) for value in sys.argv[1:4])
analysis = Path(sys.argv[4])
input_path = analysis / "inputs/observations.csv"
lineage_path = analysis / "inputs/observations.csv.lineage.json"
if registration.get("mode") != "apply" or registration.get("record_id") != "ds:registered-mea-density":
    raise SystemExit("installed wheel did not register the repository fixture")
if selection.get("ok") is not True or selection.get("record_id") != "ds:registered-mea-density":
    raise SystemExit("installed wheel did not select the registered fixture")
if selection.get("input_path") != str(input_path) or selection.get("lineage_path") != str(lineage_path):
    raise SystemExit("installed wheel selected the fixture into an unexpected analysis path")
if query.get("table") != str(input_path) or query.get("rows") != [{"value": 1010.2, "value_unit": "kg/m3"}]:
    raise SystemExit("installed wheel query did not return the known fixture value")
if not input_path.is_file() or not lineage_path.is_file():
    raise SystemExit("installed wheel did not retain the selected input and lineage")
lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
if lineage.get("record_id") != "ds:registered-mea-density":
    raise SystemExit("selected lineage has the wrong registered record")
if lineage.get("source", {}).get("locator") != {"kind": "table", "value": "Table 2, row 1"}:
    raise SystemExit("selected lineage lost the source table locator")
if lineage.get("composition_basis") != "pure component":
    raise SystemExit("selected lineage lost the composition basis")
if lineage.get("resource", {}).get("sha256") != hashlib.sha256(input_path.read_bytes()).hexdigest():
    raise SystemExit("selected lineage hash does not match the analysis input")
PY
  report_preview_roots || echo "Preview-root report did not run (exit $?)." >&2
  identity_json "installed wheel schema and data-register/data-select/query lineage checks passed"
  exit 0
fi

mkdir -p "$(dirname "$runtime_target")"
previous="$transaction/previous"
mkdir -p "$previous"
committed=0
runtime_swap_started=0
runtime_installed=0
acquired_bin_commands=()
marketplace_added=0
plugin_added=0

# Rollback restores the Zotero runtime and command entries, and undoes the
# Codex marketplace and cse@cse install only when this run created them. A local
# marketplace keeps no prior plugin snapshot, so a cse@cse that was already
# installed keeps the refreshed cache of this validated commit.
rollback() {
  local exit_status=$?
  if [[ "$committed" -eq 1 ]]; then
    rm -rf -- "$transaction"
    return "$exit_status"
  fi

  local rollback_failed=0
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

  if [[ "$plugin_added" -eq 1 && "$cse_was_installed" -eq 0 ]]; then
    if ! "$codex_bin" plugin remove cse@cse --json >/dev/null; then
      echo "Rollback failed while removing cse@cse." >&2
      rollback_failed=1
    fi
  elif [[ "$plugin_added" -eq 1 ]]; then
    echo "cse@cse was already installed; it stays installed with this commit's refreshed cache." >&2
  fi
  if [[ "$marketplace_added" -eq 1 ]]; then
    if ! "$codex_bin" plugin marketplace remove cse --json >/dev/null; then
      echo "Rollback failed while removing the cse marketplace registration." >&2
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

runtime_installed=1
uv venv "$runtime_target" >/dev/null
# Chrome loads the unpacked agent Connector from inside the runtime; keep it.
if [[ -d "$previous/runtime/zotero-connector-agent" ]]; then
  cp -a -- "$previous/runtime/zotero-connector-agent" "$runtime_target/"
fi
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

# Codex reads this repository's marketplace; `plugin add` recopies the local
# `./plugin` source into the Codex cache, so it both installs and refreshes.
[[ "$marketplace_was_present" -eq 1 ]] || marketplace_added=1
"$codex_bin" plugin marketplace add "$repository_root" --json >/dev/null
plugin_added=1
"$codex_bin" plugin add cse@cse --json >/dev/null
if [[ "${CSE_FAIL_AT:-}" == "late:after-install" ]]; then
  echo "Injected failure at late:after-install" >&2
  exit 1
fi

python3 "$repository_root/scripts/check-installed.py"
committed=1
report_preview_roots || echo "Preview-root report did not run (exit $?)." >&2
identity_json "installed wheel and schema checks passed"
echo "Installed cse@cse from the repository marketplace and the Zotero runtime."
