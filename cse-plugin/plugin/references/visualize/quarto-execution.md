# Quarto execution boundary

Use this reference whenever Quarto manages a scientific article, research
analysis notebook, presentation, or dashboard.

## Responsibility

Quarto assembles source, passes the document model through Pandoc, and invokes
the selected output renderer. It may format retained values into tables and
plots. It does not own model execution, result acceptance, or scientific
validation.

Write inline mathematics as `$...$` and display mathematics as `$$...$$` in
Quarto Markdown so Pandoc retains math mode in both HTML and PDF.

Keep the workflow boundary explicit:

```text
model or analysis command -> retained final results -> Quarto document
  -> Pandoc -> LaTeX or HTML -> scientific review
```

The model or analysis command is a separate, explicitly requested action. A
document render must not import a model entrypoint, launch a simulation or
benchmark, write retained results, or fetch uncontrolled remote data.

## Safe default and opt-in execution

Initialize a confirmed analysis repository's root Quarto analysis site at
`analyses/`. Its JSON-compatible YAML configuration defaults to:

```json
{"execute": {"enabled": false}}
```

The root is a Quarto website (`project.type: website`). The article is the
home page `_site/index.html`; a registered `case/result.qmd` is the ordinary
page `_site/case/result.html`. Every page shares one docked sidebar, theme,
and full page layout, so numbered equations and cross-references
work on every page. The home page is the sidebar section "Home", and each included
notebook is a collapsed section titled by `include --title`. A section title only
expands it; its children are an Overview link and one link per heading at the
page's highest level outside `:::` blocks, with the anchors Pandoc assigns.
`manuscript.py sync <root>` recomputes those links from the current headings while
keeping titles and groups; `include`, `refresh`, `preview`, the service, and
`render.sh` run it first, and `validate` reports stale links. Included files count as part of the page;
keep other shortcodes out of top-level headings. Re-running `include` for a grouped
notebook must repeat its `--group`, or it moves to the top level. Notebook paths may
use only letters, digits, `.`, `_`, `-`, and `/`.
There is no page table of contents or margin column, so keep side notes inline.
`include --group <name>` nests a notebook under a collapsed group heading
(`A/B` nests groups); the
last notebook leaving a group removes it. There is no top bar: the site title,
search, and reader-mode toggle sit in the sidebar. Pages load math with the page
(`self-contained-math`) and share the installed `site.css` (publication-style
tables with aligned digits, full-width figures, small captions, 16 px text); the
project owns `site.css` after `init`. The root
sets `notebook-links: false`, so an article that embeds a labeled cell from a
retained notebook with `{{< embed >}}` shows the cell without a link to a
separate notebook page.
The HTML root sets `format-links: false` so optional, unbuilt PDF views do not
produce download links. A page with PDF settings must also declare `html: {}`
first in its `format` mapping so website navigation selects its HTML output.

Initialize with `manuscript.py init`, include substantive report `.qmd` files
with `manuscript.py include`, and use `manuscript.py validate` before a render.
The root configuration and presentation profile must be JSON-compatible YAML;
ordinary YAML requires a reviewed conversion before adoption. The command
checks field ownership with stdlib JSON and native Quarto semantics in a
disposable sibling containing only configuration and registered sources.
Inspection leaves the original project and its cache unchanged. Unsupported
profiles, includes, hooks, nested projects, or output paths require
reconciliation before any write.
The command owns only `_cse-manuscript.json`; `project.render` and
`website.sidebar` are the sole ordered memberships. Quarto merges both from that
metadata file, and native inspection confirms the merged sidebar. The site
title and other presentation settings remain in `_quarto.yml`, which must not
define a sidebar. An unregistered `.qmd` is not rendered. Use `assets/visualize/project/quarto/render.sh` for a release
render; it selects `--to html` unless the caller supplies `--to` or `-t`, so
page-level PDF settings do not broaden an ordinary HTML render. It passes
`--no-execute` at the command boundary and gives Quarto, Deno, and LuaLaTeX
private writable runtime directories. TinyTeX is the TeX distribution,
LuaLaTeX (LuaHBTeX) is its compiler, Quarto is the document manager, and
`luaotfload` owns the generated font cache. The wrapper reads packages, fonts,
and configuration from TinyTeX without writing to that installation. Do not
use bare `quarto render` as the supported CSE command.

The ordinary HTML Quarto analysis site is the living synthesis and notebook
route. Select an optional native PDF view with `render.sh --to pdf` after
configuring its reviewed format settings. The separate standalone example's
`_quarto-promoted-pdf.yml` profile selects LuaLaTeX and includes
`promoted-pdf-header.tex`; invoke it with `render.sh --profile promoted-pdf
--to pdf`; the explicit format overrides the default HTML target.
Keep the header limited to packages exercised by the source. The root Quarto
analysis site does not copy this standalone profile or header.

The guarded render command disables Quarto's automatic LaTeX package
installation. Check required packages with `scripts/visualize/check-latex-toolchain.sh`;
installing or changing TinyTeX remains a separate, explicitly authorized setup
operation.

When a document needs Python to format a retained table or draw a plot, use
`manuscript.py refresh <root> <included.qmd>`. It runs the presentation-only
`present` entry, then native Quarto with `_quarto-presentation.yml`, invalidates
the presentation cache, and updates the included notebook page and the home
page. Refresh and preview select HTML explicitly, keeping a page's optional
PDF settings out of the website update.
Quarto preview does not detect arbitrary external-data changes; the
managed preview bridge asks the running preview to re-render only the affected
registered source (touching a file does not trigger it) after the presentation hook has been allowed to validate retained inputs. The following
bare Quarto command shows the
upstream syntax for the separately authorized presentation-only execution
route; it is not a normal or release CSE render:

```bash
QUARTO_PYTHON=/path/to/presentation-environment/bin/python \
  quarto render report.qmd --profile presentation
```

Before activating the profile:

- use a presentation-only environment that does not install the scientific
  model or its execution entrypoints;
- read only files from the project's retained final-results area;
- write only to the Quarto output directory;
- prohibit subprocesses, shell cells, network access, and writes to retained
  results; and
- record the exact input paths and content hashes used for a released figure or
  table.

A presentation cell may read a retained table and plot it:

```python
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

source = Path("../../analyses/case/results/final/profile.csv")
profile = pd.read_csv(source)
profile.plot(x="position", y="response")
plt.show()
```

It must not import a model package, call a solver, invoke a benchmark through a
shell or subprocess, or replace `profile.csv`. Keep `error: false` so a failed
presentation cell stops the render. Disable the Jupyter daemon so separate
renders do not share hidden kernel state.

`freeze` and `cache` are performance and reproducibility controls. They are not
execution-security boundaries: cached output can become stale, and an explicit
execution command can rerun cells. Environment and filesystem isolation provide
the stronger boundary when executable presentation cells are enabled.

## Upgrading a managed root

To give a managed root (one with `_cse-manuscript.json`) the current plugin
tooling, rerun the plugin's `init` on it:

```bash
python3 assets/visualize/project/quarto/manuscript.py init analyses/ \
  --article-source analyses/index.qmd --source-commit <SHA> --runtime-tree-sha256 <SHA256>
```

It replaces `manuscript.py`, `render.sh`, `_quarto-presentation.yml`, and the
`.cse-quarto-source.json` source record with the current plugin versions and
prints each replaced file. It keeps everything the project owns: `_quarto.yml`,
`_cse-manuscript.json` membership, `site.css`, `index.qmd`, `.gitignore`
additions, and all sources and retained results. The replacement is validated
before any write, so a failed validation leaves the root unchanged. `init` still
refuses to overwrite files in a root without `_cse-manuscript.json`.

A root created before the website layout (`project.type: manuscript`) is
refused rather than rewritten. Migrate it once:

1. Remove page-level `execute:` settings from the pages; the root configuration
   and presentation profile own execution.
2. Remove nested Quarto projects (`_quarto.yml` or `_metadata.yml` below the
   root) or move them out of the root.
3. Remove `_quarto.yml`, `_quarto-presentation.yml`, `_cse-manuscript.json`,
   `.cse-quarto-source.json`, `manuscript.py`, and `render.sh`, then rerun
   `init` with that root's `index.qmd` as `--article-source`.
4. Include each report again with `include --title <title> [--group <heading>]`.
5. Render with `render.sh`, then rerun `service` for the preview.

Sources and retained results stay in place.

## Main-checkout preview service

`python3 analyses/manuscript.py service analyses/` installs a systemd user unit
`cse-preview-<repository>-<path hash>.service` that keeps `manuscript.py preview`
running on `127.0.0.1` from the main checkout, restarting it on failure within a
bounded start limit. The unit records the interpreter absolutely (`--python`,
default the interpreter running the command) and puts its directory first on
`PATH`; the command refuses an interpreter that cannot import the Jupyter
packages the presentation profile executes with (including `jupyter-cache`,
which its `execute.cache: true` requires), or a presentation workflow whose
`snakemake` is absent from that `PATH`. It also refuses any path containing
whitespace, quotes, backslash, `%`, or `$`. The port is chosen once from the
repository path, skipping ports that are bound or claimed by another preview unit,
unless `--port` is given; reruns keep the port and refuse a unit the command did
not write for that repository. `--dry-run` prints the unit without writing or
enabling it. Without `systemctl --user`, the command reports that missing
capability and writes nothing. It reports `serving <url>` only after the URL
answers, otherwise the unit's journal command. User services stop at logout unless
lingering is enabled (`loginctl enable-linger`).

The service URL is the main-checkout view: agents do not start or stop it. An
unmerged worktree branch is previewed by a task-owned
`manuscript.py preview <root> --port <free port>` that the agent stops at cleanup.

## HTML

Ordinary Quarto HTML is the default Quarto analysis site output. It reads the retained
source, renders the selected Markdown and HTML, and leaves the scientific
model outside the document build. A selected HTML completion needs `index.qmd`,
registered report sources, and their nonempty rendered HTML. Browser-side behavior may
be added for retained values, but it must not become a model execution route.

Official references:

- <https://quarto.org/docs/computations/python.html>
- <https://quarto.org/docs/computations/execution-options.html>
- <https://quarto.org/docs/projects/profiles.html>
- <https://quarto.org/docs/projects/code-execution.html#cache>
- <https://quarto.org/docs/advanced/inspect/index.html>
- <https://quarto.org/docs/interactive/widgets/jupyter.html>
