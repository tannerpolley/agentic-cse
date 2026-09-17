# LaTeX package policy

Use this reference whenever CSE creates, revises, reviews, or configures a
LaTeX document, Quarto PDF, Beamer deck, TikZ diagram, or PGFPlots figure. It
is the package-selection source of truth. Package installation and package
loading are separate decisions: an installed package is inert, while every
loaded package expands the document requirements and its compatibility surface.

## Decision procedure

1. Inspect the document class, venue template, build command, engine, existing
   preamble, and rendered output. A publisher or university template owns any
   choice it specifies.
2. Classify the output as an author-controlled manuscript, analysis research notebook,
   report or thesis, Beamer deck, venue-controlled submission, or
   Quarto-generated PDF. See `latex-article-profiles.md` for the selected
   article profile.
3. Start from the matching profile below. Add a package only for a feature
   present in the document; select one winner for each overlapping role.
4. Keep scientific quantities, chemical notation, equations, citations,
   tables, figures, and terminology consistent across source and output.
5. Resolve every package and external executable before compilation. Do not
   install or silently substitute a dependency unless the task authorizes the
   environment change.
6. Compile through the repository entry point and inspect the PDF. Completion
   requires resolved references, citations, glossary entries, figure inputs,
   and no unexplained package, font, or engine warning that can change meaning
   or layout.

Read `latex-manuals.md` when an exact package command, option, or versioned interface
requires the installed official manual rather than a policy decision.

## Selected defaults

These are CSE defaults when the user, venue, and existing repository have not
already selected another route.

| Capability | Selected default | Why | Competing choice and exception |
| --- | --- | --- | --- |
| Engine and fonts | LuaLaTeX with `fontspec` and `unicode-math` | Unicode input and OpenType text and mathematics | Use the venue engine. Under pdfLaTeX, omit both and use the template font stack. |
| Author-controlled class | KOMA-Script `scrartcl` or `scrreprt` | Integrated headings and page furniture; manuscript type area without competing layout packages | The analysis-notebook profile uses its one explicit Quarto margin owner. Use the venue class when required. With a classic `article` or `report` class, `geometry` and `fancyhdr` remain conditional choices. |
| Mathematics | `mathtools` and `derivative` | Equation structures plus explicit derivative notation | Add `amsthm` and `thmtools` only for theorem-like exposition. |
| Bold mathematics | `\symbf` from `unicode-math` | Matches the selected Unicode math architecture | Use `bm` in a traditional font workflow, not as a LuaLaTeX default. |
| Quantities | `siunitx` | One notation for values, units, uncertainty, ranges, and numeric table columns | No manual unit typography. Preserve the project's quantity macros if already established. |
| Chemical formulas | `mhchem` | Compact formulas, phases, ions, and reactions | Choose `chemmacros` with its `chemformula` syntax when its wider chemistry model is required; keep one formula syntax. |
| Tables | `booktabs`, `siunitx`, and `threeparttable` | Restrained, portable scientific tables with aligned numbers and scoped notes | Choose `tabularray` for complex author-controlled tables; do not build both complete table systems by default. |
| Acronyms and symbols | `glossaries-extra` | Covers acronyms, symbols, nomenclature, and dissertation-scale lists | Choose `acro` only when the document needs acronyms and no glossary or symbol list. |
| Citations | Venue system; otherwise `biblatex` with Biber and `csquotes` | The venue remains authoritative; author-controlled work gains Unicode and configurable bibliographies | Add `biblatex-chem` only for a required chemistry style. |
| Cross-references | `hyperref`, `bookmark`, then `cleveref` | Linked PDF structure plus semantic reference names | Use class-provided configuration when the class owns hyperlinks. |
| Code | Quarto highlighting in `.qmd`; otherwise `listings` | Quarto already owns generated code blocks; `listings` is self-contained for raw LaTeX | Use `minted` only when its external executable is available and richer highlighting is worth the build dependency. |
| Pseudocode | `algorithmicx` with `algpseudocode` | Separates pseudocode syntax from float placement and is easy to adapt | Use `algorithm2e` only when its integrated ruled algorithm style is an explicit design choice. |
| Data tables | `pgfplotstable` | Reuses retained tables across PGFPlots figures and typeset tables | Use `csvsimple` for row filtering or repeated text generation not owned by a plot. |
| Molecular structures | `chemfig` | Document-native two-dimensional molecular drawings | Use an external reviewed vector figure when the structure is too complex or already authoritative elsewhere. |
| Process diagrams | TikZ; `chemplants` for PFD symbols; `chempid` for P&IDs | Keeps the abstraction level explicit | Use `schemabloc` only when an existing control-diagram source already depends on it. |
| Revision comparison | Git plus `latexdiff` | The source history remains authoritative and the comparison is generated | Use `changes` only for a required manual tracked-changes workflow. |

## Document profiles

### Author-controlled manuscript and analysis research notebook

Use LuaLaTeX and KOMA-Script `scrartcl`, then apply the selected structure and
appearance from `latex-article-profiles.md`. Every article-capable tool in this
reference may be used in either profile. Add it for an exercised capability,
not because of the profile name. Keep shared notation, table, and figure
sources independent of the profile header. KOMA-Script owns the manuscript
type area; the notebook's explicit Quarto margins are its sole geometry owner.

### Venue-controlled submission

Only when the user supplies a publication requirement, start with that class
and its example. Load only notation and content packages the class permits.
Treat bibliography, captions, subfigures, page geometry, line spacing,
headers, and hyperlinks as class-owned. Remove draft packages before
submission.

### Author-controlled report or thesis

Use LuaLaTeX, KOMA-Script, the selected scientific core, `microtype`, the
traditional table stack, and the author-controlled bibliography stack. Let
KOMA-Script's type area and `scrlayer-scrpage` own page geometry and furniture;
do not add `geometry` or `fancyhdr` to that profile. Add `glossaries-extra`,
`longtable`, `pdflscape`, `subfiles`, theorem support, or code support only
when the document contains the corresponding material.

### Beamer deck

Let Beamer own page geometry, navigation, lists, colors, captions, and
hyperlinks. Use a 16:9 Moloch base, one major claim per frame, no automatic
shrink, and roughly one main frame per presentation minute unless the speaking
plan proves otherwise. Share notation commands and selected scientific
packages, not the entire article preamble. Add `appendixnumberbeamer` for
backup-slide numbering and `pdfpc` only for the PDF Presenter Console workflow.
Use `animate` only after testing the exact viewer and presentation computer.

### Quarto PDF or Beamer output

See `quarto-execution.md` when Quarto is selected. Let Quarto own document assembly, generated
presentation tables, citations, cross-references, and code highlighting where
its native feature suffices. Keep document execution disabled by default; an
explicit presentation profile may read retained results but must not
run the scientific model. Put stable LaTeX packages and macros in a reviewed
header file:

```yaml
format:
  pdf:
    pdf-engine: lualatex
    keep-tex: true
    include-in-header:
      - tex/preamble.tex
```

Use a distinct Beamer header rather than injecting an article header into
slides. Inspect the generated `.tex` when package order, class behavior, or a
Pandoc transformation is uncertain.

### Quarto HTML output

Ordinary Quarto HTML is the living notebook route. Reuse scientific notation,
retained data, citations, and semantic colors without loading an article or
Beamer preamble. Use native Quarto layout and HTML for retained figures,
tables, links, and supporting details. Keep any presentation-only code under
the opt-in boundary in `quarto-execution.md`; it may read retained values but
must never run the scientific model.

## Load order for an author-controlled LuaLaTeX document

```latex
% Engine and mathematics
\usepackage{fontspec}
\usepackage{mathtools}
\usepackage{unicode-math}
\usepackage{microtype}

% Scientific notation
\usepackage{siunitx}
\usepackage[version=4]{mhchem}

% Figures and tables
\usepackage{graphicx}
\usepackage{xcolor}
\usepackage{booktabs}
\usepackage{threeparttable}

% Language and URLs
\usepackage{csquotes}
\usepackage{xurl}

% Near the end, in this order
\usepackage[hidelinks]{hyperref}
\usepackage{bookmark}
\usepackage[nameinlink,noabbrev]{cleveref}
```

Add `biblatex` after `csquotes` and before the final cross-reference group when
the document owns its bibliography. Load TikZ libraries only where their
features are used. Set an explicit PGFPlots `compat` value supported by the
resolved installation.

## Package glossary

### Engine, typography, and page design

| Package | Decision | Use and reason |
| --- | --- | --- |
| `fontspec` | LuaLaTeX default | Select OpenType or TrueType text fonts. Omit under pdfLaTeX. |
| `unicode-math` | LuaLaTeX default | Select an OpenType math font and Unicode math commands. Use `\symbf` for bold symbols. |
| `microtype` | Report and manuscript default | Improve protrusion, expansion, and spacing; retain unless the class or engine reports a real incompatibility. |
| `xcolor` | General default | Define semantic colors shared by links, tables, TikZ, and revision markup. Beamer already owns its color system. |
| KOMA-Script | Author-controlled class default | Use `scrartcl` or `scrreprt`; let `typearea` and `scrlayer-scrpage` own page layout and furniture. |
| `geometry` | Classic-class conditional | Set margins only when a venue or a non-KOMA author-controlled class requires it. |
| `setspace` | Conditional | Meet an explicit line-spacing requirement, normally for a thesis or review copy. |
| `fancyhdr` | Classic-class conditional | Create headers and footers only when the class does not provide a page-style system. |

### Mathematics, quantities, and chemistry

| Package | Decision | Use and reason |
| --- | --- | --- |
| `mathtools` | Default | Use as the main extension of AMS mathematics environments and symbols. |
| `bm` | Alternative | Use `\bm` in a traditional math-font workflow; prefer `unicode-math` commands in the LuaLaTeX profile. |
| `derivative` | Default when derivatives appear | Express ordinary, partial, material, and higher derivatives consistently. |
| `amsthm` | Conditional | Define theorem, definition, lemma, assumption, and proof environments. |
| `thmtools` | Conditional companion | Add declarative theorem styles, lists, and restatable results on top of `amsthm`. |
| `nicematrix` | Conditional | Annotate block Jacobians, Hessians, stoichiometric matrices, and bordered arrays. |
| `cancel` | Teaching only | Mark canceled terms in a derivation; keep it out of ordinary manuscript prose. |
| `siunitx` | Default | Typeset quantities, compound units, ranges, uncertainty, scientific notation, and aligned numeric columns. |
| `mhchem` | Default chemistry syntax | Typeset chemical formulas, reactions, phases, charges, and equilibrium arrows with `\ce{}`. |
| `chemmacros` | Alternative chemistry system | Choose when oxidation states, nomenclature, thermodynamic data, and its wider chemistry conventions are required. Keep its `chemformula` syntax primary. |
| `chemnum` | Conditional | Assign stable labels and references to repeatedly discussed compounds without manual renumbering. |

### Figures and diagrams

| Package | Decision | Use and reason |
| --- | --- | --- |
| `graphicx` | Default | Include, crop, scale, and rotate reviewed external graphics. |
| `tikz` | Selected diagram layer | Draw schematics, control volumes, geometries, workflows, and process concepts using semantic styles. |
| `pgfplots` | Selected native plot layer | Render modest retained tables as axes, curves, observations, and uncertainty with document-matched typography. |
| `standalone` | Conditional | Compile a reusable TikZ or PGFPlots source independently while keeping it embeddable. |
| `adjustbox` | Conditional | Constrain, crop, rotate, or frame content that cannot be sized cleanly at its source. Do not use it to hide an unreadable table design. |
| `chemfig` | Conditional | Draw two-dimensional molecular structures and reaction fragments. |
| `chemplants` | Conditional PFD layer | Add chemical-process unit and stream symbols to a simplified process-flow diagram. |
| `chempid` | Conditional P&ID layer | Add piping and instrumentation symbols when a real P&ID is required; validate the selected symbols and rendered result against project conventions. |
| `schemabloc` | Existing-source exception | Maintain an established block-diagram source; new CSE diagrams normally use TikZ positioning and shapes directly. |
| `svg` | External-tool workflow | Import an SVG only when the repository controls the Inkscape conversion step. Prefer a committed PDF for a portable journal build. |

Follow `latex-figures.md` for backend selection, source-table lineage, output
locations, externalization, and visual checks. Follow `latex-extensions.md`
when the figure needs a TikZ or PGFPlots library beyond the base layer.

### Tables and generated values

| Package | Decision | Use and reason |
| --- | --- | --- |
| `booktabs` | Default | Use restrained horizontal rules and whitespace; omit decorative vertical rules. |
| `threeparttable` | Default when notes exist | Keep a caption, table body, and scientific notes at a consistent width. |
| `longtable` | Conditional | Continue parameter or data tables across pages; check the class and column mode. |
| `multirow` | Conditional | Group repeated row categories when the grouping remains unambiguous. |
| `makecell` | Conditional | Create compact multiline headers or cells in the traditional table stack. |
| `tabularray` | Alternative table system | Choose for complex spans, styles, or long tables in an author-controlled document. Use its `booktabs` library rather than duplicating a full traditional stack. |
| `pgfplotstable` | Selected generated-table layer | Read and format the same retained tables used by PGFPlots. Keep computation in analysis code. |
| `csvsimple` | Conditional | Filter CSV rows or generate repeated LaTeX content when no PGFPlots data relationship exists. |
| `pdflscape` | Conditional | Rotate a wide table page and set the PDF page orientation correctly. |

### Captions, floats, links, and identity

| Package | Decision | Use and reason |
| --- | --- | --- |
| `subcaption` | Conditional | Create labeled subfigures or subtables only when the class permits the caption package family. |
| `placeins` | Conditional default for float boundaries | Use `\FloatBarrier` at semantic boundaries instead of forcing every float with `[H]`. |
| `hyperref` | Default unless class-owned | Create links, PDF metadata, and hyperlink targets; load near the end. |
| `bookmark` | Default companion | Improve PDF outline generation and control after `hyperref`. |
| `cleveref` | Default companion | Generate semantic names and ranges for equations, figures, tables, and sections; load after `hyperref`. |
| `xurl` | Default for URL-heavy work | Give long URLs more legal line-break points; load before `hyperref`. |
| `orcidlink` | Conditional | Add linked ORCID marks only when the class or template does not already provide them. |

### Bibliographies, acronyms, and document structure

| Package or tool | Decision | Use and reason |
| --- | --- | --- |
| `csquotes` | Author-controlled bibliography default | Supply language-aware quotations and integrate with `biblatex`. |
| `biblatex` with Biber | Author-controlled default | Manage Unicode citations, sorting, filtering, and multiple bibliographies. Follow the venue instead for submission. |
| `biblatex-chem` | Conditional style | Select a supported chemistry bibliography style for an author-controlled document. |
| `achemso` | Legacy or explicit-template only | Use only when a required existing ACS workflow names it; current ACS submission instructions own new submissions. |
| `glossaries-extra` | Selected full terminology system | Manage acronyms, symbols, units, nomenclature, and multiple glossary lists. Include the required glossary build step. |
| `acro` | Acronym-only alternative | Choose when expansion, short forms, and an acronym list are the whole requirement. |
| `subfiles` | Conditional | Compile chapters independently when that capability measurably improves a large document workflow. |
| `import` | Conditional | Resolve nested `\input` and graphics paths relative to a component directory. Prefer ordinary `\input` for a flat source tree. |
| `xr-hyper` | Conditional | Link cross-references between separately compiled documents such as a manuscript and supporting information. |
| `pdfpages` | Conditional | Insert complete reviewed PDF pages such as approved forms or appendices. |

### Lists, code, algorithms, and callouts

| Package | Decision | Use and reason |
| --- | --- | --- |
| `enumitem` | Article/report conditional | Tune list labels and spacing in author-controlled prose. Let Beamer control slide lists. |
| `listings` | Selected raw-LaTeX code layer | Typeset portable source listings without an external highlighter. Quarto code blocks remain the first choice in `.qmd`. |
| `minted` | External-tool alternative | Use only when `latexminted` is resolved, the source is trusted, and the richer highlighting is required. |
| `algorithmicx` | Selected pseudocode system | Provide the extensible pseudocode engine. |
| `algpseudocode` | Selected style companion | Supply readable pseudocode commands for `algorithmicx`. Add a separate float only when needed. |
| `algorithm2e` | Alternative | Choose its integrated float, keywords, and ruled style as one complete replacement for the selected pseudocode system. |
| `tcolorbox` | Conditional | Create breakable examples, definitions, or code callouts in teaching material, reports, and theses; keep journal styling restrained. |

### Drafting and presentations

| Package or tool | Decision | Use and reason |
| --- | --- | --- |
| `lineno` | Review-only | Add manuscript line numbers when requested by reviewers or the venue. |
| `changes` | Manual-review exception | Record explicit additions and deletions only when the collaboration requires markup inside the source. |
| `todonotes` | Draft-only | Keep visible author tasks during drafting; use final mode or remove them before release. |
| `latexdiff` | Selected revision tool | Generate a review copy from two committed source states without making tracked markup canonical. |
| `appendixnumberbeamer` | Beamer conditional default | Exclude backup frames from the main frame count. |
| `pdfpc` | Presenter-console conditional | Add notes and metadata used by PDF Presenter Console. |
| `animate` | Tested-viewer exception | Embed frame animations only after the exact PDF viewer and presentation computer pass a rehearsal. |
| `tagpdf` and LaTeX PDF management | Tested accessibility profile | Use only in a controlled target whose class, packages, validation tool, and archive requirements have been tested together. Do not claim PDF/UA from package loading alone. |

## Build and verification

The supported user toolchain is TinyTeX with LuaLaTeX. Quarto is the document
manager and uses its built-in PDF build wrapper. Verify the active installation
before document work:

```bash
scripts/visualize/check-latex-toolchain.sh
```

If the check fails because TinyTeX is absent or inactive, use the one supported
setup route and restart the terminal or Codex task:

```bash
quarto install tinytex --update-path
```

Preflight the selected route rather than installing a broad collection:

```bash
kpsewhich siunitx.sty
kpsewhich mhchem.sty
kpsewhich booktabs.sty
command -v lualatex
command -v latexmk
command -v biber
```

Add the checks implied by optional modules, such as `makeglossaries`,
`latexminted`, `inkscape`, or `latexdiff`. Compile using the repository wrapper;
for an isolated author-controlled source, the narrow fallback is:

```bash
latexmk -lualatex -interaction=nonstopmode -halt-on-error main.tex
```

For Quarto, render the real target with the project's `./render.sh`. Inspect the log and
the PDF, including equations, unit spacing, reaction notation, numeric column
alignment, captions, links, bookmarks, bibliography, glossary, diagrams,
fonts, clipping, and page breaks. A package decision is complete only when the
source declares one owner for every overlapping capability and the assembled
document passes these checks.

For scientific tables, use `\toprule`, `\midrule`, and `\bottomrule`; omit
vertical and double rules, place units in numeric-column headings, align values
with `S`, and retain leading zeros for magnitudes below one. For accessible
color, target at least 4.5:1 contrast for ordinary text and 3:1 for large text
and essential non-text marks. Keep series distinguishable by marker or line
style in grayscale. Tagged PDF is a separately tested output profile, not a
default switch.

Apply `latex-layout-and-qa.md` when the source compiles but page geometry,
connector clearance, bounding boxes, or shared article/Beamer sizing requires
visual acceptance.

## Official references

- [Quarto PDF and LaTeX includes](https://quarto.org/docs/output-formats/pdf-basics.html)
- [Quarto Beamer](https://quarto.org/docs/presentations/beamer.html)
- [PGF/TikZ](https://ctan.org/pkg/pgf) and [PGFPlots](https://ctan.org/pkg/pgfplots)
- [`siunitx`](https://ctan.org/pkg/siunitx), [`booktabs`](https://ctan.org/pkg/booktabs), and [`mhchem`](https://ctan.org/pkg/mhchem)
- [`biblatex`](https://ctan.org/pkg/biblatex) and [`glossaries-extra`](https://ctan.org/pkg/glossaries-extra)
- [`minted`](https://ctan.org/pkg/minted), [`chempid`](https://ctan.org/pkg/chempid), and [`achemso`](https://ctan.org/pkg/achemso)
