# CSE plugin review brief

## Purpose

CSE is a private, MIT-licensed Codex plugin that gives scientific
and mathematical repository work a science-first working method. It is aimed at
computational scientists, engineers, mathematicians, researchers, students,
and maintainers who need to move from a question and evidence to equations,
numerical methods, analyses, figures, notebooks, papers, or an independent
review.

The plugin is a behavioral and repository-practice adapter. It does not claim
to supply domain facts, a universal solver, a private literature corpus, or a
scientific verdict. The user and the applicable sources remain responsible for
scientific judgment.

The canonical source is
[`tannerpolley/cse`](https://github.com/tannerpolley/cse). The behavioral
heat-equation example is embedded at
[`examples/heat-equation/`](../../examples/heat-equation/README.md), so review
of the plugin and example uses one repository-local checkout.

## Non-goals

CSE does not:

- replace domain expertise, physical experiments, accepted standards, or
  literature judgment;
- decide whether a scientific claim is true or label a result as valid merely
  because code runs or converges;
- manage a user's Zotero library, private PDFs, or evidence corpus as plugin
  data;
- require Project Truss, Superpowers, Matt Pocock skills, a generic workflow,
  GitHub Actions, issue hierarchy, coverage percentages, or a lifecycle
  database;
- prescribe dataset versioning, mutate Zotero, automate publisher pages, or guess full-text
  URLs without the user-controlled route; or
- force every project into the heat-equation example's equations, units,
  tolerances, or claim boundary.

## Architecture

The plugin manifest is [`plugin.json`](../../.codex-plugin/plugin.json). Public
skills stay intentionally thin and route through shared references:

- [`operating-model.md`](../../references/operating-model.md) defines opening
  alignment, question rounds, confirmation, continuation, and stop conditions.
- [`scientific-method.md`](../../references/scientific-method.md) defines
  equations, sources, verification, validation, uncertainty, issue content,
  and scientific language.
- [`numerical-testing.md`](../../references/numerical-testing.md) defines
  result-first numerical expectations, independent oracles, metrics, tolerance
  rationale, and risk-based test selection.
- [`scientific-projects.md`](../../references/scientific-projects.md) defines
  repository records, analysis directories, plots, notebooks, bibliography,
  and manuscript conventions.
- [`github-and-git.md`](../../references/github-and-git.md) defines the
  authoritative GitHub lifecycle and guarded synchronization and cleanup.
- [`zotero-companion.md`](../../extensions/cse-sources/references/zotero-companion.md) defines the
  Zotero authority, Companion capability contract, exact source lineage,
  bibliography, and on-demand extraction boundaries.
- [`terminology.md`](../../references/terminology.md) defines canonical
  workflow, tool, source, extraction, figure, and claim language.

The nine workflow stages are:

| Entry point | Main endpoint | Next route when work continues |
| --- | --- | --- |
| [`setup`](../../skills/setup/SKILL.md) | Repository vocabulary, scientific records, bibliography, plotting, writing, and integration defaults | The skill that owns the selected scientific endpoint |
| [`research`](../../skills/research/SKILL.md) | Literature, theory, data, equations, and method evidence | `design` for substantive repository work |
| [`diagnose`](../../skills/diagnose/SKILL.md) | Cause of numerical or scientific disagreement | `design` with the correction boundary |
| [`design`](../../skills/design/SKILL.md) | A complete question and native GitHub issue | `build`, `analyze`, or `write` |
| [`build`](../../skills/build/SKILL.md) | Equations, models, numerical methods, solvers, or data transformations | `analyze` |
| [`analyze`](../../skills/analyze/SKILL.md) | Convergence, sensitivity, uncertainty, comparison, and figures | `review` or `diagnose` |
| [`summarize`](../../skills/summarize/SKILL.md) | The current reviewed analysis research notebook | `write` or `review` |
| [`write`](../../skills/write/SKILL.md) | Evidence-supported papers, reports, captions, and LaTeX | `review` |
| [`review`](../../skills/review/SKILL.md) | Whole-chain scientific and repository review | Route material corrections to the owning skill |

Supporting tools are public skills, but they are not workflow stages:

| Tool | Role | Returns to |
| --- | --- | --- |
| [`zotero`](../../extensions/cse-sources/skills/zotero/SKILL.md) | Retrieve, inspect, and cite source evidence | Invoking workflow stage |
| [`mathpix`](../../extensions/cse-sources/skills/mathpix/SKILL.md) | Create a source-linked Markdown companion from a confirmed Zotero PDF when no usable child exists | Invoking workflow stage |
| [`plot`](../../extensions/cse-visualize/skills/plot/SKILL.md) | Render or review figures from retained values with explicit visual semantics | `analyze`, `summarize`, `write`, or `review` |
| [`digitize`](../../extensions/cse-sources/skills/digitize/SKILL.md) | Recover calibrated values from source figures with independent QA | `analyze` or `review` |
| [`tikz`](../../extensions/cse-visualize/skills/tikz/SKILL.md) | Create document-native LaTeX diagrams, schematics, geometry, and annotations | `write` or `review` |
| [`pgfplots`](../../extensions/cse-visualize/skills/pgfplots/SKILL.md) | Create table-driven LaTeX-native quantitative plots | `analyze`, `summarize`, `write`, or `review` |

The initial workflow entrypoint inspects the repository and asks a material question
round. After confirmation, internal handoffs inherit decisions and ask only
delta questions. This is adaptive alignment, not a stage-by-stage stop ritual.

At runtime the plugin is self-contained. It does not invoke Project Truss,
Superpowers, Matt Pocock skills, or another workflow family. The installed
surface is Markdown, YAML, JSON, and reusable LaTeX templates. Repository work can use the local shell,
Git, `gh`, Python, LaTeX, Zotero, and the separately installed Companion when the user's
repository and environment provide them; those are workflow capabilities, not
hidden plugin dependencies.

## Repository layout

```text
.codex-plugin/plugin.json       installable manifest and interface metadata
skills/<stage-or-tool>/SKILL.md nine workflow stages plus supporting tools
references/*.md                 shared scientific, numerical, Git, and source doctrine
scripts/validate.sh             source validation and contract checks
scripts/sync-live.sh             guarded source-to-marketplace deployment
scripts/check_prose.py          forbidden-language check
extensions/cse-sources/scripts/sync_bibliography.py  one-way bibliography snapshot helper
tests/                          front-door and destructive-operation safeguards
docs/design/                    product decisions and external-review package
```

The project keeps user-specific scientific context, equations, methods,
evidence, analyses, notebooks, and manuscripts in the user's repository rather
than in the installed plugin. The embedded heat-equation example shows the intended
project-facing shape in its
[scientific context](../../examples/heat-equation/docs/scientific/CONTEXT.md),
[formulation](../../examples/heat-equation/docs/scientific/formulation.tex),
[methods](../../examples/heat-equation/docs/scientific/methods.tex),
and [evidence plan](../../examples/heat-equation/docs/scientific/evidence.tex).

## Scientific doctrine to examine

The central doctrine is result-first numerical work. A reference case or
falsifiable relation, independent source or derivation, metric, tolerance
rationale, and failure meaning should be defined before implementation when
practical. Tests are selected by scientific risk. Analytic or manufactured
solutions, conservation and dimensional invariants, convergence, independent
method comparisons, sensitivity, uncertainty propagation, and demonstrated
failure regressions are preferred over helper-by-helper coverage.

Equation records preserve symbols, units or basis, assumptions, validity
domain, source locators, alternate conventions, and links to code and tests.
The plugin keeps code verification, solution verification, model validation,
and uncertainty distinct. It does not treat one global epsilon or one coverage
percentage as scientific evidence.

The plotting and writing doctrine retains exact plotted values and publication
formats, labels quantities and units, distinguishes models, observations,
literature, and uncertainty semantically, and treats the notebook as the
current reviewed analysis record and the manuscript as a selected story.

## Validation and evaluation evidence

The source validator is [`scripts/validate.sh`](../../scripts/validate.sh). It
currently:

1. runs the Codex plugin and skill validators;
2. runs the repository's Python contract and script tests;
3. checks prose under the installable surface for forbidden language and
   unresolved placeholders; and
4. checks Bash syntax for the lifecycle scripts.

The contract tests in
[`tests/test_contract.py`](../../tests/test_contract.py) protect the manifest,
the exact eight-workflow/six-tool skill surface, thin skills, shared-reference
links, opening alignment anchors, numerical doctrine, optional GitHub features,
forbidden runtime workflow names, and the absence of generic coverage
assumptions.
[`tests/test_scripts.py`](../../tests/test_scripts.py) exercises bibliography
synchronization, prose rejection, marketplace preservation, and deployment
rollback. This is a front-door and scientific-doctrine suite, not a
coverage-driven expansion of helpers.

The post-merge deployment route is
[`scripts/sync-live.sh`](../../scripts/sync-live.sh). It refuses an uncommitted
source tree, validates a temporary copy, runs the plugin validator again, and
updates the personal marketplace with rollback protection. A fresh Codex task
is required after installation so the task receives a newly installed skill
surface. The repository has no assumed GitHub Actions or required remote
status checks.

The example's setup validator, executable solver, retained numerical study, and
bibliography helper provide behavioral evidence for one repository route. Its
generated full bibliography snapshot is
[`docs/scientific/latex/references.bib`](../../examples/heat-equation/docs/scientific/latex/references.bib).
The example demonstrates code and solution verification, but it does not claim
physical validation.

## Privacy and source assumptions

Zotero owns bibliographic metadata, collections, and attachments. Zotero
Companion is optional, user-owned, and source-linked. The plugin should read
configured Companion evidence before remote search, preserve exact locators,
and leave Zotero corrections and paper acquisition to a previewed,
user-controlled route. Private paths and PDFs should not enter the plugin cache
or a public repository.

Each project declares its data authority, formats, lineage, retention,
versioning, and recovery. Companion provides a local corpus, LinkML schema,
DuckDB indexes, and a path-sanitized Better BibTeX export. Project snapshots
contain only cited records and are never hand-edited.

## Limitations and high-value review questions

The plugin is advisory and depends on the user's scientific context, sources,
toolchain, and judgment. It cannot guarantee that a model is physically valid,
that an oracle is independent, or that a user will preserve claim boundaries.
The current package has no cross-domain benchmark for question quality,
uncertainty interpretation, or reviewer agreement. Companion integration,
domain packs, registry adapters, private-source permissions, and the right
amount of alignment questioning remain open design areas.

An external review would be most valuable on these questions:

- Does the vocabulary make scientific reasoning clearer without becoming
  process theatre or generic software language?
- Do the numerical and uncertainty rules distinguish code correctness,
  discretization error, physical validation, and scientific acceptance in
  practice?
- Do the nine workflow stages form a coherent route with useful continuity,
  and do the six supporting tools avoid becoming competing stages?
- Is the grilling quality material and adaptive without blocking ordinary work?
- Is the Zotero and Companion boundary safe, understandable, and useful for
  source-linked research?
- Do plotting, notebook, manuscript, GitHub, and review expectations support
  reproducible science rather than documentation for its own sake?
- Is the plugin genuinely self-contained and installable, and does the example
  demonstrate the promises it makes?
- Which scientific workflows are missing, ambiguous, or over-generalized?
- What would make the product useful beyond this one heat-equation benchmark?

Please distinguish observed repository evidence from inference, cite exact files
and lines or sections, and avoid generic software-engineering boilerplate or
coverage recommendations that are not tied to a scientific risk.
