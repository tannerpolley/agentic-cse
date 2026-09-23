---
name: summarize
description: "Create or refresh the analysis research notebook (Quarto .qmd) and a chat summary from retained results, before review. Use when asked to \"summarize the results\", \"write up the notebook\", or \"what did we find\" after analyze. Papers and reports go to write."
metadata:
  cse-kind: "workflow"
  cse-family: "workflow"
  cse-order: "06"
  cse-tags: "workflow"
  cse-routing:
    direct: [operating-model, scientific-projects]
    conditional: [scientific-method]
---

# Summarize results

Read first: [operating-model](../../references/workflow/operating-model.md), [scientific-projects](../../references/workflow/scientific-projects.md).

Activate [scientific-method](../../references/workflow/scientific-method.md) for interpretation, verification, validation, or
uncertainty. Return a chat summary of the main points and research
notebook. For a retained relationship or comparison, use
`cse:plot` after checking the renderer capability, providing retained values, intended use,
quantities, units, series roles, uncertainty, and scales. Ordinary Quarto HTML
is the default living notebook view; the project selects other rendering.
For an adopted analysis, use the presentation-only `present` entry to prepare
tables, figures, or include fragments from retained outputs; it must not
calculate a missing result. Read the [Snakemake workflow reference](../../references/workflow/snakemake.md).

Inspect the useful method-specific result, retained values, figures,
diagnostics, and existing notebook. A poor result may continue when values and
diagnostics answer or bound the question. The notebook preserves provenance,
units, uncertainty, limitations, and point-versus-line meaning, and must not
rerun the model. Reject empty displays, unsupported curves, unsupported
statistics, and unexplained failures. Follow [scientific-projects](../../references/workflow/scientific-projects.md) for the
claim-led figure requirement and its table-only exceptions.

The chat summary states the outcome, basis and conditions, supported quantities
and units, physical interpretation, uncertainty and limits, whether evidence is
prediction, numerical verification, or physical validation, and the affected
decision. If no physical or numerical result exists, say so and state the
scientific consequence or next decision; software status is provenance.

Summarize alone creates or refreshes a substantive `.qmd` report from useful
retained evidence before Review. A confirmed analysis repository normally
publishes one root Quarto Manuscript under `analyses/`; include the report
exactly once with its native management command, use
`python3 analyses/manuscript.py refresh analyses analyses/<id>/notebook.qmd`
for the notebook and root views. Refresh also performs presentation preparation
when no preview is running. State that the report has not been independently reviewed
or promoted for the separate raw-LaTeX submission route. If a renderer is absent, finish the report and core summary, then report the
exact missing capability. Rendering never establishes a claim. Send the report,
values, and selected renders to `cse:review`; include the limitation.
