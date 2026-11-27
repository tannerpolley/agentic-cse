# Figure doctrine

Use figures to expose a scientific comparison, not to decorate a result. Start
with the question, intended use, quantity and units, data authority,
uncertainty, and role of each series. Include a comparison limit only when a
named source, standard, regulation, repository decision, or investigator
supplies it.

## Figure purpose and hierarchy

The primary figure directly answers the scientific question. For an ordinary
model-versus-observation comparison, place the physical independent quantity
on the horizontal axis and the measured response on the vertical axis. Show
observations as points and a retained continuous model relationship as a line.

Parity, residual, influence, sensitivity, and convergence figures are
diagnostics. Keep them secondary unless the scientific question concerns that
diagnostic; a deviation or parity figure is primary evidence when the claim is
accuracy over a data set. **Plot the quantity that exposes the error** (Mathias
2017, guidelines of the JCED editors): for phase-equilibrium data, chart
distribution coefficients, relative volatilities, or percent deviations so the
key result is seen at a glance; charts of state conditions make agreement look
good and hide errors at low concentrations. Before rendering, state each figure’s question and unique comparison
in the existing figure record/caption or invoking-stage report, and compare it
with the other proposed figures. Every figure must show a comparison no other
figure shows. Remove or merge duplicate views and customary diagnostics that do
not constrain the claim; no new inventory file is needed. Review scientific
purpose, numerical fidelity, and layout as separate decisions.

When curves coincide, establish whether this is a supported finding, inadequate
resolution/encoding, or an unexplained numerical result. Preserve retained
values and diagnostic evidence. Route unexplained results to `cse:diagnose` and
missing justified model evaluations to `cse:analyze`. Deleting a view never
resolves its unexplained result.

## Series semantics

- A model, fit, interpolation, or other predicted relationship is a line only
  when retained evaluations establish its continuity across the displayed
  domain. Predictions available only at observation coordinates remain
  discrete points unless Analyze retains a justified sweep or interpolation.
- Real observations, experiments, literature values, or reference samples are points, normally `o` or `x` markers. Do not connect unordered observations.
- Connect observations only for an ordered trajectory, such as time, distance, a parameter sweep, or another sequence where the segment has scientific meaning.
- Show uncertainty with intervals, error bars, or bands when it changes the interpretation. State what the uncertainty represents.

## Chart selection

Put quantities with different meanings in separate panels.

Avoid bar charts for continuous scientific comparisons. Prefer a line plus `o`/`x` observations, or points with intervals. Bars are acceptable for inherently categorical counts, compositions, or histogram bins when their baseline and category widths are meaningful; record that reason. Do not use 3-D perspective when a 2-D projection communicates the quantity faithfully.

## Visual defaults

Use a high-contrast, color-vision-safe palette. The shared default uses
`#0072B2`, `#D55E00`, `#009E73`, and `#CC79A7`, matching the first four colors
in the PGFPlots starter. These meet 3:1 against white; the starter’s gold
`#E69F00` and sky `#56B4E9` do not. These are series colors, not automatic text
colors: ordinary text should meet 4.5:1 contrast and large text or essential
non-text marks should meet 3:1 against the actual background. Combine color
with marker, dash, or line-width differences; never rely on color alone or
red/green alone. Keep text, markers, and lines legible in print and grayscale.
Light uncertainty fills need a distinguishable boundary or another readable
encoding when the boundary conveys essential information.

Label every axis with the quantity and unit in the venue's form, such as
$T/\mathrm{K}$ or $T$ (K), and keep one form throughout; a symbol used on an
axis is defined in the caption. Continuous fields use
perceptually uniform, ordered colour maps readable in grayscale (Crameri et al.
2020; [sources](../workflow/writing-sources.md#sources)). Use linear axes by default, and use log or symlog only when multiplicative behavior, orders of magnitude, or signed dynamic range makes the linear view misleading. Keep legends, grids, annotations, and significant digits purposeful.

## Matplotlib style and sizing

An existing project style wins. Otherwise copy
`assets/visualize/project/matplotlib/cse.mplstyle` from the plugin once to the
established shared figure-style owner, defaulting to
`docs/scientific/figures/cse.mplstyle` when none exists. Resolve its path from
the rendering script or project root, never the current working directory or a
user-specific plugin-cache path. Preserve and customize the project copy; do
not overwrite it on later Setup or install it globally. Record the adopted
source commit alongside existing figure provenance, without a new metadata
file. Project style changes remain project-level decisions.

Load the project style as shown below and apply placement settings inside
that scope. The default cycle distinguishes groups, not scientific
roles. For a simple model/data/reference comparison, retain the TeX semantics:
blue continuous model with `marker="None"`, orange open-circle observations
with `linestyle="None"`, green `x` reference points with `linestyle="None"`,
and sky uncertainty fill whose meaning is stated.

For several temperatures or datasets, derive one stable group-to-style mapping
from `plt.rcParams["axes.prop_cycle"]` and reuse it across panels and
model/observation pairs. Suppress curve markers and observation lines
explicitly. With `scatter`, pass the mapping’s marker and color explicitly;
the line property cycle does not rotate scatter markers. If dashes encode
candidate versus reference model, use panels or another explicit encoding for
temperature rather than assigning two meanings to the same dash pattern.
Four entries are a deliberate default, not a four-group limit on science. For
more than four overlapping groups, split into meaningful panels or explicitly
extend the project mapping and recheck it; never silently wrap identities in
one legend.

Start manuscript figures at actual placement width: for example, 3.4 × 2.55
inches for one column or 6.8 × 3.8 inches for a full-width comparison. Keep the
same point sizes when increasing width; increase height or divide panels
instead of shrinking text.

For a 16:9 deck, use actual slide and figure-slot dimensions; every plot need
not be 16:9. On a conventional 13.33 × 7.5 inch slide, a 12 × 5 inch plot slot
starts with 22 pt font/labels, 24 pt title, 20 pt ticks/legend, 2.5 pt lines,
and 8 pt markers. On a physically smaller Beamer canvas, scale slot dimensions
and all point sizes by slide-width/13.33, then check the composed slide. A
12 × 6.75 inch full-slide figure is appropriate only if its slot permits it.
The actual theme or journal can require different settings. See
[slide-decks](slide-decks.md) for sizing slide text and checking the composed deck.

```python
from pathlib import Path
import matplotlib.pyplot as plt

# Example script lives in <project>/scripts/.
project_root = Path(__file__).resolve().parents[1]
style_path = project_root / "docs/scientific/figures/cse.mplstyle"
with plt.style.context(style_path):
    fig, ax = plt.subplots()  # manuscript single column
    # Render retained values here, with explicit scientific roles.

# Conventional slide's 12 × 5 inch slot; adapt to the actual placement.
deck = {
    "figure.figsize": (12, 5), "font.size": 22, "axes.labelsize": 22,
    "axes.titlesize": 24, "xtick.labelsize": 20, "ytick.labelsize": 20,
    "legend.fontsize": 20, "lines.linewidth": 2.5, "lines.markersize": 8,
}
with plt.style.context(style_path):
    plt.rcParams.update(deck)
    fig, ax = plt.subplots()
```

For Matplotlib PDF figures, default to `pdf.fonttype: 42` for TrueType embedding.

## Reproducible outputs

Generate data and render figures in separate stages. The render stage reads an exact plotted-data snapshot and does not rerun an expensive model. Keep the vector/raster figure, exact plotted values, and provenance together in the project’s established results layout. Re-rendering must be deterministic and must not change the underlying scientific result.

Inspect the exported output at its intended physical placement size and in
grayscale, including the composed manuscript page or slide when available.
Check shared figures at their narrowest placement. Verify group identities,
marker shapes, dashes, legend entries, units, uncertainty, and the main
comparisons remain readable, with no clipping or overlap. Convert the rendered
image to grayscale; Matplotlib’s grayscale style changes the encodings being
tested and cannot substitute for this check. Repair layout or encoding and
rerender as needed; unresolved scientific meaning returns to `cse:diagnose`.
Report size, output, and check result in the existing handoff. An automated draw
or PNG existence check is not visual acceptance.

## Review questions

Can a reader identify the question, units, source roles, fit, observations, uncertainty, scale, and limitation without guessing? Does the figure support the stated claim, or does it imply interpolation, precision, or agreement that the data do not establish?

When a named intended-use limit exists, compare the displayed result with it
and report the relation. Otherwise report the actual comparison, uncertainty,
and diagnostics without inventing a pass/fail classification. Plotting exposes
the evidence but does not judge the analysis. An unexplained pattern,
unsupported continuous-looking curve, or conflict with the retained values
returns to Analyze or Diagnose before document work continues.
