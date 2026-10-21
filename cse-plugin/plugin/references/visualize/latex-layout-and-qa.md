# LaTeX layout and visual QA

Use this reference after a LaTeX, TikZ, PGFPlots, Quarto PDF, or Beamer source
compiles but before calling the output complete. Compilation proves that TeX
accepted the source; it does not prove that the page communicates clearly.

## Geometry rules

### Reserve label zones

- Put labels in named zones above, below, or beside the drawing. Do not place a
  prose-length note across a pipe, stream, axis, or equipment symbol.
- Anchor labels to named nodes or explicit zone coordinates. Use `anchor=west`
  or `anchor=east` when the text must grow away from the drawing.
- Keep connector labels short. Move explanatory prose to the caption.
- Add explicit bounding-box clearance when a caption or neighboring figure can
  approach the lowest node:

```latex
\path ([yshift=-4mm]current bounding box.south) node[inner sep=0] {};
```

### Route connectors as a separate layer

- Choose start and end anchors before drawing a connector. Route around node
  interiors and label zones.
- Draw background regions first or on a background layer. Draw connectors
  before foreground nodes when paths might otherwise cross node text.
- Treat a crossing as intentional only when the crossing has a named meaning.
  Mark that point or bridge the line; otherwise reroute it.
- Prefer named nodes and relative placement over coordinates that happen to
  work at one document width.

### Prefer one semantic demonstration per panel

- Give independent concepts separate subfigures, panels, or table cells with
  their own `tikzpicture` coordinate systems. Shared coordinates imply a
  relationship and make accidental crossings look intentional.
- Within one focused panel, give independent path, arrow, and control-point
  examples separate rows.
- Keep a visible gutter between neighboring cells and between a cell and any
  fitted background region. A shared border is not enough clearance after
  Beamer scaling.
- Name each fitted background node. Place its panel caption relative to the
  south anchor with at least 3 mm of clearance instead of using a raw caption
  coordinate.
- Build the fitted region from a `local bounding box` around the complete
  panel content. This includes path extrema, control points, arrow tips,
  decorations, and stroke width that a hand-maintained list of nodes may omit.

Use this construction for a framed panel with an internal caption:

```latex
\begin{tikzpicture}
  \begin{scope}[local bounding box=panel-content]
    % Named nodes and paths for one semantic demonstration.
  \end{scope}
  \begin{scope}[on background layer]
    \node[cse panel frame,fit=(panel-content)] (panel-frame) {};
  \end{scope}
  \node[cse panel caption,below=4mm of panel-frame.south]
    {Panel caption};
\end{tikzpicture}
```

The local bounding box owns the visible content, the frame owns padding, and
the caption owns its clearance from the frame. Do not replace these relations
with coordinates tuned to one rendering.

### Design for the smallest output profile

A shared figure must work at the narrower of its article and Beamer placements.
Size geometry and text at that width first. `adjustbox` or `\resizebox` may
enforce an outer limit, but scaling is not a repair for crowded source geometry.
Keep labels readable after the final scaling operation. Measure minimum
clearance in the final PDF because whole-picture scaling also scales source
distances.

### Keep overlays bounded

`tikzmark` overlays need unique names, `remember picture,overlay`, and enough
LaTeX passes to stabilize positions. Route the annotation toward page interior,
not toward the nearest page edge. Inspect the assembled page because a
standalone preview cannot reproduce the paragraph anchor.

## Release sequence

Run these gates in order. A later gate does not excuse an earlier failure.

1. **Source:** inspect node anchors, label zones, connector order, explicit
   dimensions, data paths, and the smallest intended profile width.
2. **Build:** render the real Quarto targets and inspect generated `.tex` when
   Pandoc, package order, or class behavior is uncertain.
3. **Log:** reject TeX errors, unresolved references, font substitutions, and
   unexplained overfull boxes.
4. **Automated visual QA:** run `scripts/visualize/latex_visual_qa.py` on each final PDF.
   It checks text-to-text and text-to-vector geometry, renders color and
   grayscale pages, and writes `report.json`.
5. **Manual visual QA:** inspect every rendered page at full size. Use the
   contact sheet for document flow only. Check text against paths and symbols,
   hierarchy, contrast, clipping, and scientific meaning.
6. **Disposition:** classify scientific logic as `exact`, `schematic`,
   `needs-source`, or `failed`; then record `keep`, `simplify`, `split`, or
   `reject`. Rebuild and repeat the affected gates after a correction.

Useful commands:

```bash
command -v pdftotext pdftoppm mutool
./render.sh article.qmd
./render.sh deck.qmd
rg -n 'Overfull|undefined|Warning' article.log deck.log
pdfinfo builds/article.pdf
python3 scripts/visualize/latex_visual_qa.py builds/article.pdf \
  --profile article --output-dir builds/visual-qa/article --contact-sheet
python3 scripts/visualize/latex_visual_qa.py builds/deck.pdf \
  --profile beamer --output-dir builds/visual-qa/deck --contact-sheet
```

Use `--profile standalone` for an isolated figure. `--warnings-as-errors` is
useful only after the repository has calibrated the conservative warnings
against its own accepted documents.

The runner depends on Poppler's `pdftotext` and `pdftoppm` plus MuPDF's
`mutool`; use `pdfinfo` separately for document metadata. `montage` is
required only with `--contact-sheet`. Seeded clean and overlapping sources under
`tests/fixtures/latex-visual-qa/` keep the overlap gate exercised.

`chktex`, `lacheck`, and `texfot` find source and log problems, but none can
certify visual clearance. Vector checks deliberately inspect stroked paths and
ignore filled regions to avoid treating every shaded node as a collision. The
runner cannot infer whether a nearby rule, path crossing, schematic
simplification, or scientific claim is intentional. These tools supplement
full-size human inspection.

## Diagnostic switches

Use these temporarily and remove them from the release source:

| Diagnostic | Reveals |
| --- | --- |
| `\overfullrule=5pt` | Boxes extending beyond the text block |
| `\usepackage{showframe}` | Page and text-area boundaries |
| `\draw[help lines] ...` | TikZ coordinates and spacing |
| `local bounding box=<name>` plus a temporary fitted frame | The complete path and node extent owned by one panel |
| `\draw[red] (current bounding box.south west) rectangle (current bounding box.north east);` | The figure's actual bounding box |
| `draft` graphics mode | Missing or unexpectedly sized external graphics |

## Frequent failure classes

| Symptom | Common cause | Preferred correction |
| --- | --- | --- |
| Text crosses an arrow or pipe | Annotation was placed relative to nearby equipment rather than a reserved zone | Move the label to a named zone and anchor text away from the path |
| Caption touches the drawing | Lowest node or overlay is missing from the useful bounding box | Add source-level clearance and rebuild both profiles |
| Unrelated examples cross | Several concepts reuse one coordinate system | Use one semantic demonstration per panel; use separate bounded rows only within a focused panel |
| Figure works in the article but not Beamer | Geometry was designed only at article width | Design at the smaller profile and keep shared source |
| Heading is separated from its figure | A float crossed a semantic section boundary | Add `\FloatBarrier` after the figure group; do not force every float with `[H]` |
| Text becomes unreadable | Whole-picture scaling repaired an oversized layout | Reduce geometry or label content at the source |
| Overlay moves between runs | Auxiliary positions have not stabilized or names collide | Use unique marks and compile enough passes |
| Plot is blank | Data are outside limits or the plot handler uses the wrong direction | Verify retained values, handler orientation, and axis limits |
| Warning repeats as a missing package | Quarto auto-install is masking a TeX error | Disable `latex-auto-install` while diagnosing and read the first TeX error |
| Library file loads but syntax fails | Package interface and installed TikZ release disagree | Reproduce with a minimal source and version-gate the feature |

## Completion criterion

The source and every intended output profile compile, all references resolve,
the automated report records completed text, vector, and raster checks with no
error, every page has been inspected at full size in color and grayscale, and
the recorded disposition is not `unreviewed`.
No unintended overlap, clipping, ambiguous connector, blank plot, unreadable
label, or unsupported scientific implication remains.
