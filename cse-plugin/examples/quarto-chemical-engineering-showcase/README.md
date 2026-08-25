# Quarto chemical-engineering LaTeX showcase

Quarto is the source manager. It renders one detailed article and one Moloch
Beamer deck through LuaLaTeX. Shared TikZ, PGFPlots, chemistry, units, and table
sources live beside the `.qmd` files so agents can reuse them without copying
generated TeX.

## Build

```bash
./build.sh
```

Equivalent direct commands:

```bash
quarto render article.qmd
quarto render deck.qmd
```

The project writes intermediate output under `builds/`. The build wrapper also
copies the two final PDFs to the repository `output/pdf/` directory.

## Source map

- `article.qmd`: detailed package guide and reusable examples.
- `deck.qmd`: presentation-focused tour of the same system.
- `tex/`: distinct article and Beamer headers; do not inject the article
  header into Beamer.
- `theme/`: restrained Moloch customization.
- `figures/`: shared document-native TikZ and PGFPlots sources.
- `data/`: small illustrative retained tables read by PGFPlots and table tools.
- `software-references.bib`: software/manual references not owned by Zotero.

All engineering numbers are illustrative and are not validation data.

