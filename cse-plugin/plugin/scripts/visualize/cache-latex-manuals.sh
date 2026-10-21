#!/usr/bin/env bash
set -euo pipefail

cache_root="${XDG_DATA_HOME:-$HOME/.local/share}/cse/latex-manuals"
tinytex_bin="$HOME/.TinyTeX/bin/x86_64-linux"
packages=(
  adjustbox algorithmicx beamer biblatex booktabs chemfig chemnum chempid
  chemplants circuitikz cleveref csvsimple derivative fontspec forest
  glossaries-extra hyperref mathtools mhchem microtype minted moloch nicematrix
  pgf pgfplots siunitx standalone tabularray tcolorbox threeparttable tikz-ext
  unicode-math
)

command -v pdftotext >/dev/null
test -x "$tinytex_bin/kpsewhich"
mkdir -p "$cache_root/text" "$cache_root/cli"
find "$cache_root/text" -type f -delete

index="$cache_root/INDEX.md"
printf '# Local LaTeX manuals\n\nGenerated from the active TinyTeX installation.\n\n| Package | Searchable manual | Description |\n| --- | --- | --- |\n' >"$index"

for package in "${packages[@]}"; do
  while IFS=$'\t' read -r _ _ manual _ description; do
    [[ "$manual" == *.pdf ]] || continue
    [[ "$manual" == "$HOME/.TinyTeX/"* ]] || continue
    manual_base="$(basename "${manual,,}")"
    [[ "$manual_base" =~ (-code|code\.|example|introduction|style|test|sample|tutorial|poster|legacy|result) ]] && continue
    name="${package}--$(basename "${manual%.pdf}").txt"
    pdftotext -layout "$manual" "$cache_root/text/$name"
    printf '| `%s` | `text/%s` | %s |\n' "$package" "$name" "${description:-Official TeX Live manual}" >>"$index"
    break
  done < <(PATH="$tinytex_bin:$PATH" texdoc -l -M "$package" 2>/dev/null || true)
done

quarto --help >"$cache_root/cli/quarto-help.txt"
quarto pandoc --help >"$cache_root/cli/pandoc-help.txt"

printf '\nSearch example: `rg -n -i "table-format" "%s/text/siunitx"*.txt`\n' "$cache_root" >>"$index"
printf 'Created %s\n' "$index"
