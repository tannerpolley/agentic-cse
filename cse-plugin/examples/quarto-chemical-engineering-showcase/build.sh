#!/usr/bin/env bash
set -euo pipefail

showcase_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(cd "$showcase_root/../.." && pwd)"
render="$repository_root/assets/project/quarto/render.sh"

cd "$showcase_root"
mkdir -p builds/figures figures/generated

for figure in artificial-absorber-comparison analysis-notebook-lineage; do
  dvilualatex -interaction=nonstopmode -halt-on-error \
    -output-directory=builds/figures "figures/${figure}-standalone.tex" >/dev/null
  dvisvgm --exact --font-format=woff2 \
    --output="figures/generated/${figure}.svg" \
    "builds/figures/${figure}-standalone.dvi" >/dev/null
done

"$render" article.qmd
"$render" deck.qmd
"$render" interactive-deck.qmd
"$render" analyses/artificial-absorber/notebook.qmd --to pdf
"$render" analyses/artificial-absorber/notebook.qmd --to revealjs

python3 "$repository_root/scripts/latex_visual_qa.py" builds/article.pdf \
  --profile article --output-dir builds/visual-qa/article --contact-sheet
python3 "$repository_root/scripts/latex_visual_qa.py" builds/deck.pdf \
  --profile beamer --output-dir builds/visual-qa/deck --contact-sheet
python3 "$repository_root/scripts/latex_visual_qa.py" builds/analyses/artificial-absorber/notebook.pdf \
  --profile article --output-dir builds/visual-qa/analysis-notebook --contact-sheet

mkdir -p "$repository_root/output/pdf"
cp builds/article.pdf "$repository_root/output/pdf/chemical-engineering-quarto-article.pdf"
cp builds/deck.pdf "$repository_root/output/pdf/chemical-engineering-quarto-beamer.pdf"
cp builds/analyses/artificial-absorber/notebook.pdf \
  "$repository_root/output/pdf/chemical-engineering-analysis-notebook.pdf"

printf 'Created %s\n' "$repository_root/output/pdf/chemical-engineering-quarto-article.pdf"
printf 'Created %s\n' "$repository_root/output/pdf/chemical-engineering-quarto-beamer.pdf"
printf 'Created %s\n' "$showcase_root/builds/interactive-deck.html"
printf 'Created %s\n' "$repository_root/output/pdf/chemical-engineering-analysis-notebook.pdf"
printf 'Created %s\n' "$showcase_root/builds/analyses/artificial-absorber/notebook.html"
printf 'Review visual QA packets under %s\n' "$showcase_root/builds/visual-qa"
