# Analysis sets and the root Quarto analysis site

A confirmed `analysis` repository normally has one root Quarto analysis site at
`analyses/`. Its home page is a populated `index.qmd` synthesis article; its
other pages are only the substantive analysis `.qmd` reports explicitly
included by Visualize.
`project.render` and `website.sidebar` are the sole ordered publication
memberships; every included report appears exactly once in both, and an
unregistered `.qmd` is not rendered. A confirmed `tool` repository gets no
Quarto analysis site by default.

A new CSE-created side-study question defaults to the root-level
`analyses/<short-id>/` set, which can be included in the root Quarto analysis site:

```text
analyses/<short-id>/
  report.qmd
  inputs/
  scripts/
  results/
  figures/
```

An established repository may retain a coherent analysis set at any safe
repository-relative path and may use any meaningful populated child names.
Adopt that location only when its scientific question, retained content,
callers, and ownership are clear. Do not rename, duplicate, or migrate it
solely to match the default above.

In the default layout, `inputs/` owns the exact retained calculation snapshot
and provenance. An adopted layout assigns the same responsibilities to its
established child names. Analysis scripts, results, figures, and substantive
reports have no accepted owner under `docs/scientific/`. Create the
named root only when a real scientific question and retained starting content
exist. Create a subdirectory only when it contains retained content; do not add
placeholder files or an initial notebook. The main model, flowsheet, package,
or objective remains in its natural repository location. Preserve existing
structured metadata only when a real repository command consumes it; unused
analysis metadata is not a default.

Analyze owns inputs, scripts, retained results, and figures. It must retain the
exact values shown in tables and plots. A failed or missing result returns to
Diagnose when its cause is not established. Without a useful method-specific
numerical result, the work cannot be called complete and no notebook or empty
figure is created. Review checks the scientific result, failure diagnosis,
values, displays, interpretation, and claim boundary. A status flag,
unexplained failure, or empty display cannot advance.

After a useful method-specific result exists, Summarize alone creates or fully
refreshes a substantive report `.qmd` in its analysis set, includes it in the
root Quarto analysis site, and explicitly refreshes its presentation view. The report
and selected render exist before Review so the reviewer sees the same
scientific presentation as the investigator. The report reads retained outputs and
must not rerun the scientific model. It presents the current coherent question,
necessary method and conditions, warranted results and displays, pragmatic
conclusions, limitations, next steps, and exact retained paths. A negative result
that meets [failure-triage](failure-triage.md#fix-before-a-negative-disposition)
need not invent a table or figure.

A central numerical relationship or comparison backed by retained row-level
values has one claim-led figure that directly answers the scientific question.
This applies to model-versus-observation comparisons, competing methods or
formulations, parameter or sensitivity sweeps, trajectories, refinement or
convergence, and uncertainty distributions. The retained CSV owns the exact
values; a compact table may support the figure but neither a CSV link nor a
table replaces it. A table-only result is appropriate for a few scalar or
categorical values, an exact lookup, or a negative result meeting
[failure-triage](failure-triage.md#fix-before-a-negative-disposition) when the
notebook states why plotting would not clarify the claim. Preserve discrete
predictions as points unless retained continuous evaluations support a line.

Git and retained result files preserve history; the notebook does not narrate
progress or workflow labels. Before Review, state plainly that it has not been
independently reviewed or promoted for manuscript use. After Review, state the
reviewed commit, use, and limitations; manuscript use still requires investigator
promotion. After promotion, state the exact notebook commit, use, and
limitations confirmed by the investigator.

The report source is complete core output. When the endpoint selects rendering
and its required renderer executable is available, hand the same `.qmd` and
retained values to the root Quarto analysis site for ordinary HTML and explicit
presentation refresh. A promoted LuaLaTeX PDF is an optional second view from
the same source. When a required renderer is unavailable, finish independent
core setup/report work and report the exact missing executable and setup step;
do not install it without authority. Keep generated outputs under the Quarto analysis site output directory
for inspection and normally ignore them. The report is the durable
user handoff for the analysis. The task response briefly states the interpreted
result, evidence quality, limitations, and real question frontier and links the
notebook rather than replacing it.
