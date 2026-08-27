# Quarto chemical-engineering LaTeX showcase

Quarto is the source manager. It renders one detailed article and one Moloch
Beamer deck through LuaLaTeX, plus an interactive RevealJS HTML deck. A shared
analysis-notebook source also renders to a LuaLaTeX PDF and a RevealJS HTML
companion from the same artificial retained results and the same TikZ and
PGFPlots figure sources. Document code is disabled for the default and release
build.

## Build

```bash
./build.sh
```

After `./build.sh` has refreshed the shared SVG views, individual documents can
be rerendered with:

```bash
quarto render article.qmd --no-execute
quarto render deck.qmd --no-execute
quarto render interactive-deck.qmd --no-execute
quarto render analyses/artificial-absorber/notebook.qmd --to pdf --no-execute
quarto render analyses/artificial-absorber/notebook.qmd --to revealjs --no-execute
```

The project writes intermediate output under `builds/`. The build wrapper runs
the shared visual QA runner for article and Beamer profiles, writes color and
grayscale review packets under `builds/visual-qa/`, and copies the three final
PDFs to the repository `output/pdf/` directory. Inspect every rendered page at
full size before recording a release disposition.

## Source map

- `article.qmd`: detailed package guide and reusable examples.
- `deck.qmd`: presentation-focused tour of the same system.
- `interactive-deck.qmd`: browser-native RevealJS navigation, fragments,
  auto-animation, tabsets, and speaker notes without Python execution.
- `analyses/artificial-absorber/notebook.qmd`: one reviewed analysis set rendered as both a
  LuaLaTeX analysis-notebook PDF and a scroll-first RevealJS companion.
- `tex/`: distinct article and Beamer headers; do not inject the article
  header into Beamer.
- `theme/`: restrained Moloch customization.
- `figures/`: shared document-native TikZ and PGFPlots sources.
- `figures/generated/`: SVG views compiled from the shared figure sources for
  RevealJS; the PDF includes the `.tex` sources directly.
- `data/`: small illustrative retained tables read by PGFPlots and table tools.
- `software-references.bib`: software/manual references not owned by Zotero.
- `appendices/supported-tools.qmd`: complete curated bundle inventory and
  quick examples.

Agent-facing layout QA and local-manual lookup guidance lives in
`../../references/latex-layout-and-qa.md` and
`../../references/latex-manuals.md`.

The article demonstrates the author-controlled KOMA-Script profile. The deck
demonstrates the 16:9 Moloch profile with high-contrast semantic text colors;
series colors still require marker or line-style encoding in grayscale.

All engineering numbers are illustrative and are not validation data.

Read `../../references/quarto-execution.md` before adding executable Python.
