#!/usr/bin/env bash
set -euo pipefail

showcase_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(cd "$showcase_root/../.." && pwd)"
render="$repository_root/plugin/assets/visualize/project/quarto/render.sh"
visual_qa="$repository_root/plugin/scripts/visualize/latex_visual_qa.py"

cd "$showcase_root"
"$render" article.qmd --to pdf
"$render" deck.qmd --to beamer

python3 "$visual_qa" builds/article.pdf \
  --profile article --output-dir builds/visual-qa/article --contact-sheet
python3 "$visual_qa" builds/deck.pdf \
  --profile beamer --output-dir builds/visual-qa/deck --contact-sheet

mkdir -p "$repository_root/output/pdf"
cp builds/article.pdf "$repository_root/output/pdf/chemical-engineering-quarto-article.pdf"
cp builds/deck.pdf "$repository_root/output/pdf/chemical-engineering-quarto-beamer.pdf"

printf 'Created %s\n' "$repository_root/output/pdf/chemical-engineering-quarto-article.pdf"
printf 'Created %s\n' "$repository_root/output/pdf/chemical-engineering-quarto-beamer.pdf"
printf 'Review visual QA packets under %s\n' "$showcase_root/builds/visual-qa"
