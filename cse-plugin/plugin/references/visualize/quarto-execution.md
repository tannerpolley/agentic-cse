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
managed preview bridge checks affected workflows, then publishes a last-checked
source copy under the user cache (`$XDG_CACHE_HOME/cse-preview`, or
`~/.cache/cse-preview`). Quarto runs no workflows in this copy. Refused workflows
contribute no resources; their registered pages and pages including or embedding
those resources show a typed failure. The home page lists every refusal, including
workflows without a registered page. Checks remain strict outside this preview.

The bridge scans sources every ten seconds, excluding `data/`, `results/`,
and cache trees. It follows exact include targets, including HTML includes,
without walking retained trees. Its watcher compares timestamps and sizes, so an
edit preserving both needs another watched edit or a new preview session. Copying
always compares bytes, even when timestamps and sizes match. After changing
arbitrary retained data or results, run `refresh`; these changes are not automatic
triggers. Writes from a presentation check are absorbed only within that workflow.
The check-then-copy gap has the same known race as check-then-render.

Every copied source-like text file is conservatively scanned for paths escaping
the copy, absolute paths into the original tree, and `file://` references. These
need resource reconciliation. Includes, embeds, and inline images reaching refused
workflows produce typed failures. Other reference forms, such as front-matter
bibliographies and reference-style images, can instead show Quarto's missing-file
render message; refused values are absent from the copy.
The following
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

It replaces `manuscript.py`, `render.sh`, `preview.service`,
`_quarto-presentation.yml`, and the `.cse-quarto-source.json` source record
with the current plugin versions, then prints each replaced file. It keeps
everything the project owns: `_quarto.yml`,
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
   `.cse-quarto-source.json`, `manuscript.py`, `render.sh`, and
   `preview.service`, then rerun `init` with that root's `index.qmd` as
   `--article-source`.
4. Include each report again with `include --title <title> [--group <heading>]`.
5. Render with `render.sh`, then rerun `service` for the preview.

Sources and retained results stay in place.

## Main-checkout preview service

During an approved Setup action, run
`python3 analyses/manuscript.py service analyses/` once from the main checkout.
It installs and restarts a systemd user unit
`cse-preview-<repository>-<path hash>.service` that keeps `manuscript.py preview`
running on `127.0.0.1`, with `Nice=10`, `CPUWeight=10`, and restart on failure
within a bounded start limit. Outside approved Setup, agents leave this service
running and use `manuscript.py status analyses/` to report its unit state, URL,
and port.

The service uses the checkout's `.venv/bin/python`, never the interpreter that
happened to run `service`. An explicit `--python <path>` must also belong to
that project. Prepare that environment with packages providing `jupyter_core`,
`nbformat`, `nbclient`, `ipykernel`, `jupyter_client`, `jupyter_cache`, and `yaml`
(package names: `jupyter-core`, `nbformat`, `nbclient`, `ipykernel`,
`jupyter-client`, `jupyter-cache`, and `PyYAML`). The command does not install
packages or fall back to a cache environment: it fails with the required module
list and the import error when imports fail, or an actionable message when the
project interpreter is missing. Projects with a `Snakefile` also need the
`snakemake` package in that environment: `service` checks its import and the
`snakemake` executable on the unit's `PATH`, which preparation invokes.
The interpreter's directory comes first on
that `PATH`; the command refuses unit paths containing whitespace, quotes,
backslash, `%`, or `$`.

To migrate an existing unit during approved Setup, add these packages to the
project environment, rerun `init` to update the managed root's tooling, then
rerun `service` from the main checkout.

The port is chosen once from the repository path in the 8800–9799 range,
skipping ports that are bound or claimed by another preview unit, unless
`--port` is given. Reruns keep the port and refuse a unit the command did not
write for that repository. `--dry-run` prints the unit without writing or
enabling it. Without `systemctl --user`, the command reports that missing
capability and writes no unit. It reports `serving <url>` only after the URL
answers, otherwise the unit's journal command. User services stop at logout
unless lingering is enabled (`loginctl enable-linger`).

For an unmerged worktree, run `manuscript.py preview <root>` as a task-owned
foreground process. It uses the same port allocator, hashing the worktree path
and skipping bound and claimed ports; `--port` may override it.
`manuscript.py status <root>` reports the worktree preview state, URL, and port.
At cleanup, use `manuscript.py stop <root>` to signal that preview, which cleans
up its Quarto process group. `stop` refuses the main checkout, and a stale PID
record cannot signal a process that reused the PID. Worktree lifecycle records
live in the ignored `.quarto/` directory; process identity uses Linux `/proc`.

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
