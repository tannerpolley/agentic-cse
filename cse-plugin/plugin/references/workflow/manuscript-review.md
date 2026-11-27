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
section order or argument spine, review the structure before writing. Routine
wording, citation, and formatting edits do not trigger this review.

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
[methods reproducibility](scientific-writing.md#methods-reproducibility),
[equations, quantities, and units](scientific-writing.md#equations-quantities-and-units), and
[data, code, and software](scientific-writing.md#data-code-and-software). The
reader-story reviewer uses `cse:prose` for the [final manuscript checkpoint](#final-manuscript-checkpoint) and checks
figures, tables, [captions](scientific-writing.md#shared-article-requirements),
abstract, paragraph placement, and internal language. Write
applies their fixes as given; science support wins a conflict. Write then makes
one verification read.

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
   Review's [claim verdicts](../../skills/review/SKILL.md#claim-verdicts) with evidence and
   limitations. Route discovery to Research, approved bibliography work to
   Zotero, and prose fixes to Write. Follow the
   [bibliography snapshot protocol](#bibliography-snapshot).

Bind the conclusion to the reviewed revision. Changed claims, citations,
sources, or editorial directions require affected conclusions to be refreshed
at the next final checkpoint; reuse unaffected evidence. This adds no
literature-search gate to routine rendering.

## Final manuscript checkpoint

Routine revisions and builds need only the project's existing structural and
rendering checks: stable unique paragraph identifiers, reconstructable order,
one sentence per source line, blank-line paragraph boundaries, and resolved
references, labels, and citations, read from the final build log by the
[log check](../visualize/latex-layout-and-qa.md#release-sequence) because a
LaTeX build can succeed with them unresolved. These checks do not judge the
argument.

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
