#!/usr/bin/env bash
set -euo pipefail

project_directory="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "$project_directory/_cse-manuscript.json" ]]; then
  cd "$project_directory"
fi

if [[ -f _cse-manuscript.json ]] && { [[ ! -f _quarto.yml || ! -r _quarto.yml ]] ||
  grep -Eq "(^|[[:space:]{,])['\"]?(pre-render|post-render)['\"]?[[:space:]]*:" _quarto.yml; }; then
  echo "CSE Quarto render failed: provide a readable _quarto.yml without pre-render and post-render hooks" >&2
  exit 1
fi

runtime_root="$(mktemp -d "${TMPDIR:-/tmp}/cse-quarto.XXXXXX")"
trap 'rm -rf "$runtime_root"' EXIT

export TEXMFVAR="$runtime_root/tex"
export TEXMFCACHE="$TEXMFVAR"
export QUARTO_CACHE_DIR="$runtime_root/quarto"
export DENO_DIR="$runtime_root/deno"
export XDG_CACHE_HOME="$runtime_root/xdg"

for directory in "$TEXMFVAR" "$QUARTO_CACHE_DIR" "$DENO_DIR" "$XDG_CACHE_HOME"; do
  mkdir -p "$directory"
  [[ -w "$directory" ]] || {
    echo "CSE Quarto render failed: runtime directory is not writable: $directory" >&2
    exit 1
  }
done

# Select HTML unless the caller selects another format; page metadata may also declare PDF.
target_args=(--to html)
for argument in "$@"; do
  case "$argument" in
    --to|--to=*|-t|-t=*) target_args=(); break ;;
  esac
done

# Rendering must neither install TeX packages nor execute document code.
quarto render "$@" "${target_args[@]}" -M latex-auto-install:false --no-execute
