# Quarto execution boundary

Use this reference for Quarto articles, analysis reports, presentations, and
dashboards.

## Responsibility

Quarto assembles source, passes the document model through Pandoc, and invokes
the selected renderer. It can format retained values into tables and plots.
Scientific review owns result acceptance and validation.

Write inline mathematics as `$...$` and display mathematics as `$$...$$` to
preserve math mode in HTML and PDF.

```text
model or analysis command -> retained final results -> Quarto document
  -> Pandoc -> LaTeX or HTML -> scientific review
```

Run the model as a separate, explicitly requested action. A render must never
launch the model, write retained results, or fetch uncontrolled remote data.

## Analysis website

Use one Quarto website under `analyses/` in a confirmed analysis repository.
The synthesis article is `index.qmd`. Included reports share the docked
sidebar, theme, and project-owned `site.css`. The sidebar lists pages in order,
optionally grouped one level deep. Quarto's `toc: true` gives each page its own
section links. The manager records the sidebar and derives `project.render`
from it in `_cse-manuscript.json`.

With the synthesis article in place, run these commands from the repository root.
Set `CSE_PLUGIN` to the root of the installed plugin.

```bash
python3 "$CSE_PLUGIN/assets/visualize/project/quarto/manuscript.py" init analyses/
python3 analyses/manuscript.py include analyses/ analyses/case/notebook.qmd --title "Case" --group "Reports"
bash analyses/render.sh
python3 analyses/manuscript.py refresh analyses/ analyses/case/notebook.qmd
```

Repeat `--group` when updating a page in the same group. Omit it to move the
page to the top level. Refresh runs only the `present` rule when the report's
folder contains a Snakefile, then renders the report and the home page.

The site defaults to `execute.enabled: false`. Use `render.sh` for a render.
It selects HTML by default, passes `--no-execute`, and uses private caches for
Quarto, Deno, and TeX. Keep render hooks out of site configuration and profiles.
For a configured PDF view, pass `--to pdf`. For a website page with PDF options,
list `html: {}` first in its format mapping. The standalone example has its own
`promoted-pdf` profile and LuaLaTeX header. The wrapper disables automatic TeX
package installation. Check the existing TinyTeX installation with
`scripts/visualize/check-latex-toolchain.sh`.

## Upgrading a managed root

Rerun the plugin's `init analyses/` to replace the two tooling files. It
preserves the synthesis, retained results, stylesheet, and site configuration.
It removes the retired service, presentation profile, and source record, and
converts the old sidebar to page links. In the existing `_quarto.yml`, set
`format.html.toc: true` to show the page contents. Review the changes in Git
and render the site.

## Quarto documentation

- [Websites and navigation](https://quarto.org/docs/websites/website-navigation.html)
- [Render command](https://quarto.org/docs/cli/render.html)
- [Execution options](https://quarto.org/docs/computations/execution-options.html)
