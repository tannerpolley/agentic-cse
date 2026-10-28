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
diagnostic. Every additional figure must contribute a distinct comparison or
interpretation; omit duplicate views and customary diagnostics that do not
constrain the claim. Review scientific purpose, numerical fidelity, and layout
as separate decisions.

## Series semantics

- A model, fit, interpolation, or other predicted relationship is a line only
  when retained evaluations establish its continuity across the displayed
  domain. Predictions available only at observation coordinates remain
  discrete points unless Analyze retains a justified sweep or interpolation.
- Real observations, experiments, literature values, or reference samples are points, normally `o` or `x` markers. Do not connect unordered observations.
- Connect observations only for an ordered trajectory, such as time, distance, a parameter sweep, or another sequence where the segment has scientific meaning.
- Show uncertainty with intervals, error bars, or bands when it changes the interpretation. State what the uncertainty represents.

## Chart selection

Avoid bar charts for continuous scientific comparisons. Prefer a line plus `o`/`x` observations, or points with intervals. Bars are acceptable for inherently categorical counts, compositions, or histogram bins when their baseline and category widths are meaningful; record that reason. Do not use 3-D perspective when a 2-D projection communicates the quantity faithfully.

## Visual defaults

Use a high-contrast, color-vision-safe palette. A restrained Okabe–Ito-style set is a useful starting point: `#0072B2`, `#D55E00`, `#009E73`, `#CC79A7`, `#E69F00`, and `#56B4E9`. These are series colors, not automatic text colors: ordinary text should meet 4.5:1 contrast and large text or essential non-text marks should meet 3:1 against the actual background. Combine color with marker, dash, or line-width differences; never rely on color alone or red/green alone. Keep text, markers, and lines legible in print and grayscale.

Label every axis with the quantity and unit. Use linear axes by default, and use log or symlog only when multiplicative behavior, orders of magnitude, or signed dynamic range makes the linear view misleading. Keep legends, grids, annotations, and significant digits purposeful.

For Matplotlib PDF figures, default to `pdf.fonttype: 42` for TrueType embedding.

## Reproducible outputs

Generate data and render figures in separate stages. The render stage reads an exact plotted-data snapshot and does not rerun an expensive model. Keep the vector/raster figure, exact plotted values, and provenance together in the project’s established results layout. Re-rendering must be deterministic and must not change the underlying scientific result.

## Review questions

Can a reader identify the question, units, source roles, fit, observations, uncertainty, scale, and limitation without guessing? Does the figure support the stated claim, or does it imply interpolation, precision, or agreement that the data do not establish?

When a named intended-use limit exists, compare the displayed result with it
and report the relation. Otherwise report the actual comparison, uncertainty,
and diagnostics without inventing a pass/fail classification. Plotting exposes
the evidence but does not judge the analysis. An unexplained pattern,
unsupported continuous-looking curve, or conflict with the retained values
returns to Analyze or Diagnose before document work continues.
