#!/usr/bin/env bash
set -euo pipefail

plugin_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
plugin_validator="${SCIENTIFIC_CODEX_PLUGIN_VALIDATOR:-$HOME/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py}"
skill_validator="${SCIENTIFIC_CODEX_SKILL_VALIDATOR:-$HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py}"

for validator in "$plugin_validator" "$skill_validator"; do
  if [[ ! -f "$validator" ]]; then
    echo "Required Codex validator is unavailable: $validator" >&2
    exit 1
  fi
done

python3 "$plugin_validator" "$plugin_root"
for skill in "$plugin_root"/skills/*; do
  python3 "$skill_validator" "$skill"
done
python3 -m unittest discover -s "$plugin_root/tests" -v
python3 "$plugin_root/scripts/check_prose.py" \
  "$plugin_root/.codex-plugin" "$plugin_root/skills" "$plugin_root/references" \
  "$plugin_root/assets" "$plugin_root/README.md" "$plugin_root/AGENTS.md"

if rg -n '\[TODO|TODO:' "$plugin_root/.codex-plugin" "$plugin_root/skills" "$plugin_root/references" "$plugin_root/assets"; then
  echo "Unresolved placeholder found." >&2
  exit 1
fi

bash -n "$plugin_root/scripts/validate.sh" "$plugin_root/scripts/sync-live.sh"
echo "Scientific Codex validation passed."
