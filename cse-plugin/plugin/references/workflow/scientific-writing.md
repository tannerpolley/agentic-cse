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

Use `docs/scientific/writing/STYLE.md` for project-wide house style and
document-scoped standing editorial decisions, and `RULES.md` for deterministic
project writing rules. Do not duplicate terminology preferences there. Apply plugin-wide and scoped prose checks, citations, structure, and the
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

### Reader-facing identifiers

Use scientific descriptions in prose, captions, table cells, legends, axis
labels, and slides. Internal run/fit codes, issue or pull-request numbers,
commit hashes, and repository paths need reader-facing inspection. A warning
is a judgment call, not proof that a scientific label is wrong.

Run `python3 <plugin>/scripts/workflow/check_prose.py --root <project> <sources>`
on explicit manuscript sources, figure scripts, and deck `.tex`/`.pptx` files.
The scan does not expand TeX includes; name supplements and included sources.
Identifier advisories never change CLI success or block the Stop hook. Existing
terminology failures still do. The hook attributes changed files to the session,
but may miss script-generated outputs; run this explicit scan before delivery.

Only explicit owner approval can exempt an exact run/fit label. In the existing
named STYLE section, use repository-relative paths/globs in both `Sources:` and
Scope, separated by semicolons, and a nonempty Authority:

```markdown
## Example manuscript
Sources: manuscript/*.tex; figures/plot.py
| Scope | Standing owner decision | Authority |
| --- | --- | --- |
| manuscript/*.tex; figures/plot.py | Approved scientific labels: `F2`; `A1` | Dated explicit owner approval, meaning and source |
```

Both Sources and Scope must match. Approval is case-sensitive and exact: F4 does
not approve F4-0. It cannot suppress issue/path/hash findings or terminology
failures. Missing STYLE implies no approvals. Malformed approval rows warn and
suppress nothing. Pointer-only records stay valid; external editorial approval
requires semantic inspection and is not followed or copied automatically.

Extraction is deliberately bounded: TeX uses line-based command stripping and
begin/end tracking; multiline command arguments and arbitrary macros require
assembled-document inspection. Markdown/Quarto keeps visible link text, quoted
prose and simple monospace labels but hides code, math and non-caption metadata.
Python inspects literal text at figure-label calls without executing code or
propagating variables; dynamic expressions and invalid Python produce explicit
incomplete-scan advisories. PowerPoint joins text runs in slide paragraphs and
table cells; malformed archives warn. Images, embedded chart/SmartArt labels,
notes and macro-expanded text require visual inspection. Inspect the assembled
figure/deck even when the source scan is quiet. Executable patterns live only
in the checker; this section owns the editorial rule and approval requirements.

### Standing editorial decisions

Before manuscript or deck work, discover existing project guidance. Keep one
named section per manuscript or deck in `docs/scientific/writing/STYLE.md`,
identified by repository-relative authoritative source, supplement, and
associated figure paths. Keep project-wide choices outside document sections.
If an established manuscript brief or editorial record already owns the
choices, put only its pointer in the STYLE section; do not copy the decisions.
Dated revision reports and the current draft are not automatically standing
owner instructions. Create the section when document work begins; if there
are no standing directions, state that none have been recorded.

Use this minimal format, with actual document paths and owner directions:

```markdown
## Manuscript or deck title
Sources: repository-relative main source; supplement; associated figures
| Scope | Standing owner decision | Authority |
| --- | --- | --- |
```

Rows can cover precision, exclusions, audience, and the main-text/supplement
split. Record only explicit owner directions and preserve their exact meaning:
decimal places and significant digits differ. Use an authority link when
available; otherwise retain the date and a short exact owner quotation. Do not
promote agent or reviewer suggestions, or choices inferred from the draft,
into owner policy. Routine editorial choices do not broaden the scientific
choice threshold in [decision-records](decision-records.md); `evidence.md`
owns scientific evidence, not editorial preferences. Task-specific story order
stays in the accepted issue plan under manuscript structure review.

Before editing, Write, Plot, Beamer, and renderers editing document sources or
associated figures load both project-wide choices and the applicable document
record. Capture new explicit owner directions there before applying them.
A later explicit owner correction replaces only the active scoped row with
its new authority; Git retains history. Conflicting or ambiguous directions
need a scoped owner decision, without asking again about settled choices.
Expose any conflict with scientific support, attribution, or required
limitations; editorial preferences cannot remove those obligations. Build-only
invocations read applicable decisions without inventing or rewriting them.

Prose and Review remain read-only: read and check the applicable record and
return missing owner decisions for the authoring task to capture. They do not
edit the record or turn their own advice into owner policy.

### Editorial compliance

At the final checkpoint, Prose and Review check the applicable standing
editorial decisions against the assembled document, including its supplement,
figures, and tables. Report exact violations with the source identifier,
record path, scoped decision and authority, consequence, and smallest
correction. Missing or ambiguous directions return to authoring or the owner;
reviewers do not invent them.

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
against retained files and cited sources, providing exact replacement text,
and checks [manuscript reference coverage](#manuscript-reference-coverage). The
reader-story reviewer applies the final manuscript checkpoint below and checks
figures, tables, abstract, paragraph placement, and internal language. Write
applies their fixes as given; science support wins a conflict. Write then makes
one verification read.

### Manuscript reference coverage

At a final manuscript check, submission, or named publication handoff, Review
inspects assembled main text, selected supplement/appendices, figure and table
captions, bibliography snapshot, and available build diagnostics at the same
source identity as Prose. For decks, inspect frames, notes, and their sources.
Reuse existing checks; compilation proves neither support nor coverage.

1. **Resolution and support:** identify unresolved citation keys, missing
   bibliography entries, unresolved cross-reference targets, and placeholders
   from source and build evidence. Check source-dependent claims, equations,
   data, methods, and comparisons against the actual cited source and locator.
   A resolved citation with irrelevant support still fails that claim.
2. **Thin coverage:** map central claims and substantive sections to needed
   evidence: foundational method, data provenance, relevant alternatives or
   comparison methods, and claimed novelty or current field position, as
   applicable. Compare with inspected owner-named model papers and
   field-relevant primary literature/reviews for the same subject and intended
   use. Name a missing claim/evidence category and concrete sources or a bounded
   research question. Reference counts alone are never a defect or acceptance
   threshold; similar-paper counts can only orient investigation.
3. **Dated coverage:** inspect whether later relevant primary work changes a
   method, comparison, uncertainty, or current/novelty claim. Search the
   configured corpus/library first; route current literature beyond it to
   Research. Record search date, scope, and inspected source identifiers in the
   review output. Old foundational citations remain valid; use no age cutoff
   or recent-paper percentage. If current literature cannot be checked, report
   the exact limitation and affected conclusion as unverified, never passed.
4. **Bare cross-references:** inspect “see Supplement §…” and “see Part 1”
   semantically. Verify the target exists and that the main manuscript supplies
   the definition, essential method/conditions, result, or interpretation its
   argument needs. Flag the exact span and missing content when a pointer
   substitutes for it. A concise self-contained explanation plus a valid
   pointer for derivation or supporting detail is acceptable; do not ban
   cross-references or require wholesale duplication.
5. **Decision and remediation:** in existing review output, report source
   identity, record path, exact paragraph/frame/key, evidence or missing
   support, consequence, and smallest correction. Separate required corrections
   from optional broader reading. Demonstrated unsupported claims or missing
   essential content prevent support for the intended final use; a merely
   short or old list does not. Apply the [limit-origin rule](numerical-testing.md#tolerances):
   invent no reference-count, citation-age, or coverage-percentage gate. Use
   Review's existing Supported/Not supported outcomes with evidence and
   limitations. Route discovery to Research, approved bibliography work to
   Zotero, and prose fixes to Write. Never manually edit the bibliography
   snapshot or bypass its existing refresh approval.

Bind the conclusion to the reviewed revision. Changed claims, citations,
sources, or editorial directions require affected conclusions to be refreshed
at the next final checkpoint; reuse unaffected evidence. This adds no
literature-search gate to routine rendering.

### Final manuscript checkpoint

Routine revisions and builds need only the project's existing structural and
rendering checks: stable unique paragraph identifiers, reconstructable order,
one sentence per source line, blank-line paragraph boundaries, and resolved
references, labels, and citations. These checks do not judge the argument.

At this checkpoint, require [editorial compliance](#editorial-compliance) and
Review's [reference-coverage result](#manuscript-reference-coverage) for the
same source revision as Prose.

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
