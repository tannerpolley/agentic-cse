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

## Rendering a selected document

From the document's project directory, run
`bash "$CSE_PLUGIN/assets/visualize/project/quarto/render.sh" <document.qmd>`
with `CSE_PLUGIN` set to the installed plugin root. The wrapper selects HTML
by default, passes `--no-execute`, and uses private caches for Quarto, Deno,
and TeX. Keep render hooks out of configuration and profiles. For a configured
PDF view, pass `--to pdf`. The wrapper disables automatic TeX package
installation. Check the existing TinyTeX installation with
`scripts/visualize/check-latex-toolchain.sh`.

## Quarto documentation

- [Websites and navigation](https://quarto.org/docs/websites/website-navigation.html)
- [Render command](https://quarto.org/docs/cli/render.html)
- [Execution options](https://quarto.org/docs/computations/execution-options.html)
