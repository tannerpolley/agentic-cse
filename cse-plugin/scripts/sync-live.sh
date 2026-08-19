#!/usr/bin/env bash
set -euo pipefail

plugin_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
deploy_root="${CSE_DEPLOY_ROOT:-$HOME/.codex/plugins/cse}"
expected_root="$HOME/.codex/plugins/cse"
validator="${CSE_PLUGIN_VALIDATOR:-$HOME/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py}"

if [[ "${1:-}" != "--validate" || $# -ne 1 ]]; then
  echo "Usage: $0 --validate" >&2
  exit 2
fi
if [[ "$deploy_root" != "$expected_root" ]]; then
  echo "Refusing unexpected deployment target: $deploy_root" >&2
  exit 1
fi
if [[ -n "$(git -C "$plugin_root" status --porcelain)" ]]; then
  echo "Refusing to deploy an uncommitted source tree." >&2
  exit 1
fi

"$plugin_root/scripts/validate.sh"
mkdir -p "$(dirname "$deploy_root")"
next_root="$(mktemp -d "$HOME/.codex/plugins/.cse.next.XXXXXX")"
previous_root="${deploy_root}.previous.$$"
cleanup() {
  [[ ! -d "$next_root" ]] || rm -rf -- "$next_root"
}
trap cleanup EXIT

rsync -a --delete \
  --exclude .git --exclude .venv --exclude .pytest_cache --exclude tests \
  "$plugin_root/" "$next_root/"
python3 "$validator" "$next_root"

if [[ -e "$deploy_root" ]]; then
  mv -- "$deploy_root" "$previous_root"
fi
if ! mv -- "$next_root" "$deploy_root"; then
  [[ ! -e "$previous_root" ]] || mv -- "$previous_root" "$deploy_root"
  exit 1
fi
if ! python3 "$plugin_root/scripts/register_marketplace.py"; then
  if mv -- "$deploy_root" "$next_root"; then
    [[ ! -e "$previous_root" ]] || mv -- "$previous_root" "$deploy_root"
  else
    echo "Marketplace registration and deployment rollback both failed." >&2
  fi
  exit 1
fi
[[ ! -e "$previous_root" ]] || rm -rf -- "$previous_root"
echo "Deployed CSE to $deploy_root"
