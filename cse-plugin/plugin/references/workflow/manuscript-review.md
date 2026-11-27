# Manuscript review procedures

## Bibliography snapshot

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

## Manuscript structure review

For a new manuscript, rejected draft, new target journal, or material change to
section order or argument spine, review the structure before writing. The
[cumulative growth trigger](#story-spine-read) also applies to routine rounds.

Start from the **venue package**, the target journal's current guide for
authors: its limits and required statements are requirements, and where it is
silent the paper decides. Record those that shape the paper in the document's
[STYLE section](writing-editorial.md#standing-editorial-decisions).

Size the number of independent read-only structure reviewers to the change:
several for a new or rejected manuscript, one for a small journal retarget
without a structural change. Each gets the same brief and a distinct identity
and judges independently. Supply the target journal, owner-named model papers, prior
accepted version, source collection, owner rules, and accepted evidence. Each
reviewer returns a diagnosis tracing the root cause to planning records,
**measured model papers** (the owner-named model paper and a few recent
papers of its type and venue, mapped by headings, where the model sits, and
what the supplement holds, not from memory), a literature plan with existing
citation keys, an outline, a jargon list, and only blocking questions.

The accountable lead checks each proposal: citation keys exist in the
bibliography, linked PDFs exist, quoted numbers are correct, and claims do not
overreach. Merge the strongest supported parts into the task's accepted plan.
Put story order there, not in `STYLE.md`. One writer then rewrites from the plan.

### After the rewrite

Two independent reviewers work in parallel. The science-support
reviewer applies Review's Result lens to every displayed number and cited claim
against retained files and cited sources, providing exact replacement text,
and checks [manuscript reference coverage](#manuscript-reference-coverage),
[comparison reconciliation](#comparison-reconciliation),
[methods reproducibility](scientific-writing.md#methods-reproducibility),
[equations, quantities, and units](scientific-writing.md#equations-quantities-and-units), and
[data, code, and software](scientific-writing.md#data-code-and-software). The
reader-story reviewer uses `cse:prose` for the [final manuscript checkpoint](#final-manuscript-checkpoint) and checks
figures, tables, [captions](scientific-writing.md#shared-article-requirements),
abstract, paragraph placement, and internal language. Write applies supported
corrections, giving science support precedence in a conflict, then makes one
verification read.

## Story-spine read

Across the current round, including accumulated routine edits, read the spine
whenever the abstract, conclusions, a research question, the section order,
a headline claim or its verb, the set of studies, or a dissertation map changes.
Use [structure review](#manuscript-structure-review) when main-text words have
grown by more than about 20 % since the last accepted plan. Use the
[post-rewrite pair](#after-the-rewrite) when a round changes more than about
10 % of the main-text words, even when the overall length stays similar.

In one read, bring together the abstract's opening question and gap, the
Introduction's questions, the Results headings and displays, and the final
paragraph. Match each promised question to its answer, in order, and check that
the conclusions end on the contribution. Apply the [evidence guard](scientific-writing.md#evidence-guard)
to every “each”, “only”, and “confirmed” against the least supportive section
or chapter. Can an outside engineer use the headline deliverable and each
central table from the paper alone?

## Internal referee rounds

Grade a readability-and-proportion row in the referee brief against the
measured model papers and give a word or page budget. In the writer brief,
name the one contribution and which points should appear exactly once.
Give each framing point a single home in the argument.

Each request that adds material names its destination. The lead triages
requests by what the argument needs and routes fixes through
[Fixing a review finding](scientific-writing.md#fixing-a-review-finding).
In the round's report, give the change in main-text words and in the counts
of tables, figures, and captions. Apply the [story-spine triggers](#story-spine-read)
across rounds.

## Comparison reconciliation

For each central comparison, read the quantity and phase, case set, basis,
model and settings, statistic, and population from the caption and table
alone. Use the caption and figure for a plotted comparison. Reconcile those
details with the text and Methods and with companion papers that reuse the
same observations.

## Manuscript reference coverage

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
   argument needs. Flag the exact span if a pointer substitutes for needed
   content or repeated pointers interrupt a complete explanation.
   Use a concise self-contained explanation and one valid pointer for
   derivation or supporting detail.
5. **Decision and remediation:** in existing review output, report source
   identity, record path, exact paragraph/frame/key, evidence or missing
   support, consequence, and smallest correction. Separate required corrections
   from optional broader reading. Demonstrated unsupported claims or missing
   essential content prevent support for the intended final use; a merely
   short or old list does not. Apply the [limit-origin rule](numerical-testing.md#tolerances):
   invent no reference-count, citation-age, or coverage-percentage gate. Use
   Review's [claim verdicts](../../skills/review/SKILL.md#claim-verdicts) with evidence and
   limitations. Route discovery to Research, approved bibliography work to
   Zotero, and prose fixes to Write. Follow the
   [bibliography snapshot protocol](#bibliography-snapshot).

Bind the conclusion to the reviewed revision. Changed claims, citations,
sources, or editorial directions require affected conclusions to be refreshed
at the next final checkpoint; reuse unaffected evidence. This adds no
literature-search gate to routine rendering.

## Final manuscript checkpoint

For routine revisions, apply the [story-spine triggers](#story-spine-read) and
the project's existing structural and rendering checks. Maintain stable unique
paragraph identifiers, reconstructable order, one sentence per source line, and
blank-line paragraph boundaries. Verify references, labels, and citations in the
final build log with the [log check](../visualize/latex-layout-and-qa.md#release-sequence)
because a LaTeX build can succeed with them unresolved.

At this checkpoint, require [editorial compliance](writing-editorial.md#editorial-compliance) and
Review's [reference-coverage result](#manuscript-reference-coverage) for the same
source revision as Prose.

Judge sentence links by the [reader expectations principle](scientific-writing.md#scientific-prose).

Prose performs one agent-led cohesion inspection when the user asks for a final check, before
submission or a named publication handoff. A material change to central claims,
the abstract, conclusion, section order, or argument spine invalidates the
previous final Prose inspection and requires an updated inspection at the next
final checkpoint. Ordinary wording, citation, formatting, and local clarity edits
do not trigger it or block a routine build.

Read the authoritative assembled manuscript, including selected inputs and
appendices. Bind the review to its current source identity and ordered stable
paragraph identifiers; derive sentence identifiers from paragraph order.
Inspect the whole manuscript, and record the exact weak or broken links with
their consequences. A full map in compact judgments, rather than a copy of the
manuscript, is used when it helps diagnose the paper, not required every time:

- Each sentence: short idea label and role in its paragraph.
- Each adjacent sentence pair: clear, weak, or broken; explain non-clear links.
- Each paragraph: theme, purpose within its section, and transition to the
  next paragraph using the same judgments.
- Each section: the part of the scientific argument it establishes and its
  transition to the next section.
- The assembled manuscript: one argument spine against which the abstract,
  body, and conclusion can be compared.

See an [example of a generated review row](writing-examples.md#example-review-row).

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
