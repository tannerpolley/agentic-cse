# CSE Zotero: Canonical Architecture and Delivery Plan

Status: canonical design contract and implementation roadmap  
Date: 2026-07-31  
Scope decision: the complete Zotero source corpus is discoverable; curation is a many-to-many relevance layer, not a three-project boundary.

## North star

An agent should be able to answer a research or modeling question from a
small, persistent, reviewable knowledge layer instead of rereading whole PDFs
by default. Every important statement used in a model, dataset, equation,
workflow, validation, or synthesis must remain traceable through exact source
evidence and back to the Zotero item that owns the source document.

The intended loop is:

~~~text
Zotero source
  -> attachment and exact evidence passage
  -> paper brief, claim, equation, idea, insight, or workflow
  -> project-selected data authority package/parameter/correlation
  -> implementation reference and validation run
  -> project result or cross-paper synthesis
  -> backlink to Zotero key, attachment, and source locator
~~~

This project is the connective tissue between documents, structured
thermophysical data, engineering code, and accumulated scientific reasoning.
It reduces repeated reading without turning an unverified summary into model
truth.

## Scope and boundaries

### Corpus scope

- Every top-level item in the local Zotero library is part of the discoverable
  source corpus, whether it is currently relevant to an active Engineering
  project or not.
- The current materialized snapshot contains 386 source records. That number
  is a validation baseline, not a permanent limit.
- Papers, reviews, reports, theses, standards, datasets, and other useful
  source records may enter the same corpus. Their type and curation status are
  explicit metadata.
- The three current project pages — ePC-SAFT equilibrium, lithium extraction,
  and MEA thermodynamics — are initial views. They are not the corpus boundary.

### Relevance scope

Relevance is a queryable, many-to-many classification. A source can belong to
several domains, projects, and research threads at once, and a source can be
discoverable without yet being relevant to a named project. A paper may also
be promoted to a shared concept or entity when its idea is reused across
domains.

The wiki must therefore support:

- broad source discovery across all Zotero records;
- triage queues for candidate, relevant, and evidence-ready sources;
- cross-domain and cross-project links;
- paper-specific context, not only project folders;
- deliberate promotion of reusable ideas, equations, data, and workflows.

### Authority boundaries

| Layer | Owns | Does not own |
| --- | --- | --- |
| Zotero | Bibliographic records, PDFs, attachments, annotations, collection context, Zotero keys | Validated model conclusions or canonical normalized data |
| CSE Zotero | Evidence navigation, briefs, claims, equations, ideas, insights, workflows, relations, synthesis | The original PDF or a project's external data authority |
| Project-selected data authority | Source-faithful tables, normalized observations, parameter sets, correlations, versions, quality state as chosen by that project | Bibliographic document storage or silent changes to project conclusions |
| Historical thermophysical-data-registry slice | An optional prior integration pattern retained for historical evidence | A mandatory repository, corpus, or project-wide data authority |
| Engineering repositories | Implementations, regression configuration, executable behavior, validation runs, figures, outputs | Silent corrections to literature or project-selected data authority |
| Schema/instructions/indexes | Vocabulary, contracts, deterministic generated indexes, agent operating rules | Scientific evidence itself |

PDFs remain in Zotero. The wiki may use a verified existing Markdown or
Mathpix Markdown companion as evidence, but it must not silently replace a
source PDF, duplicate a PDF as a new authority, or make a paper summary the
canonical numerical dataset.

## Design influences

The primary design influence is [Karpathy's LLM Wiki
gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): a
persistent Markdown layer should compound between raw sources and future
questions. Its useful operating model is three-part: immutable raw sources,
an LLM-maintained wiki, and explicit schema/agent instructions. Its core
operations are ingest, query, and lint; query starts with the index and
reusable answers are filed back into the wiki.

Two implementations sharpen that idea for this domain:

- [Programming-With-Maury's domain-aware LLM
  Wiki](https://github.com/Programming-With-Maury/Karpathy-LLM-Wiki) routes
  sources into domains, uses staging for uncertain or weak extraction, updates
  existing pages before creating duplicates, and archives weak or stale
  material.
- [Astro-Han's Agent Skills
  implementation](https://github.com/Astro-Han/karpathy-llm-wiki) keeps the
  initial system tool-agnostic and deliberately defers vector or graph search
  until measured recall or latency problems justify it.

Adopted principles:

1. Keep source evidence immutable and generated layers rebuildable.
2. Make the wiki index-first, concise, linked, and source-backed.
3. Separate deterministic staging from human-reviewed synthesis.
4. Treat ingest, query, refresh, and lint as explicit agent operations.
5. Update existing knowledge pages before creating near-duplicates.
6. Add graph, vector, or MCP machinery only after a measurable failure of the
   simple indexed Markdown/SQLite path.

## Layered architecture

### 1. Immutable source layer

The read-only Zotero materializer records normalized metadata, child
attachments, item versions, collections, tags, and hashes. Generated source
records remain separate from interpretation in the configured user-owned
corpus. The package contract is described in the [repository
instructions](../AGENTS.md); the active corpus contains its own `wiki/README.md`
artifact contract and `wiki/index.md` navigation index.

### 2. Evidence and staging layer

This layer makes source material searchable without making it authoritative.
It contains:

- existing .md and .mmd Zotero companions;
- evidence manifests with Zotero attachment keys and SHA-256 hashes;
- line-, section-, page-, table-, and equation-aware passages;
- extracted chunks and source-location metadata;
- uncertain extraction or classification records awaiting review.

The current evidence seam is implemented in the [wiki module](../src/zotero_companion/wiki.py)
and exposed by the wiki-evidence operation. The next improvement is a
rebuildable evidence chunk index that lets wiki-context return the smallest
useful passages.

PDF conversion is not a normal ingestion step. Agents must first inspect the
Zotero parent's children and reuse a usable Markdown companion. If no
companion exists, the strict [PDF/Mathpix policy in the repository
instructions](../AGENTS.md#pdf-and-mathpix-workflow) applies.

### 3. Curated wiki layer

This is the persistent, reviewable scientific memory. It should grow by
updating existing pages and adding links, not by emitting disconnected
summaries. Its planned record families are:

| Record | Purpose | Minimum provenance |
| --- | --- | --- |
| Source | Identify a Zotero item and its document role | Zotero key and item version |
| Evidence passage | Preserve a precise source statement | Attachment key, locator, hash, excerpt or equation |
| Paper brief | Explain a paper's question, method, contribution, limits, and relation to other work | Zotero key plus evidence locators |
| Claim | Atomic reusable statement | Zotero key or derived_from, status, confidence, locator |
| Equation | Equation, symbols, assumptions, units, validity, and implementation meaning | Source locator, equation text, related claims |
| Dataset reference | Point to a structured data package or observation | Registry ID/version and source locator |
| Parameter/correlation reference | Identify a model-compatible parameter or correlation | Registry ID/version, model conventions, source lineage |
| Idea/insight | Capture an interpretation or cross-paper deduction | Supporting sources, explicit derived status, confidence |
| Workflow | Capture a repeatable research or engineering procedure | Source/design references, inputs, outputs, caveats |
| Implementation reference | Connect knowledge to code, configuration, or behavior | Repository/path/version and upstream record |
| Validation run | Record what was tested, against which data, and the result | Dataset/parameter/code versions and source lineage |
| Domain/project/thread | Provide navigable context without restricting corpus membership | Stable name and linked sources/records |
| Relation | Express a typed connection between records | Source and target IDs, relation type, rationale |

The active corpus's initial curated directories contain a Figiel paper brief,
atomic claims, and NodeGraph analysis. They are a working seed, not a completed
schema or package fixture.

### 4. Project data and implementation layer

Each project selects the authority for reusable numerical truth: source-faithful
raw tables, normalized observations, units and bases, uncertainty, quality
decisions, parameter sets, correlations, and versioned manifests. That
authority may be a local directory, an existing repository, a database, or a
service already governed by the project. CSE Zotero records the selected
authority and its identity; it does not impose a thermophysical-data-registry,
DataLad, or Git-tracked corpus.

Engineering repositories own code and execution records. Each project should
pin the selected data-authority revision and record implementation commits,
fitting assumptions, validation datasets, exclusions, and generated outputs. A
model parameter is not promoted to reusable truth merely because a paper
mentions it or an agent summarizes it.

### 5. Schema, instructions, and compiled indexes

The schema and operating contract live in [CONTEXT.md](../CONTEXT.md),
[AGENTS.md](../AGENTS.md), and future explicit record schemas. Rebuildable
catalogs, SQLite indexes, manifests, and coverage reports accelerate access;
they do not replace human-readable source and curated records.

## Lineage and relation model

The minimum traceability chain is a directed acyclic dependency graph for
derived scientific artifacts:

~~~text
Zotero item
  -> child attachment
  -> evidence passage (exact locator + content hash)
  -> paper brief / claim / equation / idea / insight / workflow
  -> selected data-authority dataset / observation / parameter set / correlation
  -> implementation reference
  -> regression or validation run
  -> project result / cross-paper synthesis
  -> backlink to Zotero key and locators
~~~

Useful typed relations include extracted_from, supports, contradicts,
supersedes, depends_on, derived_from, implemented_by, uses, validates,
contextualizes, and related_to. Relations need a rationale and provenance when
they represent a scientific conclusion. A bare hyperlink is navigation; it is
not evidence.

Every promoted item should answer:

- What source or prior record does this come from?
- Where exactly is the supporting evidence?
- Is it source-reported, normalized, inferred, or project-derived?
- What assumptions, units, model conventions, and validity limits apply?
- Which data-authority version, code version, or validation run consumed it?
- What would become stale if the upstream item changed?

## Corpus routing and curation lifecycle

All source records are indexed first. Curation then proceeds through explicit
states rather than trying to fully analyze the entire library at once:

~~~text
discovered
  -> candidate
  -> relevant
  -> evidence-ready
  -> briefed
  -> claims-curated
  -> implementation-linked
  -> validated/maintained
  -> archived or superseded
~~~

These are not mutually exclusive project folders. A paper may be relevant to
multiple domains and have different records at different states. The corpus
triage index should support filters for source type, domain, project, research
thread, property family, model family, evidence availability, curation state,
and last review.

Initial domain views may include ePC-SAFT, MEA/CO2 capture, lithium
extraction, transport, phase equilibria, thermophysical data, numerical/modeling
methods, and cross-domain concepts. The exact taxonomy should stay small until
the corpus shows a repeated need for another category.

## Agent operating workflow

### Ingest and admit

1. Refresh or inspect the read-only Zotero snapshot.
2. Check freshness and existing source/evidence records.
3. Classify the source across domains and research threads.
4. Reuse an existing companion and build evidence passages when available.
5. Put uncertain extraction or classification in staging.
6. Create or update the paper brief and related pages only after evidence is
   available.

### Query and read

1. Start at wiki/index.md and a global or domain-aware wiki-context.
2. Read the relevant brief, claims, equations, selected data-authority
   references when present, and evidence hits.
3. Open a full normalized source or PDF only for an explicit audit, unresolved
   ambiguity, or missing context.
4. Preserve new reusable answers as claims, insights, workflows, or synthesis
   with provenance.

The current [CLI surface](../src/zotero_companion/cli.py) is project-oriented. It
should gain a global corpus/context route without removing the existing views.

### Connect to data and code

When a paper contributes a dataset, equation, or parameter set, create a
source-backed wiki record first, then link to the project's selected data
authority or implementation. The project record must retain the source key,
locator, authority identity/version, transformation, and validation lineage.

### Validate and audit

Validation must check more than numeric agreement. It should report source
coverage, unit/composition bases, model convention compatibility, validity
ranges, excluded observations, code/data-authority versions, and exact Zotero
backlinks. Contradictions and unresolved interpretations remain visible rather
than being silently merged.

## Retention and recovery

The repository separates rebuildable navigation from irreplaceable research
decisions. Generated source metadata, catalogs, manifests, triage files,
SQLite indexes, and evidence-sync indexes can be rebuilt from Zotero or the
selected data authority. Curated briefs, interpretations, claims, graphs,
relations, classification decisions, and user-owned source/data files cannot
be reconstructed reliably from those generated layers. Pushing this runtime
repository does not back up the external corpus, Zotero attachments, or a
project's selected data authority.

Each project records its selected authority, root or endpoint, revision, and
retention owner. Recovery uses the project's existing ordinary copy or
versioning mechanism: copy the selected corpus, hash representative curated
and data files with `sha256sum`, and verify the hashes in the copy. No
thermophysical-data-registry, DataLad, Git-tracked corpus, backup product, or
scheduler is required.

An isolated check must not write to the live corpus. For example:

~~~bash
check=/path/to/isolated-recovery-check
mkdir -p "$check"
cp -a /path/to/selected-corpus/. "$check/"
(cd /path/to/selected-corpus && \
  sha256sum wiki/projects/<project>.md data/<dataset>.csv > "$check/expected.sha256")
(cd "$check" && sha256sum -c expected.sha256 \
  && test -s wiki/projects/<project>.md \
  && test -s data/<dataset>.csv)
uv run --project /path/to/cse-zotero cse-zotero data-query \
  "$check/data/<dataset>.csv" --sql "SELECT * FROM records LIMIT 1" --json
~~~

Then run one read-only native data query against the copied dataset and compare
one known value with the copied curated record. This verifies one
representative record and dataset without changing live state; record the
result and discard the isolated copy after review.

### Refresh and lint

Refresh is explicit and repository-only. Lint should report stale dependencies,
orphan records, missing evidence, broken links, unsupported promotion,
contradictions, superseded parameters still in use, and data/equation coverage
gaps. It should be safe to run on every task and useful before a release.

### Human acquisition gate

Agents may identify missing papers and prepare exact DOI or official article
URLs, but the user performs publisher access and Zotero Connector saving in a
normal browser session. Agents do not bypass CAPTCHA/Cloudflare, automate
publisher pages, or retry blocked access. The existing acquisition rules in
[AGENTS.md](../AGENTS.md) remain mandatory.

## Revised execution order

The phases below are the capability roadmap; implementation follows this
dependency-aware order so the wiki stays low-friction while it becomes
auditable:

1. Establish the selected project's retention and recovery authority for the
   corpus and data.
2. Freeze the shared record envelope, stable-ID rules, relation vocabulary,
   and source/evidence contract before adding scientific records.
3. Build Phase 3 with two vertical slices: Figiel 2025 and Hamer 1972, which
   is intentionally outside the three initial project views.
4. Connect those records to the selected data authority when one exists,
   project views, implementation references, and validation inputs.
5. Add cross-domain concepts, synthesis, typed relations, and
   dependency-aware health checks.
6. Stabilize the small read-only agent interface, release manifests, and
   measured retrieval benchmarks.
7. Add larger retrieval or service infrastructure only if benchmarks show
   that the indexed Markdown/SQLite path is insufficient.

Version control is useful for curated records but is not a prerequisite for
the external corpus. The project records whichever authority and recovery
mechanism it actually uses; this repository does not take over that authority.

## Delivery roadmap

Each phase has a bounded exit condition. A phase can be useful on its own; no
phase should require mass-converting or fully summarizing the library.

### Phase 0 — Canon, schema, and vocabulary

This document and [CONTEXT.md](../CONTEXT.md) establish the shared language,
authority boundaries, scope, and acceptance criteria. Keep the schema
implementation-independent until the record boundaries are tested on real
papers.

Exit: agents and humans use the same terms for source, evidence, claim,
equation, dataset, insight, workflow, registry, implementation, and
validation.

### Phase 1 — Evidence-first retrieval

Status: implemented. The rebuildable SQLite evidence index stores companion
attachment keys, hashes, line/section locators, and bounded passages; context
packs return evidence hits and coverage without opening PDFs.

Build a rebuildable evidence-chunk index with attachment keys, content hashes,
section/line/page/table/equation locators, and a short text window. Add
evidence_hits and source/evidence coverage to wiki-context. Standardize a
paper brief and expand the Figiel brief using existing companions.

Exit: an agent can answer a focused paper question from index + brief + exact
passages without reading the full PDF by default.

### Phase 2 — Broad-corpus triage

Status: implemented. All materialized top-level Zotero sources are retained in
the triage index with transparent metadata suggestions and explicit reviewable
classification assignments.

Create the all-Zotero relevance/triage index. Add source type, domains,
projects, research threads, curation state, evidence availability, and review
queue. Generate transparent candidate suggestions from metadata and existing
tags, but require deliberate promotion for interpretation. Keep explicit
assignments in a curated, reviewable layer rather than hand-editing generated
source artifacts.

Exit: every source is discoverable and every curated paper has an explainable
reason for its relevance and current curation state.

### Phase 3 — First-class scientific records

Status: implemented on 2026-08-04. The shared JSON record envelope,
type-prefixed IDs, provenance lint, typed relations, read-only templates, and
the first paper/equation/dataset/parameter/idea/insight/workflow/
implementation/validation records are in `wiki/records/`. The Figiel 2025 and
Hamer 1972 records are the initial scientific vertical slices; additional
records remain a deliberate curation queue rather than bulk-generated claims.

Add validated templates and tooling for paper briefs, claims, equations,
datasets, parameter/correlation references, ideas, insights, workflows,
implementation references, validation runs, and typed relations. Preserve
source-reported, normalized, inferred, and project-derived distinctions.

Exit: the Figiel case and at least one paper outside the three initial project
views can be represented without forcing equations, insights, or workflows
into generic claims. The shared envelope is implemented before broad record
creation, and structural lint starts here rather than waiting for dependency
propagation.

### Phase 4 — Optional external data-authority integration (historical registry slice)

Historical status: implemented as a read-only cross-repository contract on
2026-08-04. It is an optional example, not a current project requirement.
Wiki records and project manifests may point to a selected authority's
source-faithful observation and staging paths without copying or editing its
data.

Connect wiki records to stable data-authority IDs and versions when the
authority provides them. Define project data manifests, source locators,
normalization lineage, parameter dependencies, validity ranges, and
promotion/review states. Keep PDFs in Zotero and keep the selected authority
authoritative for its reusable numerical values.

Exit: a model input or validation dataset can be traced from the selected
authority to a specific source passage and Zotero item, and back from Zotero to
the consuming model/run. Any integration is read-only from this repository and
accepts the authority's own stable IDs and versions.

### Phase 5 — Cross-domain knowledge and synthesis

Status: implemented for the first cross-paper slice on 2026-08-04. The
activity-basis concept, derived insight, synthesis page, and typed relations
connect Figiel 2025 and Hamer 1972; broader global hubs remain deliberately
proposed until reuse across additional domains is demonstrated.

Add shared entities, concepts, research threads, and comparison/synthesis
pages. Capture important ideas and workflows that emerge across multiple
papers, with explicit supporting and conflicting sources. Promote a page to a
global hub only when reuse across domains is demonstrated.

Exit: an agent can explain not only what individual papers report, but how
their assumptions, methods, data, and insights connect or disagree.

### Phase 6 — Dependency-aware health and coverage

Status: implemented on 2026-08-04. `wiki-health`, `wiki-coverage`, and
`wiki-stale` now report source/data-authority-triggered review queues, curation gaps,
orphaned dependencies, contradictions, superseded records, and
record/manifest lint results without refreshing or mutating any source.

Build the typed link/dependency index and stale propagation. Add lint for
contradictions, orphan pages, broken locators, missing backlinks, unsupported
claims, unlinked model inputs, selected-authority gaps, and validation coverage gaps.

Exit: a source or selected-authority change produces a bounded review queue instead of
silently leaving downstream conclusions stale.

### Phase 7 — Agent interface

Status: implemented and contract-tested on 2026-08-12. The documented
read-only seams are
`wiki-context --global`, `wiki-evidence`, `wiki-record`,
`wiki-record-search`, `wiki-record-template`, `wiki-paper-template`,
`wiki-lineage`, `wiki-health`, `wiki-coverage`, `wiki-lint`, and
`wiki-manifest-lint`.

The repository-local `.agent/skills/cse-zotero/SKILL.md` packages the
operating protocol, and `scripts/agent_smoke.py` exercises the public command
surface with the same bounded task set as the retrieval benchmark.

Stabilize the CLI contract first: global context, focused evidence, source
lookup, record lookup, lineage tracing, coverage, and lint. Add an MCP or
other service boundary only if it reduces friction for actual agents and can
remain read-only by default.

Exit: a new agent can follow one documented start command and retrieve the
right context, evidence, lineage, and limitations without knowing the folder
layout.

### Phase 8 — Review, versioning, and release

Status: implementation complete on 2026-08-04. `wiki-release` produces a
local reproducibility manifest with artifact hashes, source/evidence counts,
selected-authority revisions, Git state, lint results, and explicit no-mutation flags.
The original implementation baseline is preserved in repository history;
subsequent curation changes remain reviewable repository changes.

Put curated wiki/schema changes under a reviewable version-control workflow.
Generated source and staging layers remain rebuildable. Add review ownership,
change logs, release manifests, and reproducibility records containing code,
selected data-authority, wiki, and source snapshot versions.

Exit: another researcher can reproduce a model/validation result and audit its
full chain without trusting an undocumented agent memory.

### Phase 9 — Scale only when measured

Status: benchmarked on 2026-08-12. Twenty representative agent tasks pass
through the indexed Markdown/SQLite path with 1.0 recall, twenty fully
auditable tasks, zero PDF reads, and approximately 61.1 ms mean latency after
the whole-library companion sync. The public CLI smoke contract also passes
all twenty tasks read-only. No vector,
graph-database, MCP, or service layer is justified by this result.

Measure retrieval recall, context size, answer audit time, stale-report volume,
and query latency. Add vector or graph retrieval, DuckDB/Parquet compilation,
or a service layer only when measurements show the indexed Markdown/SQLite
path is insufficient. Do not introduce infrastructure because the architecture
looks fashionable.

Exit: each added subsystem has a recorded failure mode, benchmark, and removal
or fallback path.

## Implementation boundary after the full plan

The repository now contains the complete low-friction implementation surface:
source materialization, whole-corpus companion synchronization, a generated
source browse table, companion-only evidence retrieval, full-corpus triage,
reviewable classification, typed records and templates, data-authority/project
contracts, lineage, health and coverage reports, release manifests, and a
measured read-only agent interface. The remaining work is scientific curation:
selecting sources from the queues, reading declared companions when available,
and deliberately promoting briefs, claims, datasets, equations, and
cross-paper insights. It is intentionally not replaced by bulk summaries or
unreviewed PDF conversion.

## Sanity-test matrix

The plan is considered coherent only if these scenarios can be represented and
verified without violating authority boundaries.

| Scenario | Expected result |
| --- | --- |
| Figiel paper contributes a Born-term equation, data, and validation result | Exact evidence passages link to separate equation/claim/dataset/validation records, the selected data-authority reference is versioned when applicable, implementation references are explicit, and every path ends at Zotero YEENX35P plus locators. |
| A relevant paper is not in the three initial project views | It remains discoverable in the all-source index, can be classified into one or more new domains/threads, and can be curated without inventing a new project boundary. |
| One paper is relevant to ePC-SAFT, transport, and a shared data concept | One source record is reused through many-to-many relations; the wiki updates existing concept/entity pages instead of duplicating the paper. |
| A source companion or Zotero metadata changes | Hash/version comparison marks only dependent evidence and curated records stale; refresh does not overwrite interpretation. |
| Two papers disagree or a parameter set is superseded | Both records remain visible with contradicts or supersedes, validity/model conventions are shown, and downstream consumers receive a review warning. |
| A data record and equation record come from the same paper | They remain separate typed records with shared evidence links and can be traced independently into the selected data authority and implementation use. |
| An insight or workflow is synthesized from several papers | It is marked derived, names all supporting sources and uncertainty, and is never mistaken for a direct source quotation. |
| A source has no usable Markdown companion | The system reports evidence unavailable and follows the strict human acquisition/Mathpix gate; it does not silently convert or invent evidence. |
| A publisher blocks or challenges access | The agent stops, reports the blocker, and asks the user to complete a normal browser step; it never bypasses, spoofs, or rapidly retries. |
| An agent starts a routine question | It reads index/context/brief/evidence first; full PDF/source inspection is an explicit audit path, not the default. |
| The entire Zotero library is refreshed | All source records remain searchable, generated layers update deterministically, curated pages remain intact, and wiki-verify/wiki-stale expose any review work. |

## Guardrails and non-goals

- Do not convert a PDF when Zotero already has a usable .md or .mmd
  companion.
- Do not run routine OCR or re-OCR; preserve immutable PDFs and never expose
  Mathpix/API credentials.
- Do not bypass publisher access controls, CAPTCHA, Cloudflare, VPN/IP bans,
  login walls, or Connector human-presence checks.
- Do not mutate Zotero as part of wiki refresh, ingestion, or synthesis.
- Do not promote a paper statement to selected data-authority or implementation truth without
  source locators, assumptions, and review status.
- Do not flatten equations, composition bases, uncertainties, or model
  conventions into unqualified prose.
- Do not duplicate PDFs or create an unversioned “master spreadsheet” as the
  numerical authority.
- Do not require every one of the 386 current sources to receive a full brief
  before the system is useful.
- Do not add a vector database, Neo4j-style graph store, MCP server, or UI
  before the simpler path has a measured limitation.

## Immediate implementation slice

Status: implemented on 2026-08-04. The generated index now contains
hash-aware Markdown evidence chunks, wiki-context returns evidence hits and
coverage, paper briefs have a standard contract, and the all-source triage
queue is available through wiki-triage.

The implemented slice includes:

1. Extend the rebuildable wiki/index.sqlite with evidence chunks containing
   attachment key, path, role, content hash, line/section locator, and text.
2. Add evidence_hits and evidence coverage to wiki-context while preserving the
   current project-scoped response.
3. Standardize the paper-brief template and expand the Figiel brief from its
   existing companion evidence.
4. Add the all-Zotero corpus triage index and a low-friction queue for papers
   that are relevant but not yet briefed.

This slice reduces repeated PDF reading immediately and creates the seams for
selected data-authority and cross-paper lineage without requiring a large
migration.

### Slice 2 — Reviewable broad-corpus classification

Status: implemented on 2026-08-04. The generated triage index now carries
transparent metadata suggestions alongside explicit classification state,
domains, research threads, relevance, reasons, and review queues. The curated
`wiki/curation/source-assignments.json` layer is separate from generated source
records, and `wiki-classify` is dry-run by default.

Slices 3–9 are now implemented for the initial Figiel/Hamer vertical slice,
with selected-authority/project-manifest links, cross-paper synthesis, dependency
health, the read-only agent interface, release manifests, and a measured seed
benchmark. Scaling to more full paper briefs remains a queue-driven curation
task across the complete 386-source corpus, not a prerequisite for using the
wiki.

## Definition of a full-fledged CSE Zotero

The system is mature enough when:

- an agent starts from an index/context/brief and rarely needs a full PDF for a
  routine question;
- every model input, equation, dataset, parameter, and validation statement
  has a source/evidence chain to Zotero;
- reusable numerical truth has a stable identity/version from its selected
  data authority and project records pin what was used;
- ideas, insights, and workflows are captured as first-class, clearly derived
  knowledge rather than disappearing into chat history;
- new papers update connected pages and surface contradictions instead of
  creating isolated summaries;
- stale, unsupported, orphaned, contradictory, and unvalidated records are
  reported by routine lint;
- human approval is needed for publisher acquisition, Zotero writes, and
  important promotion/synthesis decisions, not for every read-only lookup;
- measured performance evidence, rather than fashion, justifies any additional
  retrieval or service infrastructure.

## Resolved implementation decisions

1. CSE Zotero may use local Git history for curated records, schemas, docs, and
   reproducibility manifests, but it does not require Git for the external
   corpus. Generated source artifacts remain rebuildable; a selected external
   authority keeps its own retention and release history.
2. Wiki-owned IDs use a type namespace such as `equation:...`, `idea:...`, or
   `validation:...`. External data-authority IDs remain stable when provided
   and are referenced with the authority name and version/revision.
3. Existing Zotero `.md`/`.mmd` companions are copied exactly into a declared
   evidence bundle when needed. PDFs remain in Zotero; no routine conversion or
   second PDF store is created.
4. Concepts and entities become global hubs only after at least two domains or
   research threads reuse them. Until then, a typed relation or synthesis page
   is cheaper and clearer.
5. A benchmark records retrieval recall, context size, auditability, and
   latency. Vector, graph-database, MCP, or service infrastructure is not
   justified until a measured failure of the indexed Markdown/SQLite path is
   recorded.

These choices must preserve the low-friction path: one documented read-only
entry point, one evidence lookup, one lineage report, and clear human gates
only where authority or external access is involved.
