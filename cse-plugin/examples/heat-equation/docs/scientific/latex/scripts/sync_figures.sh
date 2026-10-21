#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
latex_root="$(cd -- "$script_dir/.." && pwd)"
repo_root="$(cd -- "$latex_root/../../.." && pwd)"
destination="$latex_root/figures"
mkdir -p -- "$destination"

declare -A sources=(
  [solution_overlay.pdf]="analyses/heat_verification/figures/solution_overlay/output/solution_overlay.pdf"
  [refinement.pdf]="analyses/heat_verification/figures/refinement/output/refinement.pdf"
  [amplification.pdf]="analyses/heat_verification/figures/amplification/output/amplification.pdf"
)

for name in "${!sources[@]}"; do
  source_path="$repo_root/${sources[$name]}"
  if [[ ! -s "$source_path" || -L "$source_path" ]]; then
    printf 'retained analysis figure is unavailable: %s\n' "$source_path" >&2
    exit 1
  fi
  if ! cmp -s -- "$source_path" "$destination/$name" 2>/dev/null; then
    cp -- "$source_path" "$destination/$name"
    chmod 0644 "$destination/$name"
  fi
done

printf '%s\n' "Manuscript figures are synchronized."
