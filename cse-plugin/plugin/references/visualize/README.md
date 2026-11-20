# CSE rendering

Figure and document rendering tools for Agentic Computational Science and
Engineering. Rendering consumes retained values or supported claims, never
runs the scientific model, and returns material changes to core Review. It does
not invoke source operations.

## Choose a tool

Use `$cse:latex` for the complete document workflow. It confirms the
document profile and selected outputs, then routes to the smallest useful
specialist:

- `plot` selects a figure backend from the quantity, retained values, and intended use.
- `tikz` creates document-native diagrams whose paths and relationships carry meaning.
- `pgfplots` renders small or moderate quantitative tables as LaTeX-native plots.
- `quarto` renders one `.qmd` source to the ordinary HTML view or the selected
  promoted PDF profile.
- `beamer` renders a fixed-layout scientific presentation PDF.

Use [slide-decks](slide-decks.md) for shared Beamer, Quarto, and PowerPoint deck defaults and checks.

Use `assets/visualize/project/quarto/manuscript.py` to initialize an analysis
website once its synthesis article is in `analyses/index.qmd`. Include report
pages explicitly and build the site with `render.sh`. The package also ships
a standalone HTML/PDF example under `assets/visualize/project/quarto/example/`. The
example reads its retained CSV and compiles one shared PGFPlots source for
HTML and LuaLaTeX without executing a model.

From the installed `cse` package root, check the toolchain before
rendering:

```bash
bash scripts/visualize/check-latex-toolchain.sh
bash scripts/visualize/cache-latex-manuals.sh
```

The first command verifies TinyTeX, LuaLaTeX, Quarto, Biber, TikZ, and PGFPlots.
The second refreshes the searchable official manual cache. For the example, run
`bash assets/visualize/project/quarto/example/render.sh`; it builds the shared figure,
then calls the asset `quarto/render.sh` with `--no-execute` for HTML and the
opt-in promoted LuaLaTeX PDF profile. The rendered outputs are written under
`assets/visualize/project/quarto/example/builds/`. Keep detailed package, article-profile,
figure, layout, and execution doctrine in the references directory.
