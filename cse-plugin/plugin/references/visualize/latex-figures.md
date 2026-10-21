# LaTeX-native figures

Use this reference when a scientific or engineering figure may be rendered
inside LaTeX. TikZ is the readable drawing layer over PGF. PGFPlots is the
table- and axis-oriented plotting layer over TikZ and PGF. Raw PGF is an
implementation layer; use it only when TikZ cannot express a required
extension, not as a separate public workflow stage.

See `latex-packages.md` for engine, preamble, package, and document-profile
decisions. This reference owns figure backend, source, and rendering rules.
When a figure needs routing, automatic layout, in-document overlays, domain
symbols, multi-panel axes, uncertainty regions, or composition coordinates,
consult the relevant section of `latex-extensions.md` before selecting
libraries.

## Choose the backend

| Backend | Use it for | Keep out of it |
| --- | --- | --- |
| `tikz` | Schematics, geometry, process diagrams, meshes, annotations, and compact conceptual models | Large numeric arrays or hidden scientific calculations |
| `pgfplots` | Small or moderate table-driven curves, convergence plots, model-versus-data figures, and axis-based comparisons | Expensive fits, millions of points, dense fields, or arbitrary shell commands |
| `plot` with Python/Matplotlib | Large, computational, statistical, heatmap, 3-D, or specialized figures | Recreating a simple document-native diagram that TikZ handles directly |

Use `cse:tikz` for a LaTeX-native diagram and `cse:pgfplots` for a
LaTeX-native quantitative plot. Use `cse:plot` to select the backend when the
user asks for a figure without specifying one.

## Source and data requirements

- Keep diagram source under `docs/scientific/latex/figures/tikz/` and PGFPlots
  source under `docs/scientific/latex/figures/pgfplots/`.
- Keep retained publication outputs under `docs/scientific/latex/figures/`,
  normally in `generated/`. Keep disposable compilation files under
  `docs/scientific/latex/builds/`.
- Keep authoritative analysis results under the project analysis directory.
  A PGFPlots source reads an explicit retained table or a reviewed publication
  snapshot; it never reruns the scientific model.
- Use `\addplot table` with named columns for computed or measured values.
  Use `\addplot expression` only for a declared analytic relationship whose
  equation is already part of the scientific record.
- Do not put fitted coefficients, digitized values, or large data arrays in
  figure source as unexplained literals.
- A figure record should identify its question, backend, source table, columns,
  units, series roles, output path, and claim or analysis-notebook section it
  supports.

## Shared styles and semantics

Load `docs/scientific/latex/figures/styles.tex` after TikZ and PGFPlots. Copy the
starter styles from `../../assets/visualize/project/latex/figure-styles.tex` during
repository setup and revise them only with a project-level design decision.
For multi-panel TikZ sources, use the starter `cse panel frame` and
`cse panel caption` styles with a named `local bounding box`; do not maintain
panel frames from a partial list of coordinates.

Use semantic styles such as `cse model`, `cse data`, `cse reference`, and
`cse uncertainty`; do not select colors independently in every figure. A
continuous model or fit is a line. Observations and reference values are
points, normally `o` or `x`. Use line style, marker, and width differences in
addition to color, and do not rely on red versus green alone.

## Preamble and compilation

Load `tikz`, only the TikZ libraries required by the source, and `pgfplots` in
the manuscript preamble. Set an explicit `compat` value matching the installed
PGFPlots version. Build through the repository's LaTeX wrapper after the
approved bibliography snapshot is current, and write the PDF to the project's
`builds/` directory.

Figure source bodies should be inserted inside a LaTeX `figure` environment
with `\centering`, a caption, and a label when they are manuscript figures.
Standalone previews may use the same body with a small wrapper document so the
manuscript preamble and figure styles are exercised by the preview.

TikZ externalization is an optional performance mode for expensive figures. Use
stable names and a controlled build script; generated cache files belong in
`builds/`, not beside the source. Do not enable arbitrary `shell-escape`,
`\addplot shell`, gnuplot calls, or `\write18` in ordinary figure source.

## Figure checks

Before returning a figure to `write`, `summarize`, or `review`:

1. Compile the figure and the assembled manuscript with the project command.
2. Check that every input, table, image, and output path exists.
3. Check quantities, units, scales, limits, legend roles, uncertainty, and
   point-versus-line semantics.
4. Inspect the rendered figure, including typography, clipping, overlap,
   contrast, and grayscale readability.
5. Confirm that the rendered values match the retained table and that the
   figure does not imply precision, interpolation, or agreement beyond the
   evidence.

Record two separate review outcomes. Scientific logic is `exact` when the
geometry or values are authoritative, `schematic` when declared simplification
is intentional, `needs-source` when support is missing, and `failed` when the
visual contradicts the evidence. Layout disposition is `keep`, `simplify`,
`split`, or `reject`. A compiled figure with either outcome unreviewed is not
ready to return.

Official references: [PGF/TikZ](https://ctan.org/pkg/pgf), the
[TikZ and PGF manual](https://tikz.dev/), and the
[PGFPlots manual](https://tikz.dev/pgfplots/tutorial1).

For label zones, connector routing, bounding-box clearance, profile-width
checks, text-to-vector clearance, and page-by-page raster inspection, read
`latex-layout-and-qa.md`.
For exact installed package syntax, read `latex-manuals.md` and search the
generated local manual cache.
