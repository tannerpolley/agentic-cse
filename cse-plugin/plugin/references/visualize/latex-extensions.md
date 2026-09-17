# TikZ and PGF extension policy

Use this reference when a LaTeX-native figure needs routing, automatic layout,
in-document overlays, domain symbols, multiple axes, uncertainty regions,
composition coordinates, or another capability beyond basic TikZ or PGFPlots.
It selects maintained libraries; it is not a gallery of every CTAN package.

## Selection ladder

1. Start with core TikZ or PGFPlots and the project semantic styles.
2. Load the smallest built-in library that supplies the missing operation.
3. Use `tikz-ext` when its focused routing, positioning, layer, or node-family
   library removes substantial custom coordinate code.
4. Use a domain package only when its symbol vocabulary matches the figure's
   engineering meaning and project convention.
5. Keep data generation, fitting, statistics, triangulation, and contour
   computation in analysis code. A TeX extension renders retained values; it
   does not become a second scientific model.

The selection is complete when every loaded library is exercised by the
figure, every numerical value has provenance, the source compiles through the
project route, and the rendered output passes the checks in `latex-figures.md`.

## Built-in TikZ libraries

Load these with `\usetikzlibrary{...}` only when their trigger applies.

| Library | Trigger | Use |
| --- | --- | --- |
| `arrows.meta` | Directed streams, fluxes, forces, or signal paths | Select modern arrow tips and size them consistently. This is the default arrow library. |
| `positioning` | Node-and-edge diagrams | Place named nodes relative to one another instead of maintaining absolute coordinates. |
| `calc` | Derived geometry | Express offsets, interpolation, projections, and vector combinations from named coordinates. |
| `fit` | Grouped equipment or stages | Draw a semantic boundary around an explicit node set. |
| `backgrounds` | Regions behind the main paths | Put boundaries, operating regions, or group fills on a controlled background layer. |
| `matrix` | Regular node grids | Build stage arrays, state grids, and compact block layouts. Use `nicematrix` instead for mathematical matrices in prose. |
| `chains` | Repeated sequential nodes | Build a simple ordered series when ordinary positioning becomes repetitive. |
| `intersections` | Geometric intersection is part of the diagram | Compute named path intersections; keep scientific root finding in analysis code. |
| `decorations.markings` | Repeated arrows or markers along a path | Mark flow direction or position along a stream without splitting the path manually. |
| `decorations.pathmorphing` | A conventional physical symbol needs it | Draw restrained coils, waves, or irregular boundaries; avoid decorative use. |
| `patterns.meta` | Grayscale-safe material or region encoding | Add a pattern when color alone cannot distinguish a region. |
| `shapes.geometric` | A conventional node shape carries meaning | Add a small set of equipment, decision, or geometry shapes. Prefer project-defined semantic styles. |
| `graphs` | Graph syntax improves readability | Declare nodes and edges compactly while retaining manual layout. |
| `graphdrawing` plus `\usegdlibrary{layered,trees}` | A larger directed graph needs automatic layout | Use LuaLaTeX to lay out dependency, solver, or process networks. Record the algorithm and visually check the result. |
| `external` | Measured TikZ compile cost is material | Cache stable figure builds through the controlled repository wrapper and keep cache outputs under `builds/`. |

A strong default for an engineering schematic is:

```latex
\usetikzlibrary{
  arrows.meta,
  positioning,
  calc,
  fit,
  backgrounds
}
```

## Selected `tikz-ext` libraries

The linked
[`tikz-ext`](https://ctan.org/pkg/tikz-ext) distribution is a maintained CTAN
collection of PGF/TikZ libraries. Load a selected library directly; there is no
general `\usepackage{tikz-ext}` requirement.

| Library | Decision | Use and boundary |
| --- | --- | --- |
| `ext.positioning-plus` | Selected | Place a node relative to multiple nodes or bounding boxes when core `positioning` would require fragile coordinate arithmetic. |
| `ext.paths.ortho` | Selected | Route orthogonal process streams, signal lines, and block-diagram edges with readable path operations. Keep route choices explicit. |
| `ext.node-families` | Conditional | Synchronize dimensions across related node families. It uses the auxiliary file, so compile enough passes to stabilize sizes. |
| `ext.layers` | Conditional | Put a path or node on a named layer without repeated `pgfonlayer` blocks. Use core `backgrounds` for a simple background-only need. |
| `ext.arrows-plus` | Conditional | Place or bend arrow tips along complex paths when `decorations.markings` is insufficient. |
| `ext.paths.arcto` and `ext.topaths.arcthrough` | Conditional | Construct an arc from geometric points when the arc itself carries meaning. |
| `ext.scalepicture` | Exception | Fit a complete picture to a target dimension only when source-level dimensions cannot do so. It uses the auxiliary file; preserve readable text size. |

The calendar, image-pattern, miscellaneous PGFKeys/loop, specialized shape,
timer, and mirror libraries remain unselected until a figure has that exact
requirement. Prefer the core library when it expresses the same relation.

Typical routing additions are:

```latex
\usetikzlibrary{
  ext.positioning-plus,
  ext.paths.ortho
}
```

## Selected domain extensions

| Package or library | Decision | Use and boundary |
| --- | --- | --- |
| `tikzmark` | Selected annotation layer | Anchor an overlay to equations, table cells, or prose. Use `remember picture,overlay`, unique mark names, and enough LaTeX passes to resolve positions. |
| `circuitikz` | Selected circuit layer | Draw electrical and electronic networks for instrumentation, sensors, and control hardware. Declare its voltage convention and use `siunitx` labels. |
| `chemplants` | Selected simple PFD layer | Draw unit operations and streams when its UNICHIM-influenced symbols match the project convention. Define any project deviations. Preflight its `hobby` dependency. |
| `chempid` | Selected P&ID candidate | Draw piping and instrumentation symbols for a real P&ID. Check each symbol against the project's governing convention, preflight its `import` dependency, and review the newer package on the exact document class. |
| `forest` | Conditional hierarchy layer | Draw compact rooted trees for model, solver, decision, or decomposition hierarchies. Use built-in graph drawing for a general network rather than forcing it into a tree. |
| `chemfig` | Selected molecular layer | Draw two-dimensional molecular structures; it is not a process-diagram package. |
| `standalone` | Selected reuse layer | Compile a reusable figure with the real preamble and embed the same source in reports and Beamer. |

`tikz-3dplot` is not a bundle default. Use native TikZ for a simple coordinate
frame, PGFPlots for modest retained three-dimensional tables, and
Python/Matplotlib for data-rich surfaces. Three-dimensional perspective must
clarify a scientific relation that a two-dimensional view cannot show.

## Selected PGFPlots libraries

Load these with `\usepgfplotslibrary{...}`. They ship with PGFPlots and do not
require separate CTAN packages.

| Library | Decision | Use and scientific boundary |
| --- | --- | --- |
| `groupplots` | Selected | Align multi-panel comparisons and share axis placement. Keep scales comparable or label the differences explicitly. |
| `fillbetween` | Selected | Render uncertainty bands, feasible regions, or the area between retained curves. State what the filled region represents. |
| `ternary` | Selected chemical-engineering extension | Render ternary composition and tie-line data. State mole or mass basis and verify normalization before plotting. |
| `statistics` | Conditional | Render box plots or histograms. Prefer prepared summary values when the statistical definition belongs to analysis code. |
| `colorbrewer` | Conditional palette source | Use a suitable sequential, diverging, or qualitative palette with a grayscale and color-vision check. Project semantic colors still own series roles. |
| `colormaps` | Conditional | Supply additional continuous colormaps when an existing project palette is insufficient. Validate ordering and perceptual meaning. |
| `polar` | Conditional | Render angular or cyclic retained data in a polar coordinate system when that coordinate system is physically meaningful. |
| `patchplots` | Exception | Render a small reviewed mesh or patch table. Use Matplotlib for large meshes, fields, or expensive geometry. |

For common uncertainty and multi-panel work:

```latex
\usepgfplotslibrary{
  groupplots,
  fillbetween
}
```

For ternary phase or composition data:

```latex
\usepgfplotslibrary{ternary}
```

PGFPlots should read explicit tables with `\addplot table`. Generate contours,
fits, confidence intervals, statistics, and mesh connectivity outside TeX when
they support a scientific claim. Avoid gnuplot shell calls and hidden random
sampling in publication figures.

## Options not selected for the bundle

- `tikzscale`: set explicit PGFPlots `width` and `height`, design TikZ geometry
  at the intended size, or use `standalone`; preserve text size at the source.
- `smartdiagram`, `pgf-pie`, and novelty shape collections: use semantic TikZ
  styles and a chart type tied to the scientific question.
- `tikzplotlib`: retain data and render with CSE's chosen Matplotlib or
  PGFPlots route rather than depending on generated TikZ internals.
- `gnuplottex`, `\addplot shell`, and direct `\write18`: keep computation in
  the analysis environment and the LaTeX build reproducible.
- Development snapshots copied from GitHub: use the released CTAN/TeX Live
  package unless a pinned upstream fix is required and documented.

## Preflight and verification

Resolve exactly the selected libraries and packages:

```bash
kpsewhich tikzlibraryext.positioning-plus.code.tex
kpsewhich tikzlibraryext.paths.ortho.code.tex
kpsewhich tikzlibrarytikzmark.code.tex
kpsewhich circuitikz.sty
kpsewhich chemplants.sty
kpsewhich tikzlibraryhobby.code.tex
kpsewhich chempid.sty
kpsewhich import.sty
kpsewhich forest.sty
```

Compile a minimal source that loads the exact selected set before integrating
it into a venue class. Then compile and inspect the assembled document. Check
orthogonal routes, arrow direction, node dimensions, overlays, component
symbols, composition basis, axis alignment, uncertainty meaning, clipping,
font consistency, grayscale readability, auxiliary-pass stability, and build
time. Keep only extensions exercised by the final source.

## Official references

- [`tikz-ext`](https://ctan.org/pkg/tikz-ext) and its [source repository](https://github.com/Qrrbrbirlbel/tikz-extensions)
- [TikZ libraries](https://tikz.dev/library-toc) and [graph drawing](https://tikz.dev/gd-usage-tikz)
- [`tikzmark`](https://ctan.org/pkg/tikzmark), [`circuitikz`](https://ctan.org/pkg/circuitikz), and [`forest`](https://ctan.org/pkg/forest)
- [`chemplants`](https://ctan.org/pkg/chemplants) and [`chempid`](https://ctan.org/pkg/chempid)
- [PGFPlots `groupplots`](https://tikz.dev/pgfplots/libs-groupplots), [`fillbetween`](https://tikz.dev/pgfplots/libs-fillbetween), [`statistics`](https://tikz.dev/pgfplots/libs-statistics), and [`ternary`](https://tikz.dev/pgfplots/libs-ternary)
