# LaTeX article profiles

Use this reference when CSE creates, revises, summarizes into, or reviews a
manuscript or analysis research notebook. These are two author-controlled scientific
content profiles. They share the document tool bundle but have different
selection, structure, and presentation rules.

## Select the profile

| Profile | Scientific purpose | Organizing rule |
| --- | --- | --- |
| Manuscript | Present one selected scientific argument from abstract through conclusion | Every section advances the same question and supported conclusion |
| Analysis research notebook | Present the current view of one coherent scientific question for Review | Every section serves that question |

Use one profile per rendered document and one notebook per analysis set. Do not
turn an analysis research notebook into a manuscript by adding an abstract;
select the relevant investigator-promoted results and write a separate manuscript.

## Shared article requirements

- Use LuaLaTeX and KOMA-Script `scrartcl` for the author-controlled default.
  Let KOMA-Script own headings and page furniture. It also owns the manuscript
  type area; the analysis-notebook profile instead has one explicit margin
  owner.
- Keep a one-column body so equations, process diagrams, multipanel figures,
  and scientific tables retain readable width.
- Use the scientific core from `latex-packages.md`. Every article-capable tool
  in that reference may be used in either profile. A tool belongs to a
  capability, not to a profile.
- Load a package or extension only when the document exercises its capability.
  Select one owner for overlapping capabilities and keep profile styling out
  of shared notation and figure source.
- See `quarto-execution.md` for a Quarto project. Let Quarto own document
  assembly, presentation tables, citations, cross-references, and code
  highlighting. Keep execution disabled by default and never run the
  scientific model during document rendering. Keep stable LaTeX notation,
  packages, and semantic figure styles in reviewed headers.
- Present scientific provenance: data source, equations, parameter values,
  units, assumptions, comparison basis, and uncertainty. Keep agent actions,
  repository operations, build commentary, and chronological work history out
  of rendered scientific prose.
- Use result-led captions. A figure caption states the quantity, conditions,
  comparison, and supported observation. A table caption states what the
  values compare. Put figure captions below figures and table captions above
  tables.
- Follow the scientific tables rules in `latex-packages.md`.
- Apply `latex-layout-and-qa.md` to every selected PDF output. Compilation,
  resolved references, automated visual QA, and full-size page inspection are
  required for both profiles.

## Manuscript profile

### Appearance

- Use `scrartcl`, 11 pt, one-sided, one column, `DIV=calc`, normal heading
  size, conventional paragraph indentation, and restrained vertical spacing.
- Use a compact title block followed immediately by the abstract and
  keywords. Omit a table of contents and chapter-style title pages.
- Use black body text. Reserve the project color palette for figures, links,
  and small semantic accents that remain meaningful in grayscale.
- Use numbered sections and equations. Keep headers quiet and page numbers
  visible. Do not imitate a named publisher, masthead, volume, issue, or DOI.
- Place figures and tables near their first substantive discussion. Use float
  barriers only at real semantic boundaries.

### Structure

Use the applicable subset in this order:

1. title, authors, affiliations, and date;
2. abstract stating the question, method, principal result with conditions,
   and supported implication;
3. keywords and nomenclature when useful;
4. introduction;
5. formulation, theory, or governing equations;
6. experimental, computational, or analytical methods;
7. verification, validation, and uncertainty when they support the claims;
8. results;
9. discussion;
10. conclusions;
11. data, code, funding, or conflict statements when applicable;
12. references and selected appendices.

Merge adjacent sections when the scientific argument is clearer without a
separate heading. The manuscript remains one continuous story: introduce each
result before showing it, interpret it after showing it, and carry only the
evidence needed for the stated conclusion.

### Evidence guard

A result enters the manuscript only when it supports the selected claim order.
The manuscript may omit sound analyses that do not serve that story. It may
condense an analysis-notebook result, but reported values, conditions,
uncertainty, and claim boundaries must remain consistent with the retained
results.

## Analysis-notebook profile

### Output forms

The durable living view is ordinary Quarto HTML. An investigator may select the
portable LuaLaTeX PDF profile for a paged handoff. Both views render from one
curated Quarto source or from explicitly shared section, data, and figure
sources; they are not independent scientific records.

Use ordinary HTML images or tables for the HTML view and TikZ or PGFPlots
directly in the promoted PDF. Format-specific blocks may change the rendering
representation but not values, conditions, uncertainty, interpretation, or
limitations.

### Scope and appearance

- Create one notebook for one coherent scientific question. Use the repository's
  short analysis identifier rather than a workflow stage or time period.
- For PDF, use `scrartcl`, 10 pt, one-sided, one column, explicit 0.62 in left
  and right margins, and explicit 0.55 in top and bottom margins. These margins
  alone own the notebook type area; do not combine them with `DIV=calc` or a
  second geometry owner. Use 4 pt table column padding (`\tabcolsep`) and 1.05
  row spacing (`\arraystretch`) once in the notebook header.
- Use `\small` or `\footnotesize` locally only when a table requires it. Never
  use `\scriptsize`, whole-table scaling, clipped cells, or compressed rows as
  a fit repair; narrow or wrap columns, or use landscape placement. Let figures
  and tables use the available width when that improves the scientific
  comparison, without forcing every display to full width.
- Use a compact title block naming the project and question. Keep related
  results and floats together; use a table of contents only when it improves
  navigation.
- For HTML, use ordinary headings and a continuous result report with focused
  views for the question, conditions, results, interpretation, limitations,
  next steps, and provenance.
- Give plots, diagrams, equations, and tables the available text width. Prefer
  one strong result display over a dense page of marginal outputs.
- Omit an abstract and paper-style narrative introduction. Include the
  pragmatic conclusion and useful next steps supported by the analysis.

### Notebook content

Include only the material needed to review the analysis:

1. **Question:** one precise sentence naming the quantity or comparison.
2. **Conditions:** a compact table or short block giving inputs, units,
   assumptions, method, and comparison basis.
3. **Results:** retained plots, diagrams, equations, tables, and the key
   numerical values.
4. **Interpretation:** a concise statement of what the results support.
5. **Limitations:** only boundaries that materially constrain use of the
   result.
6. **Conclusions and next steps:** the pragmatic answer and useful supported
   continuation.
7. **Provenance:** exact retained-result and source paths.

Use subsections only when they improve navigation among substantial content.
Captions and tables should carry most local explanation. Avoid repeated prose
when the conditions table or figure caption already states the information.

### Evidence guard

Review the completed notebook and selected render against these questions:

- the calculation is reproducible from retained inputs;
- balances, invariants, convergence, comparisons, and uncertainty required by
  the question have been checked;
- every displayed value agrees with its retained result table;
- every figure and table passes scientific and visual review;
- captions identify quantities, conditions, and series roles;
- the primary figures answer the question and diagnostics remain secondary
  unless the question requires them;
- a named authoritative limit is applied when one governs the intended use;
  otherwise the notebook reports the actual comparison and diagnostics;
- the interpretation stays inside the tested domain.

Keep exploratory plots, malformed tables, duplicate views, raw diagnostics,
uninterpreted diagnostics, unsupported continuous-looking curves, statistics
without a comparison basis, and unexplained attempts outside the rendered
notebook. Include a poor fit or failed model only when it contains useful
values and diagnostics that constrain the interpretation. An unresolved
disagreement returns to Analyze or Diagnose before Review Pass.
Fully replace the prior coherent view; Git and retained results preserve
history.

## Manuscript writing and source organization

Treat mechanical correctness as the first check. A manuscript build must have
no unresolved references, duplicate labels, or missing citation keys. These
checks do not establish prose completeness; review the assembled manuscript
for statements whose meaning still depends on information outside the document.

Before publication review, correct these general classes:

- Identify every transferred parameter, analogue, correlation, or property value by name, source, exact locator, and applicability; state when transfer to the present system is an assumption.
- Define every objective, constraint, operating domain, and comparison method before its result or sensitivity appears.
- Give the rationale for fixed sensitivity cases, selected designs, reference conditions, and reported optima when the choice is not self-evident.
- State phase-volume, composition-basis, standard-state, sign, unit, and normalization conventions instead of saying only that source conventions were retained.
- Identify the operating conditions associated with large errors, failed checks, rejected states, and non-evaluable cases when they constrain interpretation.
- Match verbs to the evidence: use “considered during model selection” when alternatives were screened but their comparison is not presented, and reserve “retained for comparison” for comparisons actually shown.
- Remove temporal revision language such as “now” unless the manuscript explicitly compares defined versions.
- Replace repository-ownership terms such as “owner,” “campaign,” and “retained result table” with the actual equation, calculation, validation study, or reported table meant for a reader.

### Keep one authoritative manuscript edition

- Advertise one current manuscript entrypoint and one current build command.
- Remove an obsolete draft from ordinary navigation and build commands, or mark it unmistakably as historical and outside current scientific claims.
- Do not let a writing checker silently exclude an older edition that is still advertised as buildable.
- Search legacy sections, appendices, README instructions, and build scripts for publication claims that disagree with the current manuscript.

### Make paragraphs and sentences inspectable

LaTeX sections, equations, figures, and tables have explicit commands and
labels; ordinary paragraphs and sentences do not. Use source layout to make
prose reviewable without adding rendered structure:

1. Put one complete sentence on each physical source line.
2. Keep blank lines as paragraph boundaries.
3. Add one stable comment identifier before each paragraph, using a section-based form such as `% P:introduction-05`.
4. Derive a sentence identifier from the paragraph identifier and sentence order when a review tool needs one; do not store a second sentence map in the manuscript source.
5. Generate any paragraph- or sentence-cohesion report under `builds/`; do not maintain a duplicated manuscript map.
6. Do not use `\paragraph{}` or sentence-wrapper macros merely to create tracking identifiers. They add formatting or command semantics without improving the scientific argument.

For example:

```latex
% P:introduction-05
Reported batch extraction percentages do not define a process model for this solvent.
Lithium and sodium partition between two nonideal liquids while the extractants compete for finite inventory.
The reactive liquid-liquid-equilibrium calculation resolves those coupled effects.
```

The three source lines render as one paragraph because no blank line separates
them.

### Drafting versus final review

Keep routine builds mechanical: verify paragraph identifiers, source order,
sentence-per-line layout, blank-line boundaries, and LaTeX references and
citations. A prose edit does not require an agent review.

At a requested final check or publication handoff, invoke `cse:prose` and use
the manuscript checkpoint in `references/workflow/scientific-projects.md`.
That rule follows sentence ideas and roles through paragraph themes, section
claims, adjacent transitions, and one manuscript argument. Material story
changes invalidate an earlier final review; local wording changes do not
create a new drafting gate. Generated judgments use the stable identifiers
above and stay outside the authoritative manuscript. Mechanical checks may
verify those judgments' identity and coverage, never invent their meaning.
This cohesion inspection does not establish scientific truth or replace
evidence review and investigator promotion.

### Separate scientific correction from source reflow

Correct missing identities, assumptions, methods, conditions, and claims before
reflowing the source. Commit the scientific prose correction separately, then
make the one-sentence-per-line conversion as a formatting-only commit. The
separate diff keeps scientific review focused and makes later source
reorganization mechanically checkable.

## Promotion between profiles

An analysis research notebook presents one reviewed analysis set. A manuscript
selects only investigator-promoted notebook results and rewrites that evidence
into one argument.
Share retained tables, figure sources, notation, and bibliography keys. Do not
share profile headers, document structure, or rendered workflow language.
