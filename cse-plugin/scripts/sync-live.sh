#!/usr/bin/env bash
set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
deploy_parent="$HOME/.codex/plugins"
marketplace="$HOME/.agents/plugins/marketplace.json"
legacy_root="$deploy_parent/scientific-codex"
validator="${CSE_PLUGIN_VALIDATOR:-$HOME/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py}"

if [[ "${1:-}" != "--validate" || $# -ne 1 ]]; then
  echo "Usage: $0 --validate" >&2
  exit 2
fi
if [[ -n "$(git -C "$repository_root" status --porcelain)" ]]; then
  echo "Refusing to deploy an uncommitted source tree." >&2
  exit 1
fi

"$repository_root/scripts/validate.sh"
mkdir -p "$deploy_parent"
transaction="$(mktemp -d "$deploy_parent/.cse-family.XXXXXX")"
staged="$transaction/staged"
previous="$transaction/previous"
mkdir -p "$staged" "$previous"
committed=0

rollback() {
  if [[ "$committed" -eq 0 ]]; then
    while IFS=$'\t' read -r package_name _ target; do
      if [[ -e "$previous/$package_name" ]]; then
        rm -rf -- "$target"
        mv -- "$previous/$package_name" "$target"
      elif [[ -e "$previous/$package_name.absent" ]]; then
        rm -rf -- "$target"
      fi
    done < <(python3 "$repository_root/scripts/package_inventory.py" list)
    if [[ -e "$previous/marketplace" ]]; then
      mkdir -p "$(dirname "$marketplace")"
      cp -- "$previous/marketplace" "$marketplace"
    elif [[ -e "$previous/marketplace.absent" ]]; then
      rm -f -- "$marketplace"
    fi
    if [[ -e "$previous/scientific-codex" ]]; then
      rm -rf -- "$legacy_root"
      mv -- "$previous/scientific-codex" "$legacy_root"
    fi
  fi
  rm -rf -- "$transaction"
}
trap rollback EXIT

commit="$(git -C "$repository_root" rev-parse HEAD)"
while IFS=$'\t' read -r package_name _ target; do
  case "$target" in
    "$deploy_parent"/cse|"$deploy_parent"/cse-sources|"$deploy_parent"/cse-visualize) ;;
    *) echo "Refusing unexpected deployment target: $target" >&2; exit 1 ;;
  esac
  if [[ -e "$target" ]]; then
    installed_name="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["name"])' "$target/.codex-plugin/plugin.json" 2>/dev/null || true)"
    if [[ "$installed_name" != "$package_name" ]]; then
      echo "Refusing unexpected directory at $target" >&2
      exit 1
    fi
  fi
  if [[ "${CSE_FAIL_AT:-}" == "stage:before:$package_name" ]]; then
    echo "Injected failure at stage:before:$package_name" >&2
    exit 1
  fi
  python3 "$repository_root/scripts/package_inventory.py" stage "$package_name" "$staged/$package_name" --commit "$commit"
  python3 "$validator" "$staged/$package_name"
  if [[ "${CSE_FAIL_AT:-}" == "stage:after:$package_name" ]]; then
    echo "Injected failure at stage:after:$package_name" >&2
    exit 1
  fi
done < <(python3 "$repository_root/scripts/package_inventory.py" list)

if [[ -f "$marketplace" ]]; then
  cp -- "$marketplace" "$previous/marketplace"
else
  touch "$previous/marketplace.absent"
fi
while IFS=$'\t' read -r package_name _ target; do
  if [[ -e "$target" ]]; then
    mv -- "$target" "$previous/$package_name"
  else
    touch "$previous/$package_name.absent"
  fi
done < <(python3 "$repository_root/scripts/package_inventory.py" list)

while IFS=$'\t' read -r package_name _ target; do
  if [[ "${CSE_FAIL_AT:-}" == "deploy:before:$package_name" ]]; then
    echo "Injected failure at deploy:before:$package_name" >&2
    exit 1
  fi
  mv -- "$staged/$package_name" "$target"
  if [[ "${CSE_FAIL_AT:-}" == "deploy:after:$package_name" ]]; then
    echo "Injected failure at deploy:after:$package_name" >&2
    exit 1
  fi
done < <(python3 "$repository_root/scripts/package_inventory.py" list)

python3 "$repository_root/scripts/register_marketplace.py" --keep-legacy
python3 "$repository_root/scripts/check-installed.py" --all --deployed-only

if [[ -d "$legacy_root" ]]; then
  legacy_name="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["name"])' "$legacy_root/.codex-plugin/plugin.json" 2>/dev/null || true)"
  if [[ "$legacy_name" == "scientific-codex" ]]; then
    mv -- "$legacy_root" "$previous/scientific-codex"
  else
    echo "Preserving unexpected directory at $legacy_root" >&2
  fi
fi
python3 "$repository_root/scripts/register_marketplace.py"

committed=1
echo "Deployed CSE family to $deploy_parent"
