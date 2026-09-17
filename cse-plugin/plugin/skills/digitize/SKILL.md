---
name: digitize
description: "CSE — Recover calibrated values from a source figure into a reviewable CSV with provenance and QA."
metadata:
  cse-kind: "tool"
  cse-family: "sources"
  cse-tags: "source-pipeline, data-extraction"
  cse-routing:
    direct: [source-operations]
    conditional: []
---

# Figure digitization tool

Inherit core scientific, numerical, and
language decisions; do not invoke a visualization plugin for QA.

Prefer source tables, supplements, repositories, or vector paths. If pixels
are necessary, preserve source path, page or panel, crop, resolution, scale,
units, ROI, series mapping, and assumptions. Calibrate two known points per
axis, use the narrow bundled helper, and never overwrite the source. Write
coordinates, calibration metadata, and a QA overlay; inspect it before use.

Compare two independent lanes when possible and classify `pass`, `review`, or
`fail`. Preserve incomplete extraction and limitations rather than guessing or
reporting unsupported precision. Return the CSV and QA evidence to the
invoking stage; core CSE owns interpretation and Review advises on claim support.
