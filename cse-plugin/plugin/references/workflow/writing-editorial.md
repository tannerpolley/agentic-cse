# Editorial procedures

## Project prose authorities

Keep terminology preferences out of the [standing editorial record](#standing-editorial-decisions).
Deterministic project avoid rules live only in the
`## Prose avoid rules` table that `check_prose.py` reads
([scientific project records](scientific-projects.md)). Apply plugin-wide and scoped prose checks, citations, structure, and the
selected document profile when a scientific document is prepared.

## Prose inspection

For file-backed input, Prose runs the [source scan](#reader-facing-identifiers) with the
available project glossary and personal configuration before semantic
inspection. Pasted input without a declared repository-relative path receives
plugin-wide and contextual inspection only; state that path-scoped project and
personal rules were not checked, and create no surrogate file.

Routine Prose findings identify the smallest exact span, classify it as
`required correction` or `contextual judgment call`, cite the rule source, and
explain the scientific or communication consequence. Apply the
[scientific prose principles](scientific-writing.md#scientific-prose).

The patterns in those principles are not evidence of authorship. Prose returns no AI probability,
detector score, or authorship verdict and does not optimize text for a detector.

### Routine corrections

Apply [Fixing a review finding](scientific-writing.md#fixing-a-review-finding),
[revision fidelity](scientific-writing.md#scientific-prose), and
[editorial compliance](#editorial-compliance) within the scope of the diagnosed issue.
After corrections, perform one verification read. Do not iterate toward a style
or detector score.

### Original and revision comparison

When comparing an original with a revision, check [revision fidelity](scientific-writing.md#scientific-prose). Report exact differences and unresolved risks.
This semantic inspection neither proves equivalence nor
decides whether evidence supports a changed scientific claim; route claim
support to Review's Result lens and unresolved source authority to Research.

## Standing editorial decisions

Before manuscript or deck work, discover existing project guidance. Keep one
named section per manuscript or deck in `docs/scientific/writing/STYLE.md`,
identified by repository-relative authoritative source, supplement, and
associated figure paths. Keep project-wide choices outside document sections.
If an established framing brief such as `FRAMING.md` or an editorial record
owns the choices, put its pointer in the STYLE section and read that brief.
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
split. For target-journal requirements identified in the
[venue package](manuscript-review.md#manuscript-structure-review), use the guide
link and access date as authority. For other decisions, record explicit owner
directions and preserve their exact meaning:
decimal places and significant digits differ. Use an authority link when
available; otherwise retain the date and a short exact owner quotation. Do not
promote agent or reviewer suggestions, or choices inferred from the draft,
into owner policy. Routine editorial choices do not broaden the scientific
choice threshold in [decision-records](decision-records.md); `evidence.md`
owns scientific evidence, not editorial preferences. Follow
[manuscript structure review](manuscript-review.md#manuscript-structure-review) for story order.

When the owner gives a standing editorial direction to any stage, the lead
ensures it becomes a STYLE row before it is applied or writing is delegated.
Before editing, Write, Plot, Beamer, and renderers editing document sources or
associated figures load both project-wide choices and the applicable document
record. At Write's Start, report the number of rows in the applicable STYLE
section, including zero.
A later explicit owner correction replaces only the active scoped row with
its new authority; Git retains history. Conflicting or ambiguous directions
need a scoped owner decision, without asking again about settled choices.
Expose any conflict with scientific support, attribution, or required
limitations; editorial preferences cannot remove those obligations. Build-only
invocations read applicable decisions without inventing or rewriting them.

Prose and Review remain read-only: read and check the applicable record and
return missing owner decisions for the authoring task to capture. They do not
edit the record or turn their own advice into owner policy.

## Reader-facing identifiers

Apply the [reader-outside-the-project principle](scientific-writing.md#scientific-prose). A warning is a judgment call, not proof that a scientific label is wrong.

Run `python3 <plugin>/scripts/workflow/check_prose.py --root <project> [--config <personal.toml>] <sources>`,
where `<plugin>` is the directory holding `skills/`, on explicit sources, including
manuscript sources, figure scripts, and deck `.tex`/`.pptx` files. Use the printed
reference for each advisory.
The scan does not expand TeX includes; name supplements and included sources.
The same channel carries two numerical advisories: code-style print forms
([numbers in print](scientific-writing.md#equations-quantities-and-units)) and roundoff-scale
detail ([fitness for purpose](numerical-testing.md#fitness-for-purpose)).
Advisories never change CLI success or block the Stop hook. Existing
terminology failures still do. The hook attributes changed files to the session,
but may miss script-generated outputs; run this explicit scan before delivery.

Only explicit owner approval can exempt an exact run/fit label. In the existing
named STYLE section, use repository-relative paths/globs in both `Sources:` and
Scope, separated by semicolons, and a nonempty Authority. See the
[STYLE approval example](writing-examples.md#example-manuscript).

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

## Editorial compliance

Check applicable standing editorial decisions in ordinary revisions against
the material edited. At the [final checkpoint](manuscript-review.md#final-manuscript-checkpoint),
Prose and Review check the assembled document, including its supplement, figures,
and tables. Report exact violations with the source identifier,
record path, scoped decision and authority, consequence, and smallest
correction. Missing or ambiguous directions return to authoring or the owner;
reviewers do not invent them.

### Project story checkers

When a project keeps a story checker, pin the role of the opening sentence,
the order of the points, and the subject of the final paragraph. Exact
phrases can change while those relationships hold. Test that the checker
fails when a revision breaks the intended story.
