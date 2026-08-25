#!/usr/bin/env bash
set -euo pipefail

showcase_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(cd "$showcase_root/../.." && pwd)"

cd "$showcase_root"
quarto render article.qmd
quarto render deck.qmd

python3 "$repository_root/scripts/latex_visual_qa.py" builds/article.pdf \
  --profile article --output-dir builds/visual-qa/article --contact-sheet
python3 "$repository_root/scripts/latex_visual_qa.py" builds/deck.pdf \
  --profile beamer --output-dir builds/visual-qa/deck --contact-sheet

mkdir -p "$repository_root/output/pdf"
cp builds/article.pdf "$repository_root/output/pdf/chemical-engineering-quarto-article.pdf"
cp builds/deck.pdf "$repository_root/output/pdf/chemical-engineering-quarto-beamer.pdf"

printf 'Created %s\n' "$repository_root/output/pdf/chemical-engineering-quarto-article.pdf"
printf 'Created %s\n' "$repository_root/output/pdf/chemical-engineering-quarto-beamer.pdf"
printf 'Review visual QA packets under %s\n' "$showcase_root/builds/visual-qa"
