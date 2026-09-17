#!/usr/bin/env bash
set -euo pipefail

if [[ -f manuscript.py || -f _cse-manuscript.json ]]; then
  python3 ./manuscript.py validate .
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

# Rendering must neither install TeX packages nor execute document code.
quarto render "$@" -M latex-auto-install:false --no-execute
