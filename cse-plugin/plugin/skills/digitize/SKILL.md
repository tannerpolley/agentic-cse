---
name: digitize
description: "Recover calibrated values from a figure image (XY, bar, or ternary plot) into a CSV with provenance and a QA overlay. Use when asked to \"digitize this plot\", \"extract data from this figure\", or \"get the points off this graph\". PDF text and equations go to zotero."
metadata:
  cse-kind: "tool"
  cse-family: "sources"
  cse-tags: "source-pipeline, data-extraction"
  cse-routing:
    direct: [source-operations]
    conditional: []
---

# Figure digitization tool

Read first: [source-operations](../../references/sources/source-operations.md).

Inherit core scientific, numerical, and
language decisions; do not invoke a visualization plugin for QA.

Prefer source tables, supplements, repositories, or vector paths. If pixels
are necessary, preserve source path, page or panel, crop, resolution, scale,
units, ROI, series mapping, and assumptions. Calibrate two known points per
axis, use the narrow bundled helper for the plot type
([digitize_xy_plot.py](scripts/digitize_xy_plot.py),
[digitize_bar_chart.py](scripts/digitize_bar_chart.py), or
[digitize_ternary_plot.py](scripts/digitize_ternary_plot.py); see
[plot_types.md](references/plot_types.md)), and never overwrite the source. Write
coordinates, calibration metadata, and a QA overlay; inspect it before use.

Compare two independent lanes when possible and classify `pass`, `review`, or
`fail`. Preserve incomplete extraction and limitations rather than guessing or
reporting unsupported precision. Return the CSV and QA evidence to the
invoking stage; core CSE owns interpretation and Review advises on claim support.
