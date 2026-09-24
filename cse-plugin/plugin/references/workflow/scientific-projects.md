# Scientific project records

Use `docs/scientific/CONTEXT.md` as the short scientific map and
repository-specific terminology authority. It owns one investigator-confirmed
`repository role: analysis` or `repository role: tool`; Setup recommends a role
from purpose and owners and confirms it on every run. Record confirmed personal
preferences in `~/.config/cse/config.toml` only after preview and approval.
Both terminology sources use Avoid, Prefer, Meaning, Scope, Exceptions, and
Evidence. Scope values are repository-relative POSIX globs. When personal and
repository rules overlap for the same avoided phrase, ask the user which owner
to retain or how to split the scopes; never choose precedence silently.

The personal file uses TOML array-of-tables entries:

```toml
[[terminology]]
Avoid = "contact"
Prefer = "stages"
Meaning = "Use equilibrium stages for the modeled extraction sequence."
Scope = ["analyses/**/*.qmd"]
Exceptions = ["MSContactor", "contact mechanics"]
Evidence = "confirmed user correction and task locator"
```

The repository context table uses the same six headings. Separate multiple
scopes or exceptions with semicolons. Matching is case-insensitive and
phrase-bounded. An exception suppresses only the matching occurrence inside
that exact exception phrase. Every field except Exceptions is required. A
malformed entry or overlapping authority is a configuration error with both
source locators, not a silent fallback.

Run the existing `scripts/workflow/check_prose.py` with `--config` and `--context`
for the available authorities and the files being reviewed. The checker
reports Avoid → Prefer with the rule locator; semantic review still decides
whether wording that depends on the scientific question is scientifically correct.

The shared CSE-created record owner is `docs/scientific/`. Setup always creates
only `README.md` and `CONTEXT.md`. Optional formulation, methods, evidence,
decisions, and writing records are Markdown. Manuscript sources and their
bibliography stay below `docs/scientific/latex/` when writing is enabled;
LaTeX is never used for a scientific record. Temporary source synthesis may
use the ignored `docs/scientific/.research/` path.

For an analysis role, emphasize data and source authority, retained analyses,
results, figures or notebooks, uncertainty, and validation. For a tool role,
emphasize equation and implementation owners, interfaces, failure behavior,
reference cases, tolerances, and numerical verification. Fill the core with the repository's real scientific question, owners, and
paths; do not copy generic ADR starters or write blank headings or placeholder
files. Source code, canonical
reusable data, and main model files remain in their natural repository owners.
Do not turn an analysis-only repository into a package or require package and
environment policy as part of CSE setup.

## Analysis sets and the root Quarto analysis site

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
conclusions, limitations, next steps, and exact retained paths. A diagnosed
negative result need not invent a table or figure.

A central numerical relationship or comparison backed by retained row-level
values has one claim-led figure that directly answers the scientific question.
This applies to model-versus-observation comparisons, competing methods or
formulations, parameter or sensitivity sweeps, trajectories, refinement or
convergence, and uncertainty distributions. The retained CSV owns the exact
values; a compact table may support the figure but neither a CSV link nor a
table replaces it. A table-only result is appropriate for a few scalar or
categorical values, an exact lookup, or a diagnosed negative result when the
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

## Migration

During Setup in an established repository, detect every competing CSE-created
record owner, including `docs/`, `docs/latex/`, alternate decision-record
directories, central notebooks, superseded analysis metadata, generated
reports, and repository-native equivalents. Preview the exact source-to-target
moves, caller and link updates, retained inputs and outputs, and displaced
owners to remove. Obtain approval before mutation. Use `git mv` where practical
to preserve history, update every real caller and link, verify the destination,
render selected documents, and remove displaced owners in the same change.
Leave no alias, duplicate, or redirect and never retain two accepted decision
record or notebook locations.

## Optional writing records

When writing is selected, the committed bibliography snapshot lives under
`docs/scientific/latex/references.bib`. Refresh it only through the approved
`cse:zotero` route when CSE source and Zotero Companion are available.
Synchronize cited project records one way, omit local attachment paths, and
never edit the snapshot by hand.

If Companion is unavailable, a committed bibliography snapshot remains a
read-only reproducibility input for already approved sources. Report that no
refresh occurred. Stop for new or changed source metadata until the authority
is available.

Manuscript sources live under `docs/scientific/latex/` and resolve the project
bibliography snapshot by a portable relative path.

### Scientific prose

Use `docs/scientific/writing/STYLE.md` for house style and `RULES.md` for
deterministic project writing rules. Do not duplicate terminology preferences
there. Apply plugin-wide and scoped prose checks, citations, structure, and the
selected document profile when a notebook or manuscript is prepared.
Write direct, active, specific prose and preserve scientific meaning,
uncertainty, provenance, and limitations.

`cse:prose` owns writing inspection; `cse:write` owns authoring and correction.
For file-backed input, Prose runs `scripts/workflow/check_prose.py` with the
available repository context and personal configuration before semantic
inspection. Pasted input without a declared repository-relative path receives
plugin-wide and contextual inspection only; state that path-scoped project and
personal rules were not checked, and create no surrogate file.

Routine Prose findings identify the smallest exact span, classify it as
`required correction` or `contextual judgment call`, cite the rule source, and
explain the scientific or communication consequence. If no finding remains,
return `CSE prose is clear.` without rewriting. Inspect writing for:

- formulaic openers, canned transitions, repeated connective scaffolding,
  false binary contrasts, dramatic fragments, rhetorical setups, and padded
  repeated structures;
- unsourced vague attribution, unsupported significance or novelty, empty
  participial tails, vague declarations, business language, chatbot residue,
  meta-commentary, and internal repository or workflow language;
- synonym cycling or terminology drift for one scientific referent;
- wording or citation scope inconsistent with an accepted claim boundary,
  tested domain, uncertainty statement, limitation, or causal description; and
- over-editing that invents first person, stakes, specifics, mechanisms,
  contrarian framing, or staccato prose.

These patterns are not evidence of authorship. Prose returns no AI probability,
detector score, or authorship verdict and does not optimize text for a detector.
It preserves evidence-calibrated hedging; passive voice when the actor is
irrelevant; field-appropriate first-person plural; exact technical terms;
definitions, equations, symbols, methods, metrics, citations, source titles,
and genuine domain terms; and occasional semicolons, long sentences, or
three-item lists that carry real logic. Author voice comes from supplied prior
writing, and venue calibration requires supplied requirements or inspected
examples.

When comparing an original with a revision, Prose checks numbers, signs,
percentages, ranges, counts, units, equations, statistics, citations, citation
scope, labels, cross-references, quotations, code, URLs, paths, figure and table
identity, and technical terminology. It also checks each value's subject,
variable, group, denominator, condition, and comparison; effect direction and
magnitude; negation, modality, aggregation, scope, uncertainty, causality,
limitations, and exceptions; and whether an author or reviewer action is
proposed, planned, completed, declined, or unresolved. Report exact differences
and unresolved risks. This semantic inspection neither proves equivalence nor
decides whether evidence supports a changed scientific claim; route claim
support to Review's Result lens and unresolved source authority to Research.

When correction is requested, Write changes only diagnosed spans, leaves clear
prose unchanged, invents no specificity or evidence, preserves supported
content, and performs one verification read. Do not iterate toward a style or
detector score.

### Final manuscript checkpoint

Routine revisions and builds need only the project's existing structural and
rendering checks: stable unique paragraph identifiers, reconstructable order,
one sentence per source line, blank-line paragraph boundaries, and resolved
references, labels, and citations. These checks do not judge the argument.

Prose performs one agent-led cohesion inspection when the user asks for a final check, before
submission or a named publication handoff. A material change to central claims,
the abstract, conclusion, section order, or argument spine invalidates the
previous final Prose inspection and requires an updated inspection at the next
final checkpoint. Ordinary wording, citation, formatting, and local clarity edits
do not trigger it or block a routine build.

Read the authoritative assembled manuscript, including selected inputs and
appendices. Bind the review to its current source identity and ordered stable
paragraph identifiers; derive sentence identifiers from paragraph order.
Record compact judgments rather than copying the manuscript:

- Each sentence: short idea label and role in its paragraph.
- Each adjacent sentence pair: clear, weak, or broken; explain non-clear links.
- Each paragraph: theme, purpose within its section, and transition to the
  next paragraph using the same judgments.
- Each section: the part of the scientific argument it establishes and its
  transition to the next section.
- The assembled manuscript: one argument spine against which the abstract,
  body, and conclusion can be compared.

Example of a generated review row, not additional manuscript source:

| Source identifier | Idea | Role | Transition to next | Explanation |
|---|---|---|---|---|
| introduction-05.s2 | finite extractant inventory | explains coupling | weak | State how inventory couples the two partition calculations. |

Keep these summaries under the project's existing build or review-output path.
A small repository-local checker may verify source identity, order, identifier
coverage, allowed judgment values, and unresolved items at the final checkpoint.
It must never assign ideas, themes, relationships, or a coherence judgment from
keywords, length, or other mechanical proxies. CSE supplies no universal LaTeX
parser or second manuscript edition.

Return **Revise** with exact identifiers when the inspection is stale, omits current
coverage, or leaves weak or broken relationships unresolved. Routine building
remains available. A second independent Prose inspection is needed only under the existing
scientific risk rules or for disputed weak or broken relationships, not for
every final prose check. Cohesion inspection does not establish scientific truth
or replace evidence review and investigator promotion.
