# Analysis sets

A new CSE-created side study defaults to a root-level analysis set:

```text
analyses/<short-id>/
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
placeholder files. The main model, flowsheet, package,
or objective remains in its natural repository location. Preserve existing
structured metadata only when a real repository command consumes it; unused
analysis metadata is not a default.

Analyze owns inputs, scripts, retained results, and figures. It must retain the
exact values shown in tables and plots. A failed or missing result returns to
Diagnose when its cause is not established. Without a useful method-specific
numerical result, the work cannot be called complete and no empty figure is
created. Review checks the scientific result, failure diagnosis, values,
displays, interpretation, and claim boundary. A status flag,
unexplained failure, or empty display cannot advance.

Retain the necessary method and conditions, result, interpretation, limitations,
and exact evidence paths. A negative result that meets
[failure-triage](failure-triage.md#fix-before-a-negative-disposition) needs a
table or figure only when it clarifies the claim.

A central numerical relationship or comparison backed by retained row-level
values has one claim-led figure that directly answers the scientific question.
This applies to model-versus-observation comparisons, competing methods or
formulations, parameter or sensitivity sweeps, trajectories, refinement or
convergence, and uncertainty distributions. The retained CSV owns the exact
values; a compact table may support the figure but neither a CSV link nor a
table replaces it. A table-only result is appropriate for a few scalar or
categorical values, an exact lookup, or a negative result meeting
[failure-triage](failure-triage.md#fix-before-a-negative-disposition) when the
analysis explains why plotting would not clarify the claim. Preserve discrete
predictions as points unless retained continuous evaluations support a line.

Git and retained result files preserve history. Before Review, state that the
results await independent review and investigator promotion. After Review,
state the reviewed result commit, use, and limitations. Follow the
[investigator promotion procedure](operating-model.md#continuation-and-investigator-promotion)
before manuscript use.

In chat, state the interpreted result, evidence quality, limitations, and
remaining scientific question, and link the retained evidence.
