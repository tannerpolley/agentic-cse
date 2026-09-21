---
name: summarize
description: "CSE Execute and deliver — Create the working analysis research notebook and chat summary from retained results."
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

Activate `scientific-method` for interpretation, verification, validation, or
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
statistics, and unexplained failures. Follow `scientific-projects` for the
claim-led figure requirement and its table-only exceptions.

The chat summary states the outcome, basis and conditions, supported quantities
and units, physical interpretation, uncertainty and limits, whether evidence is
prediction, numerical verification, or physical validation, and the affected
decision. If no physical or numerical result exists, say so and state the
scientific consequence or next decision; software status is provenance.

Summarize alone creates or refreshes a substantive `.qmd` report from useful
retained evidence before Review. A confirmed analysis repository normally
publishes one root Quarto Manuscript under `analyses/`; include the report
exactly once with its native management command and explicitly refresh its
presentation view; pass `--external-results-changed` when retained inputs
changed. State that the report has not been independently reviewed
or promoted for the separate raw-LaTeX submission route. If a renderer is absent, finish the report and core summary, then report the
exact missing capability. Rendering never establishes a claim. Send the report,
values, and selected renders to `cse:review`; include the limitation.
