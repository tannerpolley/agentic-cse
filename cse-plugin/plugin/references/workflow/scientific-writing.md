# Optional writing records

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
available project glossary and personal configuration before semantic
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

### Manuscript structure review

For a new manuscript, rejected draft, new target journal, or material change to
section order or argument spine, review the structure before writing. Routine
wording, citation, and formatting edits do not trigger this review.

Give three independent read-only structure reviewers the same brief and distinct
identities. One reviewer is enough for a small journal retarget without a
structural change. Supply the target journal, owner-named model papers, prior
accepted version, source collection, owner rules, and accepted evidence. Each
reviewer returns a diagnosis tracing the root cause to planning records, a map
of the model paper, lessons from similar papers, a literature plan with existing
citation keys, an outline, a jargon list, and only blocking questions.

The accountable lead checks each proposal: citation keys exist in the
bibliography, linked PDFs exist, quoted numbers are correct, and claims do not
overreach. Merge the strongest supported parts into the task's accepted plan.
Put story order there, not in `STYLE.md`. One writer then rewrites from the plan.

After the rewrite, two independent reviewers work in parallel. The science-support
reviewer applies Review's Result lens to every displayed number and cited claim
against retained files and cited sources, providing exact replacement text. The
reader-story reviewer applies the final manuscript checkpoint below and checks
figures, tables, abstract, paragraph placement, and internal language. Write
applies their fixes as given; science support wins a conflict. Write then makes
one verification read.

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
