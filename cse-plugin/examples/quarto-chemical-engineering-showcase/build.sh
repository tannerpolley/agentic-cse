#!/usr/bin/env bash
set -euo pipefail

showcase_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(cd "$showcase_root/../.." && pwd)"
render="$repository_root/plugin/assets/visualize/project/quarto/render.sh"
visual_qa="$repository_root/plugin/scripts/visualize/latex_visual_qa.py"

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
"$render" analyses/artificial-absorber/notebook.qmd
"$render" analyses/artificial-absorber/notebook.qmd --profile promoted-pdf

python3 "$visual_qa" builds/article.pdf \
  --profile article --output-dir builds/visual-qa/article --contact-sheet
python3 "$visual_qa" builds/deck.pdf \
  --profile beamer --output-dir builds/visual-qa/deck --contact-sheet
python3 "$visual_qa" builds/analyses/artificial-absorber/notebook.pdf \
  --profile article --output-dir builds/visual-qa/analysis-notebook --contact-sheet

mkdir -p "$repository_root/output/pdf"
cp builds/article.pdf "$repository_root/output/pdf/chemical-engineering-quarto-article.pdf"
cp builds/deck.pdf "$repository_root/output/pdf/chemical-engineering-quarto-beamer.pdf"
cp builds/analyses/artificial-absorber/notebook.pdf \
  "$repository_root/output/pdf/chemical-engineering-analysis-notebook.pdf"

printf 'Created %s\n' "$repository_root/output/pdf/chemical-engineering-quarto-article.pdf"
printf 'Created %s\n' "$repository_root/output/pdf/chemical-engineering-quarto-beamer.pdf"
printf 'Created %s\n' "$repository_root/output/pdf/chemical-engineering-analysis-notebook.pdf"
printf 'Created %s\n' "$showcase_root/builds/analyses/artificial-absorber/notebook.html"
printf 'Review visual QA packets under %s\n' "$showcase_root/builds/visual-qa"
