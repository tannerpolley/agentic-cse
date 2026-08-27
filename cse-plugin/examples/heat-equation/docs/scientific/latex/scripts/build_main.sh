#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
latex_root="$(cd -- "$script_dir/.." && pwd)"
repo_root="$(cd -- "$latex_root/../../.." && pwd)"

bash "$repo_root/scripts/sync_bibliography.sh" --check
bash "$script_dir/sync_figures.sh"
mkdir -p -- "$latex_root/builds"
cd "$latex_root"
latexmk -pdf -interaction=nonstopmode -halt-on-error -file-line-error \
  -outdir=builds main.tex

if [[ ! -s "$latex_root/builds/main.pdf" ]]; then
  printf '%s\n' "manuscript build did not produce builds/main.pdf" >&2
  exit 1
fi
if rg -n "Citation.*undefined|There were undefined references" \
    "$latex_root/builds/main.log"; then
  printf '%s\n' "manuscript contains unresolved citations or references" >&2
  exit 1
fi

printf '%s\n' "Tutorial manuscript built: docs/scientific/latex/builds/main.pdf"
