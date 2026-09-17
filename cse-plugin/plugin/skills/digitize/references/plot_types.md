# Plot Type Coverage

Use this reference after identifying the figure type. Keep extraction calibrated, local, and QA-overlay driven.

## Directly Scripted

| Plot type | Preferred script | Calibration | Output |
|---|---|---|---|
| Scatter | `digitize_xy_plot.py` | x/y axes | point rows |
| Line plot | `digitize_xy_plot.py` | x/y axes | traced curve rows |
| Step/Kaplan-Meier | `digitize_xy_plot.py` | x/y axes | step curve rows |
| Error-bar plot | `digitize_xy_plot.py` plus manual/error pass | x/y axes | means, optional low/high |
| Vertical/horizontal bar | `digitize_bar_chart.py` | value axis + baseline | category values |
| Grouped bar | `digitize_bar_chart.py` | value axis + category spans | series/category values |
| Stacked bar | `digitize_bar_chart.py` per segment color | value axis + stack interpretation | segment values |
| Histogram | `digitize_bar_chart.py` | value axis + bin spans | bin heights |
| Ternary scatter/curve | `digitize_ternary_plot.py` | three vertices | A/B/C compositions |

## Adaptable With Extra Calibration

| Plot type | Calibration needed | Strategy |
|---|---|---|
| Heatmap/matrix | x/y axes plus colorbar | sample cell/region colors, map through colorbar, export x/y/value |
| Contour plot | x/y axes plus contour labels or colorbar | threshold contour colors or labels, export polylines or raster samples |
| Box-and-whisker | category axis plus y axis | detect horizontal median/quartile/whisker lines, export q1/median/q3/min/max |
| Violin plot | category axis plus y axis | extract silhouette width vs y, export density samples |
| Area/stacked area | x/y axes plus baseline/stack order | trace upper/lower boundaries, subtract baselines |
| Polar/radar | center, radius scale, angle zero/direction | convert pixels to angle/radius, export theta/r |
| Pie/donut | center plus sector labels | estimate sector angles; only use for approximate percentages |
| Bland-Altman/parity/log-log | x/y axes, often log scale | treat as XY scatter/line with explicit scale checks |
| Phase diagrams | axes or ternary vertices | treat as XY/ternary plus boundary tracing |

## When To Prefer Manual WebPlotDigitizer

Use a manual or externally assisted workflow when:

- series overlap heavily
- tick labels are unreadable
- the plot is perspective-distorted or photographed
- colors are too similar to isolate
- the plot has many insets or broken axes
- extracted values will drive high-stakes scientific conclusions

## Common Output Schemas

XY:

```text
series,x,y,pixel_x,pixel_y
```

Bars:

```text
series,category,value,baseline_value,pixel_center_x,pixel_center_y,pixel_endpoint_x,pixel_endpoint_y,pixel_left,pixel_top,pixel_right,pixel_bottom
```

Ternary:

```text
series,A,B,C,pixel_x,pixel_y
```

Heatmap:

```text
series,x,y,value,pixel_x,pixel_y,color
```

Box plot:

```text
series,category,min,q1,median,q3,max
```
