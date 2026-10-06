# Agentic Computational Science and Engineering decisions

This document is the durable decision record for the CSE product.
It summarizes the originating Project Truss grilling and the later setup of the
embedded [heat-equation example](../../examples/heat-equation/README.md).
It is a decision summary, not a transcript. Statements below are separated into
plugin-wide decisions and choices made only for that example.

## Unified plugin decision

The `cse` plugin owns all 21 individually callable workflow, source, data, and
rendering skills under the `cse:<skill>` namespace. It is staged from the single
`plugin/` payload, identified by source commit and payload hash, and installed
as one package. External Zotero, corpus, authentication, and renderer
capabilities remain separately checked at use time.

The three canonical phases are Research and design, Build, and Summarize,
review, and write. Direct execution remains the default; a named skill does
not create role tasks unless the user explicitly requests them.

Rejected alternatives are duplicate plugin roots, forwarding skills,
compatibility aliases, and duplicated scientific doctrine. Source skills return
provenance and QA without judging claims. Rendering skills consume retained
values, never run the scientific model, and treat successful rendering as
distinct from Review Pass.

## Product vision

Agentic Computational Science and Engineering is a self-contained Codex plugin for scientific and
mathematical work. It changes how an agent frames a scientific question,
researches sources, formulates equations, implements numerical methods,
evaluates results, preserves evidence, and writes or reviews a supported
scientific record.

The product is a behavioral and repository-practice adapter, not a repository
of scientific facts. It helps users produce scientific tools, numerical
analyses, research notebooks, figures, and papers while leaving scientific
judgment with the user and the applicable domain evidence.

Intended users include computational scientists, engineers, mathematicians,
researchers, students, and maintainers of scientific repositories. The work
may include literature and data research, equation or model formulation,
numerical solvers, data transformation, convergence and uncertainty studies,
method comparison, figure generation, manuscript preparation, and whole-chain
review.

The product does not promise that a calculation is physically valid merely
because code runs or a numerical result converges. Its job is to make the
question, evidence, numerical behavior, uncertainty, interpretation,
limitations, and claim boundary explicit.

## Shared vocabulary

The plugin uses the following terms across its workflow stages, supporting
tools, and references:

| Term | Working meaning |
| --- | --- |
| Question | The scientific decision or comparison the work is meant to answer. |
| Equation or model | The stated mathematics or physical representation, including symbols, units or basis, assumptions, and validity domain. |
| Method | The analytical, numerical, data, or writing procedure used to obtain or interpret a result. |
| Reference case or oracle | An independent value, relation, analytic solution, accepted experiment, standard, or justified baseline against which a result is compared. |
| Numerical behavior | Stability, convergence, residuals, invariants, sensitivity, failure modes, and other observed properties of a computation. |
| Tolerance | A quantity-specific comparison limit with a stated source, scale, and acceptance meaning. |
| Evidence | A source, derivation, retained input, result table, figure, test, or comparison that supports an interpretation. |
| Interpretation | What the evidence suggests, including competing explanations and what it does not establish. |
| Limitation | A known boundary on method, data, source, uncertainty, reproducibility, or claim. |
| Claim | A statement the documented evidence may support. |
| Code verification | Whether an implementation represents the stated mathematics. |
| Solution verification | Numerical error or behavior for the solved case, such as refinement, residual, conservation, or convergence evidence. |
| Model validation | Comparison of a model with physical observations for its intended use. |
| Uncertainty | Traced numerical, input, parameter, measurement, model-form, or other variation in a reported quantity. |

The distinction among code verification, solution verification, model
validation, and uncertainty is a product-wide doctrine. Agreement with an
experiment does not prove the code, and convergence does not prove the
physical model.

## Self-contained architecture

The plugin keeps public skills thin and puts shared scientific behavior in
versioned references. The [operating model](../../plugin/references/workflow/operating-model.md),
[scientific method](../../plugin/references/workflow/scientific-method.md),
[numerical testing](../../plugin/references/workflow/numerical-testing.md),
[scientific project records](../../plugin/references/workflow/scientific-projects.md),
[GitHub and Git](../../plugin/references/workflow/github-and-git.md) references are the shared
doctrine. Sources owns its operational
[Zotero Companion](../../plugin/references/sources/zotero-companion.md)
behavior, and Visualize owns its rendering references. Repository-specific
equations, methods, evidence, notebooks, analyses, and writing rules remain in
the user repository.

The [terminology reference](../../plugin/references/workflow/terminology.md) is the canonical
glossary for workflow stages, supporting tools, sources, extraction,
figures, and claims.

The nine workflow stages form the default agent path:

1. [`setup`](../../plugin/skills/setup/SKILL.md) establishes repository vocabulary,
   scientific documents, bibliography, writing rules, and integration paths.
2. [`research`](../../plugin/skills/research/SKILL.md) investigates literature, theory,
   data, equations, and numerical methods.
3. [`diagnose`](../../plugin/skills/diagnose/SKILL.md) establishes the cause of a
   numerical or scientific disagreement.
4. [`design`](../../plugin/skills/design/SKILL.md) lays out substantive work and
   publishes its native GitHub issue.
5. [`build`](../../plugin/skills/build/SKILL.md) implements equations, models,
   numerical methods, solvers, and data transformations.
6. [`analyze`](../../plugin/skills/analyze/SKILL.md) runs studies for convergence,
   sensitivity, uncertainty, comparison, and figures.
7. [`summarize`](../../plugin/skills/summarize/SKILL.md) replaces the analysis
   research notebook with the current retained results and selected render.
8. [`review`](../../plugin/skills/review/SKILL.md) checks the full scientific chain,
   including the notebook and selected render.
9. [`write`](../../plugin/skills/write/SKILL.md) uses only reviewed notebook results
   the investigator promotes for the named manuscript use.

The eleven specialist skills are public skills but are not workflow stages:

- Sources: [`zotero`](../../plugin/skills/zotero/SKILL.md),
  [`mathpix`](../../plugin/skills/mathpix/SKILL.md),
  [`data`](../../plugin/skills/data/SKILL.md), and
  [`digitize`](../../plugin/skills/digitize/SKILL.md) own source
  evidence, extraction, data lineage, and digitization QA.
- Visualize: [`plot`](../../plugin/skills/plot/SKILL.md),
  [`tikz`](../../plugin/skills/tikz/SKILL.md),
  [`pgfplots`](../../plugin/skills/pgfplots/SKILL.md),
  [`latex`](../../plugin/skills/latex/SKILL.md),
  [`quarto`](../../plugin/skills/quarto/SKILL.md),
  [`beamer`](../../plugin/skills/beamer/SKILL.md) own figures,
  LaTeX, and non-executing document rendering.

The workflow stages are connected routes rather than isolated commands. Tools
are invoked by a stage and normally return their evidence or files to that
stage. The initial workflow entrypoint inspects the current repository, asks a
material question round, confirms the interpretation and write authority, then
continues to the requested endpoint in the same task. Internal handoffs inherit
those decisions and ask only delta questions. The questions are meant to resolve
material scientific, numerical, writing, or repository choices. They are not a
requirement to stop after every stage or to ask for facts already present in
the repository.

Runtime self-containment is intentional. CSE does not invoke
Project Truss, Superpowers, Matt Pocock skills, or a similarly named generic
workflow. It has no required GitHub Actions, issue hierarchy, coverage target,
or lifecycle database. The installed plugin supplies the skills and shared
references; user repositories, local configuration, Zotero, and the separately
installed Companion remain separate.

## Coexistence with Matt Pocock's skills (2026-10-05, issue #127)

CSE and Matt's engineering skills are separate plugins that share files.
Neither absorbs the other; CSE remains self-contained without a runtime
requirement on Matt's skills. The subject decides overlapping routes: Matt's
skills own software work, while CSE owns scientific questions and evidence.
See [skill families](../../plugin/references/workflow/skill-families.md).

Root `GLOSSARY.md` owns project vocabulary in Matt's format, with CSE's required
`Source:` and optional `Scope:` lines. CSE also reads every glossary linked by
an existing root `GLOSSARY-MAP.md` but never creates a map. Setup migrates old
vocabulary rows with approval only when all columns map exactly, preserving
existing definitions and sources. Plain synonym-avoids share the term's scope;
rules with their own scope, exceptions, or other writing information remain in
`docs/scientific/CONTEXT.md` under `## Prose avoid rules`, with every column.
Unrelated tables and unmappable rows stay in place, with reasons in the preview.
The prose checker reads both vocabulary and those project writing rules.

New entries are inserted inside `## Language`. Only CSE-owned tables migrate.
Matt owns glossary files and maps, including Matt-format pre-1.3 `CONTEXT.md`
and `CONTEXT-MAP.md`. Setup never moves, renames, or merges them; its preview
only reports `git mv <path> <same dir>/GLOSSARY.md` (or `GLOSSARY-MAP.md`).
Matt files are not CSE stray contexts; their relationships and links stay put.
Caller rewriting is main's literal replacement code, with no new matcher.
A CSE stray file with unmapped rows stays in place, and its prose is not copied.
Later writing rules use the existing `## Prose avoid rules` section.
Missing mapped files are lazy, not errors; implicit scopes cover each glossary's
directory. Identical behavioral rules are not conflicts, and differing rules
conflict only in overlapping scopes at the checked file. The scientific context
retains questions, owners, roles, source/data adoption, and a glossary link.
Absorbing and deleting `GLOSSARY.md`, as proposed in draft PR #125, is rejected.

Use Matt's `/retro` for a requested retrospective, supplemented by CSE's
[science categories](../../plugin/references/workflow/retrospective.md).
Candidates trace to session moments, mechanical problems become checks, and
nothing changes before the user picks a candidate. Setup adds only one
retrospective navigation line to its always-loaded protocol, routing through
`cse:audit` and that skill's relative link to the reference.

## Science-first and numerical-testing doctrine

The plugin uses result-first Scientific Software Test-Driven Development. A
scientific expectation comes before implementation when practical:

- define inputs, units, basis, domain, model or method version, and expected
  value, trend, invariant, relation, or convergence behavior;
- identify an independent source or derivation, metric, tolerance rationale,
  and failure meaning;
- select the smallest tests that expose plausible scientific corruption; and
- add narrower interface checks only when parsing, units, indexing, or data
  transformation could change the scientific result.

Useful test families include literature or experiment reproduction, analytic or
manufactured solutions, conservation and dimensional invariants, symmetry and
limiting behavior, monotonicity, grid or solver convergence, cross-method or
independent-implementation comparison, sensitivity and uncertainty
propagation, and previous-failure checks for demonstrated numerical failures.

The plugin rejects a test pyramid, helper-by-helper coverage expansion, private
implementation mirroring, and one unexplained epsilon across unrelated
quantities. Tolerances separate source rounding, measurement or reference
uncertainty, floating-point and solver stopping error, discretization or
sampling error, legitimate method variation, and the scientific acceptance
criterion. The metric should match the quantity: absolute error near zero,
relative error away from zero, weighted or uncertainty-normalized residuals for
heterogeneous data, and norms or conservation measures for fields and
balances.

Explore permits disposable calculations but no persistent test or accepted
claim. Retaining a new or expanded test promotes it to durable scientific work:
the agent presents the complete scientific-risk, oracle, metric, tolerance,
failure, replacement, and runtime proposal and obtains explicit user approval.
Optional lifecycle hooks compare test contents with the session-start inventory
and report changes as advisories. They do not enforce test approval or judge
whether the proposal or science is correct. Prose violations remain blocking
for the prose this session writes in any checkout of the repository, including
lane worktrees, committed or not: files whose content differs both from the
integrated line (upstream, origin's default, or the local default branch) and
from what that checkout's branch held when the session started. Text that
arrived by merging or pulling reviewed work, and existing branches checked out
for review, are not attributed to the session.

Durable equations and correlations receive stable identifiers, exact source
locators, symbols, units or basis, assumptions, validity domain, and links to
implementation and tests. Alternate conventions stay named and distinct.
The [scientific-method reference](../../plugin/references/workflow/scientific-method.md)
separates formulation, methods, and evidence so an implementation cannot
silently replace the stated mathematics.

## Evidence and source hierarchy

When configured, research begins with repository context, Zotero, and Zotero
Companion before remote search. Preferred evidence is primary literature,
standards, accepted experiments, analytic derivations, and trusted independent
implementations. Claims that drive equations, parameters, data, tolerances, or
interpretation record exact page, section, equation, table, figure, or row
locators. Metadata or a paper alone is not treated as a validated project
conclusion without an applicability check.

[Zotero Companion](../../plugin/references/sources/zotero-companion.md) is the separately
installed capability-gated evidence and lineage layer. Zotero remains authoritative for
bibliographic metadata, collections, and attachments. Companion can hold
source-linked briefs, claims, equations, limitations, and structured data; it
does not become a second bibliography manager. Zotero corrections are separate,
previewed operations. The plugin must not silently edit or delete Zotero
records, automate publisher pages, guess full-text URLs, or claim that a paper
was saved without verification.

Each project declares its data authority, formats, lineage, retention,
versioning, and recovery strategy. CSE and Companion do not
prescribe or install a dataset versioning tool.

## GitHub and research-record choices

GitHub issues, Git history, pull requests, remote rules, and current worktrees
are authoritative. A standalone issue is normal. Every open issue belongs to
one milestone through GitHub's native field, under the milestone convention in
[github-and-git](../../plugin/references/workflow/github-and-git.md#milestones),
which Setup reconciles after an approved preview. Labels remain advisory;
Projects, relationships, issue types, and Actions are optional context and are
used only when the science or user chooses them. Substantive
construction records the question, equations or model, assumptions, inputs,
references, reference cases, metrics and tolerances, analyses, outputs, claim
limits, limitations, unresolved questions, and required result checks. A negative
outcome is valid only under
[fix before a negative disposition](../../plugin/references/workflow/failure-triage.md#fix-before-a-negative-disposition).

Before mutation, the route discovers the default branch and remotes, fetches and
prunes, requires a clean canonical checkout, fast-forwards it, and isolates
the feature branch or attached worktree. The endpoint records authority for
commit, push, pull request, merge, remote-head deletion, and local cleanup.
After a merge, only clean, outcome-owned, confirmed-merged branches and
worktrees are removed. The plugin does not create a parallel lifecycle store.

## Science-first decision records and project ownership

CSE-created shared scientific records have one owner: `docs/scientific/`.
Formulation, methods, evidence, writing rules, optional shared LaTeX and Quarto
sources, bibliography, manuscript, and one numbered decision-record sequence
stay there. Each bounded analysis instead owns its retained input snapshot with
provenance, scripts, results, figures, and notebook. New CSE-created
sets default to root `analyses/<short-id>/`; established repositories may keep
a clear repository-owned analysis path and meaningful populated child names.
Setup never creates an empty analysis root or initial notebook; Summarize
creates or replaces the notebook after useful results and before Review.

Decision records are shared doctrine, not a public workflow stage, external
skill dependency, or lifecycle store; the system is not a lifecycle database.
Their four-part threshold and five
science-first kinds preserve only consequential, non-obvious trade-offs. CSE
requires the setting and evidence but leaves acceptance to the repository's
authorized scientific owner. Dependent scientific changes likewise use GitHub
issues, pull requests, Git state, executable checks, and retained results
rather than a controller service or lifecycle database.

## Writing, plotting, and manuscript expectations

Each analysis research notebook is the current view of one coherent question.
Review checks that complete view; the investigator decides whether to promote
its reviewed commit for manuscript use. Git and retained results preserve
history. A manuscript is a selected scientific story, not a replacement for
the notebook.
The [project-record reference](../../plugin/references/workflow/scientific-projects.md) expects
questions and conditions, methods and sources, results, interpretation,
limitations, claim boundaries, and relevant convergence, uncertainty,
sensitivity, alternatives, and negative results.

Plots preserve exact plotted values and, when retained, PDF, PNG, and SVG
outputs. Axes name quantities and units, scales must not conceal behavior, and
models, experiments, literature, and uncertainty are distinguished by meaning
rather than decoration. The manuscript uses the approved Better BibTeX
snapshot and is compiled and inspected after material changes. Scientific prose
is direct, active, specific, and restrained; the repository's style and rule
files govern forbidden language and completeness checks.

## Rejected alternatives and why

| Alternative | Decision and reason |
| --- | --- |
| Keep Project Truss as the runtime foundation | Rejected. The product needs a clean scientific identity and must not inherit generic lifecycle machinery or vocabulary. |
| Invoke Matt Pocock skills or Superpowers at runtime | Rejected. Their useful ideas can inform design history, but CSE must be installable and understandable without those families. |
| Merge Zotero-Wiki into the plugin | Rejected. A replaceable plugin cache must not contain a user's private library or evidence corpus. The capability belongs in an optional, user-owned Zotero Companion boundary. |
| Put the thermophysical data registry inside the plugin | Rejected. A registry is an independent scientific resource. CSE may teach provenance and adapters without owning its data, schema, or migration. |
| Make the agent adjudicate or label scientific claims | Rejected. The agent should calculate, compare, expose uncertainty, and present interpretations; the user owns the scientific judgment. |
| Universal result-status machinery | Rejected as successor baggage. Scientific work needs evidence and interpretation tied to the question, not a generic status taxonomy. |
| Strict question-only stage gates | Rejected. Material alignment questions are required, but the agent should continue through connected routes once the user confirms rather than stopping at every stage. |
| Generic TDD, test pyramids, or coverage targets | Rejected. Tests protect scientific expectations and realistic corruption risks; coverage can reveal gaps but does not establish correctness. |
| Mandatory labels, Projects, Actions, or issue hierarchy | Rejected. These remain optional GitHub context and should not become a hidden lifecycle database. Milestones are the exception: every open issue belongs to one, titled by the shared convention, so hosts can browse issues by milestone; they grant no authority. |
| Hand-edit a BibTeX snapshot or automate publisher access | Rejected. Zotero and the approved Better BibTeX export own metadata and attachments; repository snapshots are one-way and source-linked acquisition stays user-controlled. |
| Prescribe one dataset versioning tool | Rejected. Data authority, formats, lineage, retention, versioning, and recovery are scientific-project decisions. |

## Known limitations

- The plugin remains advisory about scientific correctness and interpretation.
  Optional hooks block on prose violations and report test changes as advisories.
  They cannot prevent transient writes. Hook activation (once at user level,
  or per repository) is separate from plugin enablement and remains subject to
  host-managed hook policy; hooks stay silent outside a CSE repository.
- The domain expert must supply or approve the question, equations, sources,
  conventions, tolerances, intended use, and claims. Missing context can stop
  a route.
- The installed package contains workflow and doctrine, not a universal solver,
  domain database, private PDF corpus, or replacement for a research group.
- Source acquisition depends on user-controlled browser and Zotero actions;
  Companion is separately installed and has its own availability and
  permissions.
- GitHub and Codex app capabilities, private-repository access, repository
  rules, and the local toolchain can vary. Actions and checks are not assumed
  unless the live repository supplies them.
- The current repository has no mature benchmark suite for measuring the
  quality of scientific alignment, independent oracle selection, or reviewer
  agreement across domains.

## Unresolved questions

Plugin-wide questions remain about how to evaluate scientific usefulness across
domains, how Companion behavior should evolve without duplicating Zotero,
which domain packs or registry adapters are worth
maintaining, how much questioning is optimal for different users, and which
review benchmark best detects unsupported claims without turning into a
coverage target. The privacy and permission boundary for future connected
research services also needs continued testing.

The embedded heat-equation example now includes executable FTCS and
Crank–Nicolson methods, retained stability, refinement, convergence, and
uncertainty evidence, and a tutorial manuscript. Those results are not
plugin-wide claims: the example remains limited to code and solution
verification and does not establish physical model validation.

## Heat-equation example boundary

The embedded [heat-equation example](../../examples/heat-equation/README.md)
is the behavioral evidence for the setup route. Its
[scientific context](../../examples/heat-equation/docs/scientific/CONTEXT.md)
define a one-dimensional dimensionless transient heat equation with a single
Fourier-mode reference case. Its [formulation](../../examples/heat-equation/docs/scientific/formulation.tex),
[methods](../../examples/heat-equation/docs/scientific/methods.tex),
and [evidence plan](../../examples/heat-equation/docs/scientific/evidence.tex)
specify:

- \(\partial\theta/\partial Fo=\partial^2\theta/\partial\xi^2\) on
  \(0<\xi<1\), zero Dirichlet boundaries, and initial condition
  \(\sin(\pi\xi)\);
- exact solution \(e^{-\pi^2 Fo}\sin(\pi\xi)\), with dimensionless
  \(\theta\), \(\xi\), and Fourier number \(Fo\);
- FTCS as second-order in space and first-order in time with \(r\le 1/2\);
- Crank–Nicolson as second-order in space and time, linearly stable but not
  unconditionally monotone for large steps; and
- field error, observed order, monotonic refinement, discrete amplification
  factors, and numerical uncertainty as the planned evidence.

The example deliberately excludes material properties, experimental data,
dimensional prediction, physical uncertainty, and model validation. Its
Crank–Nicolson source is now in the generated
[repository bibliography snapshot](../../examples/heat-equation/docs/scientific/latex/references.bib),
which is synchronized from the user's Better BibTeX export by the example's
[one-way helper](../../examples/heat-equation/scripts/sync_bibliography.sh).
