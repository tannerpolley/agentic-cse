#!/usr/bin/env bash
set -euo pipefail

example_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
render="$(cd "$example_root/.." && pwd)/render.sh"

cd "$example_root"
mkdir -p builds/figures figures/generated
dvilualatex -interaction=nonstopmode -halt-on-error \
  -output-directory=builds/figures figures/profile-standalone.tex >/dev/null
dvisvgm --exact --font-format=woff2 \
  --output=figures/generated/profile.svg \
  builds/figures/profile-standalone.dvi >/dev/null
"$render" notebook.qmd
"$render" notebook.qmd --profile promoted-pdf --to pdf
printf 'Created %s\n' "$example_root/builds/notebook.pdf"
printf 'Created %s\n' "$example_root/builds/notebook.html"
