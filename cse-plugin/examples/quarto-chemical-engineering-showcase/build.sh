#!/usr/bin/env bash
set -euo pipefail

showcase_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(cd "$showcase_root/../.." && pwd)"

cd "$showcase_root"
mkdir -p builds/figures figures/generated

for figure in artificial-absorber-comparison research-journal-lineage; do
  dvilualatex -interaction=nonstopmode -halt-on-error \
    -output-directory=builds/figures "figures/${figure}-standalone.tex" >/dev/null
  dvisvgm --exact --font-format=woff2 \
    --output="figures/generated/${figure}.svg" \
    "builds/figures/${figure}-standalone.dvi" >/dev/null
done

quarto render article.qmd --no-execute
quarto render deck.qmd --no-execute
quarto render interactive-deck.qmd --no-execute
quarto render research-journal.qmd --to pdf --no-execute
quarto render research-journal.qmd --to revealjs --no-execute

python3 "$repository_root/scripts/latex_visual_qa.py" builds/article.pdf \
  --profile article --output-dir builds/visual-qa/article --contact-sheet
python3 "$repository_root/scripts/latex_visual_qa.py" builds/deck.pdf \
  --profile beamer --output-dir builds/visual-qa/deck --contact-sheet
python3 "$repository_root/scripts/latex_visual_qa.py" builds/research-journal.pdf \
  --profile article --output-dir builds/visual-qa/research-journal --contact-sheet

mkdir -p "$repository_root/output/pdf"
cp builds/article.pdf "$repository_root/output/pdf/chemical-engineering-quarto-article.pdf"
cp builds/deck.pdf "$repository_root/output/pdf/chemical-engineering-quarto-beamer.pdf"
cp builds/research-journal.pdf \
  "$repository_root/output/pdf/chemical-engineering-research-journal.pdf"

printf 'Created %s\n' "$repository_root/output/pdf/chemical-engineering-quarto-article.pdf"
printf 'Created %s\n' "$repository_root/output/pdf/chemical-engineering-quarto-beamer.pdf"
printf 'Created %s\n' "$showcase_root/builds/interactive-deck.html"
printf 'Created %s\n' "$repository_root/output/pdf/chemical-engineering-research-journal.pdf"
printf 'Created %s\n' "$showcase_root/builds/research-journal.html"
printf 'Review visual QA packets under %s\n' "$showcase_root/builds/visual-qa"
