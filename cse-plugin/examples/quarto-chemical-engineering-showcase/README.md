# Quarto chemical-engineering LaTeX showcase

Quarto is the source manager. It renders one detailed article and one Moloch
Beamer deck through LuaLaTeX. Document code is disabled for both builds.

## Build

```bash
./build.sh
```

Individual documents can be rerendered through the CSE wrapper with:
```bash
../../plugin/assets/visualize/project/quarto/render.sh article.qmd --to pdf
../../plugin/assets/visualize/project/quarto/render.sh deck.qmd --to beamer
```

The project writes intermediate output under `builds/`. The build wrapper runs
the shared visual QA runner for article and Beamer profiles, writes color and
grayscale review packets under `builds/visual-qa/`, and copies the two final
PDFs to the repository `output/pdf/` directory. Inspect every rendered page at
full size before recording a release disposition.

## Source map

- `article.qmd`: detailed package guide and reusable examples.
- `deck.qmd`: presentation-focused tour of the same system.
- `tex/`: distinct article and Beamer headers; do not inject the article
  header into Beamer.
- `theme/`: restrained Moloch customization.
- `figures/`: shared document-native TikZ and PGFPlots sources.
- `data/`: small illustrative retained tables read by PGFPlots and table tools.
- `software-references.bib`: software/manual references not owned by Zotero.
- `appendices/supported-tools.qmd`: complete curated bundle inventory and
  quick examples.

Agent-facing layout QA and local-manual lookup guidance lives in
`../../plugin/references/visualize/latex-layout-and-qa.md` and
`../../plugin/references/visualize/latex-manuals.md`.

The article demonstrates the author-controlled KOMA-Script profile. The deck
demonstrates the 16:9 Moloch profile with high-contrast semantic text colors;
series colors still require marker or line-style encoding in grayscale.

All engineering numbers are illustrative and are not validation data.

Read `../../plugin/references/visualize/quarto-execution.md` before adding executable Python.
