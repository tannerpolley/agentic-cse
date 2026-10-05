# CSE glossary

This is the plugin-wide glossary for conversations, questions,
issues, source files, figures, notebooks, manuscripts, and review reports.
Project-specific `GLOSSARY.md` files may add domain terms, but they should not
repurpose the workflow and tool terms below without an explicit decision.
Root `GLOSSARY.md` owns project vocabulary; an existing `GLOSSARY-MAP.md` links
additional glossaries. The scientific context links to vocabulary, not tables.

## Use the glossary

- Use the canonical term below after it has been resolved.
- When a user or source uses an overloaded term, state the precise term you
  will use and ask only if the distinction changes the work.
- Preserve a quotation when exact wording matters, but use canonical language
  in the surrounding explanation and durable record.
- Add a new term here only after the plugin-wide meaning is settled. Record
  project-only terms in the project's `GLOSSARY.md` instead, using Matt Pocock's
  `**Term**:`, short definition, and `_Avoid_: a, b` format. CSE requires a
  `Source:` line (`sourceless` when missing) and accepts optional `Scope:` paths.

## Workflow and tools

**Workflow stage**:
One step in the agent path: `setup`, `research`, `diagnose`, `design`, `build`,
`analyze`, `summarize`, `review`, or `write`.
_Avoid_: “context” as a phase name or tool when referring to a stage.

**Supporting tool**:
A capability invoked by a workflow stage and normally returning evidence or
files to that stage. Sources tools are `zotero`, `mathpix`, `data`, and
`digitize`. Visualize tools are `plot`, `tikz`, `pgfplots`, `latex`, `quarto`,
and `beamer`. `prose` inspects scientific writing and final manuscript cohesion
without authoring or accepting scientific claims.
_Avoid_: workflow stage or an extra step in the agent path.

**Skill family**:
The primary discovery group shown in the skill picker: Workflow, Sources, or
Visualize. Route tags such as `quarto-pipeline`, `latex-toolbox`, `matplotlib`,
`zotero`, and `data-extraction` may overlap; they do not create more workflow
stages.

**Starting stage**:
The workflow stage where the task enters the agent path. Use this in
user-facing explanations.
_Avoid_: front door or entrypoint in user-facing prose. `entrypoint` is
reserved for technical skill metadata and design discussion.

**Continuation**:
Moving to the next relevant workflow stage, or returning to the stage that
owns a correction after a supporting tool or review.
_Avoid_: implying that every stage is mandatory or that a tool creates a new
stage.

**Review Pass**:
Reviewer advice that the active issue, implementation, evidence, claims,
notebook, and selected outputs support the identified use within the stated
limitations. It is not universal certification or investigator promotion.

## Scientific work

**Scientific question**:
The decision, comparison, or explanation the work is intended to answer.

**Reference case**:
An independent known value, relation, analytic solution, accepted experiment,
standard, or justified baseline used for comparison.
_Avoid_: oracle by itself in user-facing prose; write `independent reference
case` and use `oracle` only when the testing literature or code requires it.

**Observation**:
A measured, reported, or digitized value retained with its source and
uncertainty. Use `data` for a collection of observations or other retained
values.

**Fitted relationship**:
A model or curve estimated from observations. Plot it as a line when the
figure represents a continuous relationship; plot observations as points.

**Scientific claim**:
A statement supported by identified evidence under stated conditions and
bounded by its limitations.

**Interpretation**:
What the evidence suggests, including competing explanations and what it does
not establish.

**Regression analysis**:
Statistical estimation of a relationship or parameters from observations. Use
“regression” for this scientific meaning, not for a software previous-failure
check.

**Persistent behavior check**:
A repository check retained to expose a distinct loss of scientific or
user-facing tool behavior. A check for one previously demonstrated defect may
be called a previous-failure check.
_Avoid_: “regression test” in CSE prose.

**CSE audit**:
A read-only inspection for generic software-engineering ceremony that displaces
scientific questions, methods, numerical work, and interpretation. It does not
judge scientific truth or replace Review.

**Provenance**:
The recorded origin, transformation, and identity of a source, input, result,
or figure value.

## Sources and extraction

**Source record**:
The bibliographic item owned by Zotero, including its metadata, collection
membership, and attachments.

**Source evidence**:
A source passage, equation, table, figure, row, or retained value with an
exact locator and applicability check.

**Source-linked Markdown companion**:
A Markdown transcription linked to a confirmed Zotero PDF when no usable
Markdown child exists. It is transcription, not validated scientific truth.

**Data extraction**:
Recovering machine-readable values from a source table, supplement, vector
file, PDF, or figure. Use the narrower term when the source permits it.

**Figure digitization**:
Calibrated recovery of values from a source figure, with axis transforms,
provenance, and independent QA.
_Avoid_: extraction stage or treating digitized values as more
precise than the source supports.

**Plotting**:
Rendering a figure from retained values and explicit visual semantics. It is
not the numerical analysis that generated those values.

**Analysis set**:
The retained inputs, scripts, results, figures, notebook, and interpretation
for one coherent scientific question.

**Analysis research notebook**:
An explicitly included substantive `.qmd` report, rendered as one page of the
root Quarto analysis site. It reads retained values without rerunning the model
and is rendered only when its path appears once in both `project.render` and
`website.sidebar`. It is not a chronology, raw evidence inventory, or
raw-LaTeX submission draft.

**Manuscript**:
An author-controlled raw-LaTeX article that selects supported results and
presents one continuous scientific argument from abstract through conclusion.

**Quarto analysis site**:
The root Quarto website project whose home page is a populated synthesis article
and whose other pages are the explicitly included analysis reports, all sharing
one sidebar. It is the living HTML synthesis/notebook route; Review owns scientific acceptance, while Write owns deliberate promotion
to the separate raw-LaTeX Manuscript route.
