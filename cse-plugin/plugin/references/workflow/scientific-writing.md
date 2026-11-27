# Scientific writing

These conventions describe how established papers are built. A venue requirement or [standing editorial decision](writing-editorial.md#standing-editorial-decisions) overrides a convention,
and a paper departs from one when its argument needs it. See the [sources](writing-sources.md#sources)
and apply [fitness for purpose](numerical-testing.md#fitness-for-purpose).

## Argument

- **Rule of One** (Mensh and Kording 2017, Rule 1): a paper argues one central contribution, and the title
  names it without numerical results.
- **Outline from the displays** (Whitesides 2004): plan the equations, figures, and tables first, ordered by
  importance, then write the text that explains them.
- **Findings first** (Mensh and Kording 2017, Rule 7): results are a chain of supported claims, not the path taken. Apply the paragraph structure below.
- **A conditions table and a result plot** (ACS Guide 2.1.3, 4.1, 4.2): give every study that runs inputs to
  outputs a conditions table and a result plot. Put inputs on x and outputs on y in an X–Y plot. The results
  paragraph poses the question, points to the displays, and ends with the finding and only the numbers the claim
  rests on. Use [fitness for purpose](numerical-testing.md#fitness-for-purpose) to decide which values belong
  in the paper. Honor page limits set by the venue and meet them by cutting words while keeping the displays.
- **Every display earns a place in the text** (ACS Guide 4.1.2, 4.2.3): a figure or table is cited in order of
  first mention. Its discussion tells the reader what to look for and how it supports the finding.
- **An archival finding, not design data** (Andrews 2011; Zimmermann et al. 2020): a paper earns its place by
  a finding and its consequence. Values reported without interpretation read as an engineering report.

## Methods reproducibility

**Methods reproducibility** (Goodman, Fanelli, and Ioannidis 2016) is giving enough detail about the
procedures and the data that the same calculation could be exactly repeated with the same data and tools. Readers
can check the reported numbers and rework the derivations from the printed mathematics. Name the software and
version (ACS Guide 2.3.8). Give governing relations as compact displayed equations in calculation order, from
inputs to results, including any fit objective and optimization problem. As in a degrees-of-freedom analysis,
state each model's inputs and outputs, including handoffs. Printed equations match the code, with consistent
units and [notation](#equations-quantities-and-units).

- **Standard tool or contribution:** print what is new or chosen in this work and cite standard expressions at
  their source. A common model needs its name, form, and citation; a model that is the paper's contribution is
  formulated in full with every parameter printed.
- **Good reporting practice for property models** (Bazyleva et al. 2021, IUPAC): every parameter with its
  units, origin, and fitted range, plus check values computed from the printed parameters.
- **The fit is part of the formulation** (Anderson, Abrams, and Grens 1978; Thol et al. 2019): objective,
  residuals, and weights, and every data set used, withheld, or excluded, with the same exclusions for every
  model compared.
- **Problem statement in standard form** (Biegler 2010): an optimization or design study states its given
  data, decisions, objective, and constraints once, with size and solver, and says whether the optimum is
  local or global.
- **Numerical accuracy** (Journal of Fluids Engineering numerical-accuracy policy; Celik et al. 2008; Andrews
  2011): give accuracy evidence suited to the reported quantity, a prediction stable under refinement or, when
  the error itself is the result, its measured convergence. In proportion, as comparable papers do: the main
  text names the solver, its stopping tolerance where the algorithm has one, and the stability method, and
  says in one sentence how convergence was checked. Residuals, certificates, and checks of identities that
  hold by derivation go to the supplement or deposit only when a reader needs them ([fitness for
  purpose](numerical-testing.md#fitness-for-purpose)). Name the property method, unit models, and correlations
  a simulator used, and show the conditions lie within their validity ranges.
- **Paper and deposit carry different halves** (Buckheit and Donoho 1995; National Academies 2019): the paper
  carries the argument and formulation, the deposit regenerates every number, and neither substitutes for the
  other. For a model, the deposit holds the software and version, the configuration and parameters, the inputs
  and outputs, and the numbers behind every figure and table as open text files (ACS Guide 3.1.5). A claim
  names the standard met instead of the bare word "reproducible".
- Identify every transferred parameter, analogue, correlation, or property value by name, source, exact
  locator, and applicability; state when transfer to the present system is an assumption.
- Define every objective, constraint, operating domain, and comparison method before its result or sensitivity
  appears.
- Give the rationale for fixed sensitivity cases, selected designs, reference conditions, and reported optima
  when the choice is not self-evident. Keep **sensitivity versus uncertainty** distinct (Saltelli et al.
  2019): one-at-a-time variation shows local leverage, not overall uncertainty, in a nonlinear model.
- Give every cost its **cost basis** (NETL 2021; Rubin et al. 2013): currency and year, estimate class,
  capital-cost level, real or nominal financing, scope, and reference plant. Set the **boundary before the
  metric**: define scope and battery limits first and match the metric to them (Rubin et al. 2013).
- State phase-volume, composition-basis, standard-state, sign, unit, and normalization conventions instead of
  saying only that source conventions were retained.
- Identify the operating conditions associated with large errors, failed checks, rejected states, and
  non-evaluable cases when they constrain interpretation.

A referee request for reconstruction or a worked example often points to a missing step in the text, even
when the data and code are available. See the [heater operating-cost example](writing-examples.md#example-heater-operating-cost).

## Equations, quantities, and units

- **Mathematics is prose** (Mermin 1989; Knuth, Larrabee, and Roberts 1989): a displayed equation is read as
  part of its sentence, numbered in order of first appearance, and cited by phrase as well as number. End
  punctuation on the equation line follows the venue: some styles require it (Mermin 1989) and others forbid
  it (ACS Guide 5.4.2).
- **Symbols in equations, words in prose** (ACS Guide 5.4.2): equations prefer single-letter symbols with
  subscripts, and multi-letter abbreviations mostly stay in the prose. A definition after an equation uses
  words: "where $T$ is temperature", not "$T$ = temperature".
- **Numbers in print, not in code** (ACS Guide 5.4.1, 5.4.2): a manuscript writes $2.4 \times 10^{-3}$, not
  `2.4e-3`; a multiplication sign, not an asterisk; 8000, not `8k`. In LaTeX the form is `\num{2.4e-3}`, which
  typesets the printed form ([no manual unit typography](../visualize/latex-packages.md#selected-defaults)).
  Printed digits claim precision: 25.0 °C is not 25 °C.
- **One notation for one thing** (Halmos 1970): one meaning per symbol across main text and supplement,
  defined at first use.
- **Quantity calculus** (BIPM SI Brochure 2019; NIST SP 811; IUPAC Green Book): a physical quantity is a
  number times a unit, so physical laws hold in any units. An empirical correlation states the unit of every
  variable, inside the equation as in $\ln(p/\mathrm{kPa})$ or in the definitions right after it, whichever
  the venue uses. Attaching a qualifier to the quantity rather than the unit is the SI and IUPAC convention;
  it yields to venues that accept forms such as "10 wt %".
- **Uncertainty statements** (JCGM GUM 2008; NIST TN 1297): a measurement uncertainty is standard or expanded
  with its coverage factor, sources justified. A numerical error estimate is described by its construction,
  assumptions, and scope. Digits follow the uncertainty, with extra digits only for parameters a reader must
  reproduce.

## Data, code, and software

- **Disclose, share, cite** (TOP Guidelines; FAIR 2016; FAIR4RS 2022): the availability statement names the
  archived version that produced the numbers, preferably with a persistent identifier, or says why the data
  cannot be shared. Release versions, and a public repository link where the venue asks for one, belong there;
  working paths, branches, issue numbers, and commit hashes stay out ([reader-facing
  identifiers](writing-editorial.md#reader-facing-identifiers)).
- **Software citation** (Smith, Katz, and Niemeyer 2016): software that shaped a result, including scripts,
  models, and notebooks, is cited in the reference list with its version and identifier. Cite the software
  itself, and its paper as well, never the paper in its place.
- **AI disclosure belongs to the authors:** whether and where AI use is disclosed follows the venue. An agent
  records what it drafted and leaves the declaration for the authors to confirm.
- **Every reference is real** (Elsevier generative-AI policy): each reference is checked to exist before
  submission, because generated references can be fabricated. AI-made figures are disclosed in their captions.

## Shared article requirements

- **Choosing the display** (Ehrenberg 1977, ACS Guide 4.1 and 4.2): apply the [conditions table and result
  plot principle](#argument). What should a reader see at a glance, or what trend or relationship should they
  see? Use a figure. Which exact values will they compare or reuse, or what detail would take many words to
  convey? Use a table with short, parallel entries and put explanations in footnotes or the text. Use an
  equation to state a mathematical relation. For phase equilibrium, use a ternary diagram with tie lines for a
  liquid split and a phase map with boundaries for a flash grid.
- Present scientific provenance: data source, equations, parameter values, units, assumptions, comparison
  basis, and uncertainty. Data are traceable to their origin, and comparison with published values is part of
  the evidence (Bazyleva et al. 2021; Cummings et al. 2009).
- Use result-led captions. A figure caption states the quantity, conditions, comparison, and supported
  observation. A table caption states what the values compare. So that figure and caption stand alone (ACS
  Guide 4.1.3, 4.1.4), a caption also defines every symbol, line, and marker and says what any error bar or
  band represents. Where the venue's captions are descriptive, the caption says what the figure shows and the
  text states the finding. Put figure captions below figures and table captions above tables.
- Follow the [scientific table rules](../visualize/latex-packages.md#scientific-tables).

## Structure

Use the applicable subset in this order.

1. a title that follows the [Rule of One](#argument), omits novelty adjectives, and sets emphasis with its
   first phrase (ACS Guide 2.3.2), then authors, affiliations, and date;
2. an informative abstract stating the question and the gap it fills, the method, principal result with
   conditions, and supported implication, within the venue's length and without citations;
3. keywords, and a nomenclature list when the venue uses one; it never replaces definition at first use;
4. introduction as a **Create a Research Space** (Swales 1990): territory, gap, contribution. The literature
   review is the evidence for the gap and the baseline the results are compared against;
5. formulation, theory, or governing equations;
6. experimental, computational, or analytical methods;
7. verification, validation, and uncertainty when they support the claims;
8. results;
9. discussion;
10. conclusions;
11. the statements the [venue package](manuscript-review.md#manuscript-structure-review) requires, such as
    data, code, funding, or conflicts;
12. references in the venue's style, and selected appendices.

This is **IMRaD as four questions** (Gastel and Day 2022; Sollaci and Pereira 2004): why, how, what, and so
what, with engineering variants such as a model section, combined Results and discussion, or alternating
methods and results. The discussion interprets and bounds; conclusions say what was learned (ACS Guide 2.3.8),
pairing each finding with its consequence or domain of validity. Top-level headings use the field's
conventional names. Subheadings name the system, study, or step, never an internal label. Merge adjacent sections when the scientific
argument is clearer without a separate heading. Introduce each result before showing it, then interpret it. Carry only the evidence needed for the conclusion.

## Skeletons by paper type

Start from the skeleton shared by published papers of the type and venue.
- **Thermodynamic model:** a model section named for the theory, split by physics, then results in rising
  system complexity (pure, binary, ternary).
- **Process, techno-economic, or optimization:** the [problem statement](#methods-reproducibility) in standard
  form, then unit and cost models, then results by study, with the cost basis, boundary before the metric, and
  sensitivity versus uncertainty described under [Methods reproducibility](#methods-reproducibility).
- **Rate-based column:** **validate, then use**: validation against plant or pilot data comes before
  sensitivity, design, or case studies.
- **Software** (JOSS review criteria): need and gap against existing packages, design trade-offs, verification
  against an independent reference, measured performance, limitations, and availability. Documentation stays
  in the documentation.

A multi-paper dissertation is one argument, with an integrating introduction and conclusion and co-author
contributions stated per chapter.

## Supplement

The supplement keeps the main text readable. Cite its derivations, term-by-term expansions, extra cases,
full tables, data, and notebooks from the main text. Reserve the problem statement and new model relations
for the main text, where the formulation and summaries of validation for main claims belong. Archive
reusable data separately as machine-readable files because PDF supplements hinder reuse and receive less
scrutiny (ACS Guide 3.1.4).

## Evidence guard

A result enters the manuscript only when it supports the selected claim order. The manuscript may omit sound
analyses that do not serve that story. It may condense an analysis-notebook result, but reported values,
conditions, uncertainty, and claim boundaries must remain consistent with the retained results.

## Scientific prose

Write direct, active, specific prose that preserves scientific meaning, uncertainty, provenance, and limitations.
Practice **calibrated hedging** (Hyland 1996; IEEE Author Center): state a supported finding
plainly with its conditions and uncertainty, and hedge only what the evidence leaves open. Over-qualifying
misreports the evidence as surely as inflating it.
Write for **a reader outside the project** (Mensh and Kording 2017, Rule 2): a term, label, or piece of
history a new reader would need explained is defined or removed. Use scientific descriptions in prose,
captions, table cells, legends, axis labels, and slides. Internal run/fit codes, issue or pull-request
numbers, commit hashes, and repository paths need [reader-facing inspection](writing-editorial.md#reader-facing-identifiers).
Keep agent actions, repository operations, build commentary, and chronological work history out of rendered
scientific prose.

Judge sentence links by **reader expectations** (Gopen and Swan 1990), as principles rather than rules: old
information opens a sentence and new, emphasized information closes it.

Watch for these prose patterns.

- formulaic openers, canned transitions, repeated connective scaffolding, false binary contrasts, dramatic
  fragments, rhetorical setups, and padded repeated structures;
- unsourced vague attribution, unsupported significance or novelty, empty participial tails, vague
  declarations, business language, chatbot residue, meta-commentary, and internal repository or workflow
  language;
- synonym cycling or terminology drift for one scientific referent;
- wording or citation scope inconsistent with an accepted claim boundary, tested domain, uncertainty
  statement, limitation, or causal description;
- over-editing that invents first person, stakes, specifics, mechanisms, contrarian framing, or staccato
  prose; and
- departures from the named writing principles, including **disproportion** under its [named
  forms](numerical-testing.md#fitness-for-purpose), such as manuscript text that reports roundoff-scale
  bookkeeping or repeats one limitation.

Preserve evidence-calibrated hedging; passive voice when the actor is irrelevant; field-appropriate
first-person plural; exact technical terms; definitions, equations, symbols, methods, metrics, citations,
source titles, and genuine domain terms; and occasional semicolons, long sentences, or three-item lists that
carry real logic. Author voice comes from supplied prior writing, and venue calibration requires supplied
requirements or inspected examples.

**Revision fidelity.** A revision preserves numbers, signs, percentages, ranges, counts, units, equations,
statistics, citations, citation scope, labels, cross-references, quotations, code, URLs, paths, figure and
table identity, and technical terminology. Preserve each value's subject, variable, group, denominator,
condition, and comparison; effect direction and magnitude; negation, modality, aggregation, scope,
uncertainty, causality, limitations, and exceptions; and whether an author or reviewer action is proposed,
planned, completed, declined, or unresolved.

- Match verbs to the evidence: use “considered during model selection” when alternatives were screened but
  their comparison is not presented, and reserve “retained for comparison” for comparisons actually shown.
- Remove temporal revision language such as “now” unless the manuscript explicitly compares defined versions.
- Replace repository-ownership terms such as “owner,” “campaign,” and “retained result table” with the actual
  equation, calculation, validation study, or reported table meant for a reader.

## Revision responses and cover letters

A response to referees follows **answer, then show** (Noble 2017): quote each comment and answer it directly.
Where the text changed, quote the changed text and say what changed; otherwise give the answer with its
evidence. Place details added at a referee's request in a table row, figure, or the supplement and point to
that location in the response. A cover letter gives the editor a short summary, not a copy of the abstract:
why this journal, what is new, and what the editor needs to route the paper (ACS Guide 2.4.4).
