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
uncertainty, provenance, and limitations. Practice **calibrated hedging**
(Hyland 1996; IEEE Author Center): state a supported finding plainly with its
conditions and uncertainty, and hedge only what the evidence leaves open.
Over-qualifying misreports the evidence as surely as inflating it.

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

Write for **a reader outside the project** (Mensh and Kording 2017, Rule 2): a
term, label, or piece of history a new reader would need explained is defined
or removed. Use scientific descriptions in prose, captions, table cells,
legends, axis labels, and slides. Internal run/fit codes, issue or pull-
request numbers, commit hashes, and repository paths need reader-facing
inspection. A warning is a judgment call, not proof that a scientific label is
wrong.

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
split. A row may also record a target-journal requirement that shapes the
paper (see [venue package](#manuscript-structure-review)), with the guide link
and access date as authority. Otherwise record only explicit owner directions
and preserve their exact meaning:
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

### Argument

These conventions describe how established papers are built; section order
and skeletons live in the [manuscript profile](../visualize/latex-article-profiles.md#manuscript-profile).
A venue requirement or standing editorial decision overrides a convention, and
a paper departs from one when its argument needs it.

- **Rule of One** (Mensh and Kording 2017, Rule 1): a paper argues one central
  contribution, and the title carries it.
- **Outline from the displays** (Whitesides 2004): plan the equations, figures,
  and tables first, ordered by importance rather than by the order the work
  was done, then write the text that explains them.
- **Findings first** (Mensh and Kording 2017, Rule 7): results are a chain of
  supported claims, not the path taken. A results paragraph poses its question
  and ends with the answer.
- **Text density** (ACS Guide 2.1.3): an effective article avoids dense text.
  Paragraphs stay short, and tables, equations, and graphics carry part of
  the load.
- **Every display earns a place in the text** (ACS Guide 4.1.2, 4.2.3): a
  figure or table is cited and discussed in the text, in order of first
  mention. One with no natural place to be discussed does not belong.
- **An archival finding, not design data** (Andrews 2011; Zimmermann et al.
  2020): a paper earns its place by a finding and its consequence. Values
  reported without interpretation read as an engineering report.

### Methods reproducibility

**Methods reproducibility** (Goodman, Fanelli, and Ioannidis 2016) is giving
enough detail about the procedures and the data that the same calculation
could be exactly repeated with the same data and tools. The paper's share is
the mathematics: a reader can check the reported numbers and rework the
derivations from what is printed, and the software is named with its version
(ACS Guide 2.3.8). The data and code are the deposit's share. In a model-based
paper the Methods deliver the paper's share through the model formulation: the
governing relations in the order the calculation uses them, from the inputs to
the reported results, including any fit objective and optimization problem.
Write each relation as a compact displayed equation
rather than describing it in prose. As in a degrees-of-freedom analysis, say
which quantities each model is given and which it computes, especially where
one model feeds another. Printed equations match what the code computes, with
consistent units and one meaning per symbol.

- **Standard tool or contribution:** print what is new or chosen in this work
  and cite standard expressions at their source. A common model needs its
  name, form, and citation; a model that is the paper's contribution is
  formulated in full with every parameter printed.
- **Good reporting practice for property models** (Bazyleva et al. 2021, IUPAC):
  every parameter with its units, origin, and fitted range, plus check values
  computed from the printed parameters.
- **The fit is part of the formulation** (Anderson, Abrams, and Grens 1978;
  Thol et al. 2019): objective, residuals, and weights, and every data set used,
  withheld, or excluded, with the same exclusions for every model compared.
- **Problem statement in standard form** (Biegler 2010): an optimization or
  design study states its given data, decisions, objective, and constraints
  once, with size and solver, and says whether the optimum is local or global.
- **Numerical accuracy** (Journal of Fluids Engineering numerical-accuracy
  policy; Celik et al. 2008; Andrews 2011): state the solver, tolerances, and
  stopping criteria, and show the reported quantity is insensitive to
  refinement. Name the property method, unit models, and correlations a
  simulator used, and show the conditions lie within their validity ranges.
- **Paper and deposit carry different halves** (Buckheit and Donoho 1995;
  National Academies 2019): the paper carries the argument and formulation, the
  deposit regenerates every number, and neither substitutes for the other.
  For a model, the deposit holds the software and version, the configuration
  and parameters, the inputs and outputs, and the numbers behind every figure
  and table as open text files (ACS Guide 3.1.5). A claim names the standard
  met instead of the bare word "reproducible".

Choose each display by [its job](../visualize/latex-article-profiles.md#shared-article-requirements).
Trimming moves derivations, term-by-term expansions, and long tables to the
supplement, never the formulation itself. A referee request for reconstruction
or a worked example often means a step is missing from the text, separate from
any data or code availability.

#### Example: heater operating cost

For a steady single-phase electric heater with specified inlet and outlet
temperatures $T_{\mathrm{in}}$ and $T_{\mathrm{out}}$ (K), the property model
uses constant specific heat capacity $c_p$ (kJ/(kg K)).

$$
\Delta h = c_p(T_{\mathrm{out}}-T_{\mathrm{in}}).
$$

The enthalpy rise $\Delta h$ (kJ/kg) is the **property-model output** and a
**heater input** alongside mass flow $\dot m$ (kg/s). The heater outputs the
thermal duty $\dot Q$ (kW).

$$
\dot Q = \dot m\,\Delta h.
$$

With electrical-to-thermal efficiency $\eta$ (dimensionless) and electricity
price $p_e$ (currency/kWh), the reported operating cost rate $\dot C$ is in
currency/h.

$$
\dot C = p_e\,\dot Q/\eta.
$$

### Equations, quantities, and units

- **Mathematics is prose** (Mermin 1989; Knuth, Larrabee, and Roberts 1989):
  a displayed equation is read as part of its sentence, numbered in order of
  first appearance, and cited by phrase as well as number. End punctuation on
  the equation line follows the venue: some styles require it (Mermin 1989)
  and others forbid it (ACS Guide 5.4.2).
- **Symbols in equations, words in prose** (ACS Guide 5.4.2): equations use
  single-letter symbols with subscripts, and multi-letter abbreviations stay
  in the prose. A definition after an equation uses words: "where $T$ is
  temperature", not "$T$ = temperature".
- **Numbers in print, not in code** (ACS Guide 5.4.1, 5.4.2): a manuscript
  writes $2.4 \times 10^{-3}$, not 2.4e-3; a multiplication sign, not an
  asterisk; 8000, not 8k. Printed digits claim precision: 25.0 °C is not 25 °C.
- **One notation for one thing** (Halmos 1970): one meaning per symbol across
  main text and supplement, defined at first use.
- **Quantity calculus** (BIPM SI Brochure 2019; NIST SP 811; IUPAC Green
  Book): a physical quantity is a number times a unit, so physical laws hold
  in any units. An empirical correlation states the unit of every variable,
  inside the equation as in $\ln(p/\mathrm{kPa})$ or in the definitions right
  after it, whichever the venue uses. Attaching a qualifier to the quantity
  rather than the unit is the SI and IUPAC convention; it yields to venues
  that accept forms such as "10 wt %".
- **Uncertainty statements** (JCGM GUM 2008; NIST TN 1297): standard or
  expanded with its coverage factor, sources justified. Digits follow the
  uncertainty, with extra digits only for parameters a reader must reproduce.

### Data, code, and software

- **Disclose, share, cite** (TOP Guidelines; FAIR 2016; FAIR4RS 2022): the
  availability statement names the archived version that produced the numbers,
  preferably with a persistent identifier, or says why the data cannot be
  shared. Release versions, and a public repository link where the venue asks
  for one, belong there; working paths, branches, issue numbers, and commit
  hashes stay out ([reader-facing identifiers](#reader-facing-identifiers)).
- **Software citation** (Smith, Katz, and Niemeyer 2016): software that shaped
  a result, including scripts, models, and notebooks, is cited in the reference
  list with its version and identifier. Cite the software itself, and its
  paper as well, never the paper in its place.
- **AI disclosure belongs to the authors:** venues forbid AI authorship and
  require disclosure. An agent records what it drafted and leaves the
  declaration for the authors to confirm.
- **Every reference is real** (Elsevier generative-AI policy): each reference
  is checked to exist before submission, because generated references can be
  fabricated. AI-made figures are disclosed in their captions.

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

Start from the **venue package**, the target journal's current guide for
authors: its limits and required statements are requirements, and where it is
silent the paper decides. Record those that shape the paper in the document's
[STYLE section](#standing-editorial-decisions).

Give three independent read-only structure reviewers the same brief and distinct
identities. One reviewer is enough for a small journal retarget without a
structural change. Supply the target journal, owner-named model papers, prior
accepted version, source collection, owner rules, and accepted evidence. Each
reviewer returns a diagnosis tracing the root cause to planning records,
**measured model papers** (the owner-named model paper and two or three recent
papers of its type and venue, mapped by headings, where the model sits, and
what the supplement holds, not from memory), a literature plan with existing
citation keys, an outline, a jargon list, and only blocking questions.

The accountable lead checks each proposal: citation keys exist in the
bibliography, linked PDFs exist, quoted numbers are correct, and claims do not
overreach. Merge the strongest supported parts into the task's accepted plan.
Put story order there, not in `STYLE.md`. One writer then rewrites from the plan.

After the rewrite, two independent reviewers work in parallel. The science-support
reviewer applies Review's Result lens to every displayed number and cited claim
against retained files and cited sources, providing exact replacement text,
and checks [manuscript reference coverage](#manuscript-reference-coverage) and
[methods reproducibility](#methods-reproducibility). The
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
   Review's [claim verdicts](../../skills/review/SKILL.md#claim-verdicts) with evidence and
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
Review's [reference-coverage result](#manuscript-reference-coverage) for the same
source revision as Prose.

Judge sentence links by **reader expectations** (Gopen and Swan 1990), as
principles rather than rules: old information opens a sentence and new,
emphasized information closes it.

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

### Revision responses and cover letters

A response to referees follows **answer, then show** (Noble 2017): quote each
comment, answer it directly, quote the changed text, and say what changed. A
cover letter gives the editor a short summary, not a copy of the abstract: why
this journal, what is new, and what the editor needs to route the paper (ACS
Guide 2.4.4).

### Sources

Principles in the CSE writing references cite these works by author and year.

- American Chemical Society. *ACS Guide to Scholarly Communication.* Cited by section number. doi:10.1021/acsguide
- Anderson, T. F.; Abrams, D. S.; Grens, E. A. Evaluation of parameters for nonlinear thermodynamic models. *AIChE J.* 1978, 24, 20. doi:10.1002/aic.690240103
- Andrews, M. J. Guidelines for use of commercial software and diagnostics in articles for JFE. *J. Fluids Eng.* 2011, 133, 010201.
- Barker, M. et al. Introducing the FAIR principles for research software (FAIR4RS). *Sci. Data* 2022, 9, 622. doi:10.1038/s41597-022-01710-x
- Bazyleva, A. et al. Good reporting practice for thermophysical and thermochemical property measurements (IUPAC Technical Report). *Pure Appl. Chem.* 2021. doi:10.1515/pac-2020-0403
- Biegler, L. T. *Nonlinear Programming: Concepts, Algorithms, and Applications to Chemical Processes.* SIAM, 2010.
- BIPM. *The International System of Units (SI Brochure)*, 9th ed., 2019.
- Buckheit, J. B.; Donoho, D. L. WaveLab and reproducible research. In *Wavelets and Statistics*, Springer, 1995. doi:10.1007/978-1-4612-2544-7_5
- Celik, I. B. et al. Procedure for estimation and reporting of uncertainty due to discretization in CFD applications. *J. Fluids Eng.* 2008, 130, 078001.
- Cohen, E. R. et al. *Quantities, Units and Symbols in Physical Chemistry* (IUPAC Green Book), 3rd ed., 2007.
- Crameri, F.; Shephard, G. E.; Heron, P. J. The misuse of colour in science communication. *Nat. Commun.* 2020, 11, 5444. doi:10.1038/s41467-020-19160-7
- Cummings, P. T. et al. Joint statement of editors of journals publishing thermophysical property data. *Fluid Phase Equilib.* 2009, 276, 165.
- Ehrenberg, A. S. C. Rudiments of numeracy. *J. R. Stat. Soc. A* 1977, 140, 277.
- Elsevier. Generative AI policies for journals, as stated in its guides for authors.
- Gastel, B.; Day, R. A. *How to Write and Publish a Scientific Paper*, 9th ed. Cambridge University Press, 2022.
- Goodman, S. N.; Fanelli, D.; Ioannidis, J. P. A. What does research reproducibility mean? *Sci. Transl. Med.* 2016, 8, 341ps12. doi:10.1126/scitranslmed.aaf5027
- Gopen, G. D.; Swan, J. A. The science of scientific writing. *Am. Sci.* 1990, 78, 550.
- Halmos, P. R. How to write mathematics. *Enseign. Math.* 1970, 16, 123.
- Hyland, K. Writing without conviction? Hedging in science research articles. *Appl. Linguist.* 1996, 17, 433. doi:10.1093/applin/17.4.433
- IEEE Author Center. Structure your article.
- JCGM 100:2008. *Evaluation of Measurement Data: Guide to the Expression of Uncertainty in Measurement* (GUM). doi:10.59161/JCGM100-2008E
- Journal of Fluids Engineering. Editorial policy statement on the control of numerical accuracy (1986; revised 1993).
- Journal of Open Source Software. Review criteria.
- Knuth, D. E.; Larrabee, T.; Roberts, P. M. *Mathematical Writing.* MAA Notes 14, 1989.
- Kontogeorgis, G. M. et al. Industrial requirements for thermodynamic and transport properties: 2020. *Ind. Eng. Chem. Res.* 2021, 60, 4987. doi:10.1021/acs.iecr.0c05356
- Mathias, P. M. Guidelines for the analysis of vapor–liquid equilibrium data. *J. Chem. Eng. Data* 2017, 62, 2231. doi:10.1021/acs.jced.7b00582
- Mensh, B.; Kording, K. Ten simple rules for structuring papers. *PLoS Comput. Biol.* 2017, 13, e1005619. doi:10.1371/journal.pcbi.1005619
- Mermin, N. D. What's wrong with these equations? *Phys. Today* 1989, 42(10), 9.
- National Academies of Sciences, Engineering, and Medicine. *Reproducibility and Replicability in Science.* 2019. doi:10.17226/25303
- NETL. *Cost Estimation Methodology for NETL Assessments of Power Plant Performance* (QGESS), NETL-PUB-22580, 2021.
- Noble, W. S. Ten simple rules for writing a response to reviewers. *PLoS Comput. Biol.* 2017, 13, e1005730. doi:10.1371/journal.pcbi.1005730
- Oberkampf, W. L.; Trucano, T. G. *Verification and Validation in Computational Fluid Dynamics.* SAND2002-0529, 2002. doi:10.2172/793406
- Raue, A. et al. Structural and practical identifiability analysis of partially observed dynamical models by exploiting the profile likelihood. *Bioinformatics* 2009, 25, 1923. doi:10.1093/bioinformatics/btp358
- Rubin, E. S. et al. A proposed methodology for CO2 capture and storage cost estimates. *Int. J. Greenh. Gas Control* 2013, 17, 488. doi:10.1016/j.ijggc.2013.06.004
- Saltelli, A. et al. Why so many published sensitivity analyses are false. *Environ. Model. Softw.* 2019, 114, 29. doi:10.1016/j.envsoft.2019.01.012
- Smith, A. M.; Katz, D. S.; Niemeyer, K. E. Software citation principles. *PeerJ Comput. Sci.* 2016, 2, e86. doi:10.7717/peerj-cs.86
- Sollaci, L. B.; Pereira, M. G. The introduction, methods, results, and discussion (IMRAD) structure: a fifty-year survey. *J. Med. Libr. Assoc.* 2004, 92, 364.
- Swales, J. M. *Genre Analysis: English in Academic and Research Settings.* Cambridge University Press, 1990.
- Taylor, B. N.; Kuyatt, C. E. *Guidelines for Evaluating and Expressing the Uncertainty of NIST Measurement Results.* NIST TN 1297, 1994. doi:10.6028/NIST.TN.1297
- Thol, M. et al. EOS-LNG: a fundamental equation of state for the calculation of thermodynamic properties of liquefied natural gases. *J. Phys. Chem. Ref. Data* 2019, 48, 033102. doi:10.1063/1.5093800
- Thompson, A.; Taylor, B. N. *Guide for the Use of the International System of Units (SI).* NIST SP 811, 2008.
- TOP Guidelines (Transparency and Openness Promotion), Center for Open Science, 2025 update.
- Whitesides, G. M. Whitesides' group: writing a paper. *Adv. Mater.* 2004, 16, 1375. doi:10.1002/adma.200400767
- Wilkinson, M. D. et al. The FAIR guiding principles for scientific data management and stewardship. *Sci. Data* 2016, 3, 160018. doi:10.1038/sdata.2016.18
- Zimmermann, A. W. et al. Techno-economic assessment guidelines for CO2 utilization. *Front. Energy Res.* 2020, 8, 5. doi:10.3389/fenrg.2020.00005
