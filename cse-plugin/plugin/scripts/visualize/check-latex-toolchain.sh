#!/usr/bin/env bash
set -euo pipefail

tinytex_root="$HOME/.TinyTeX"
setup_command="quarto install tinytex --update-path"

fail() {
  echo "CSE LaTeX toolchain check failed: $1" >&2
  echo "Setup: $setup_command" >&2
  exit 1
}

for command in quarto kpsewhich lualatex latexmk biber dvilualatex dvisvgm; do
  command -v "$command" >/dev/null 2>&1 || fail "missing command: $command"
done

active_root="$(kpsewhich -var-value=TEXMFROOT)"
[[ "$active_root" == "$tinytex_root" ]] ||
  fail "active TeX distribution is $active_root; expected $tinytex_root"

for command in kpsewhich lualatex latexmk biber dvilualatex dvisvgm; do
  resolved="$(readlink -f "$(command -v "$command")")"
  [[ "$resolved" == "$tinytex_root/"* ]] ||
    fail "$command resolves outside TinyTeX: $resolved"
done

for file in beamer.cls tikz.sty pgfplots.sty siunitx.sty booktabs.sty mhchem.sty; do
  kpsewhich "$file" >/dev/null || fail "missing TeX file: $file"
done

printf 'CSE LaTeX toolchain ready\n'
printf 'distribution: TinyTeX (%s)\n' "$active_root"
printf 'engine: %s\n' "$(lualatex --version | sed -n '1p')"
printf 'manager: Quarto %s\n' "$(quarto --version)"

if kpsewhich sfrm1000.pfb >/dev/null; then
  printf 'cm-super: present\n'
else
  printf 'cm-super: missing; pdfLaTeX T1 Computer Modern may fall back to bitmap fonts without Type 1 coverage (install cm-super or use lmodern).\n' >&2
fi
