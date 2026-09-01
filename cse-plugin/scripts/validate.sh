#!/usr/bin/env bash
set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
plugin_validator="${CSE_PLUGIN_VALIDATOR:-$HOME/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py}"
skill_validator="${CSE_SKILL_VALIDATOR:-$HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py}"

for validator in "$plugin_validator" "$skill_validator"; do
  if [[ ! -f "$validator" ]]; then
    echo "Required Codex validator is unavailable: $validator" >&2
    exit 1
  fi
done

package_roots=()
while IFS=$'\t' read -r package_name package_root _; do
  package_roots+=("$package_root")
  if [[ "${CSE_FAIL_AT:-}" == "validate:before:$package_name" ]]; then
    echo "Injected failure at validate:before:$package_name" >&2
    exit 1
  fi
  python3 "$plugin_validator" "$package_root"
  for skill in "$package_root"/skills/*; do
    python3 "$skill_validator" "$skill"
  done
  if [[ "${CSE_FAIL_AT:-}" == "validate:after:$package_name" ]]; then
    echo "Injected failure at validate:after:$package_name" >&2
    exit 1
  fi
done < <(python3 "$repository_root/scripts/package_inventory.py" list)

python3 -m unittest discover -s "$repository_root/tests" -v
python3 "$repository_root/scripts/install_cse_hooks.py" --check
for package_root in "${package_roots[@]}"; do
  prose_paths=("$package_root/.codex-plugin" "$package_root/skills")
  for optional in references assets README.md AGENTS.md; do
    [[ ! -e "$package_root/$optional" ]] || prose_paths+=("$package_root/$optional")
  done
  python3 "$repository_root/scripts/check_prose.py" "${prose_paths[@]}"
done

if rg -n '\[TODO|TODO:' --glob '!scripts/validate.sh' "${package_roots[@]}"; then
  echo "Unresolved placeholder found." >&2
  exit 1
fi

bash -n "$repository_root/scripts/validate.sh" "$repository_root/scripts/sync-live.sh" \
  "$repository_root/extensions/cse-visualize/scripts/cache-latex-manuals.sh" \
  "$repository_root/extensions/cse-visualize/scripts/check-latex-toolchain.sh" \
  "$repository_root/extensions/cse-visualize/assets/project/quarto/render.sh"
echo "CSE family validation passed."
