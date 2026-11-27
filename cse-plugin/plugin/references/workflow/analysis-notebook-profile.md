# Analysis-notebook profile

The notebook presents the current view of one coherent scientific question for Review.
Every section serves that question. Use one notebook per analysis set. For
article rendering, apply the [shared LaTeX requirements](../visualize/latex-article-profiles.md#shared-article-requirements).
Use the [writing principles](scientific-writing.md#shared-article-requirements)
for display choice, provenance, and captions.

## Output forms

The durable living view is ordinary Quarto HTML. An investigator may select the
portable LuaLaTeX PDF profile for a paged handoff. Both views render from one
curated Quarto source or from explicitly shared section, data, and figure
sources; they are not independent scientific records.

Use ordinary HTML images or tables for the HTML view and TikZ or PGFPlots
directly in the promoted PDF. Format-specific blocks may change the rendering
representation but not values, conditions, uncertainty, interpretation, or
limitations.

## Scope and appearance

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

## Notebook content

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

## Evidence guard

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
