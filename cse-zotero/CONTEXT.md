# Zotero-LLM-Wiki vocabulary

This glossary defines the domain concepts used by the wiki and its connected
project-selected data authorities and engineering repositories. It intentionally avoids
implementation details; commands and file formats belong in the repository
instructions and the canonical plan.

## Core terms

**Source** — A bibliographic or research record in Zotero, identified by a
stable Zotero key. It may represent a paper, review, report, thesis, standard,
dataset, or another useful document.

**Evidence** — A source-derived attachment or precisely located passage,
equation, table, figure, or annotation. Evidence preserves what the source
actually says and is not automatically a validated conclusion.

**Brief** — A concise paper-level orientation that states the source's
question, methods, contribution, assumptions, limitations, and relationships
to other work, with links to evidence.

**Claim** — An atomic reusable statement whose status, confidence, and
provenance are explicit. A claim may be source-reported or derived, but it must
not hide that distinction.

**Equation** — A mathematical relationship together with symbols, units,
assumptions, domain of validity, source locator, and any implementation or
validation meaning. An equation is not just an unqualified text snippet.

**Dataset** — A coherent collection of observations or source-faithful data
with composition basis, units, conditions, uncertainty, provenance, and quality
state.

**Parameter set** — A versioned, model-specific collection of compatible
parameters and dependencies. Parameters are not assumed to be transferable
outside their stated model formulation and validity range.

**Insight** — An interpretation or deduction that connects evidence from one
or more sources. It is explicitly derived and carries supporting sources,
uncertainty, and limitations.

**Workflow** — A repeatable sequence of research, extraction, fitting,
validation, or engineering actions, including inputs, outputs, assumptions, and
failure modes.

**Validation** — An evidence-backed comparison or test of an implementation,
parameter set, or derived result against declared data, conditions, and
acceptance criteria.

**Project** — A bounded engineering effort that consumes selected sources,
data-authority records, implementations, and validation results.

**Domain** — A subject-area view such as ePC-SAFT, MEA/CO2 capture, lithium
extraction, transport, phase equilibria, or methodology. A source can belong to
multiple domains.

**Research thread** — A focused question or evolving line of reasoning that
can cross projects and domains, such as a particular electrolyte treatment,
parameterization strategy, or data-quality issue.

**Data authority** — The project-selected, versioned home for reusable
structured scientific data, observations, parameter sets, and correlations.
An external registry is one possible authority; it links to Zotero sources but
does not replace them.

**Implementation reference** — A pointer from a knowledge or registry record
to code, configuration, or executable behavior in an engineering repository,
including the version needed to interpret it.

**Relation** — A typed, reasoned connection between records, such as
supports, contradicts, supersedes, depends_on, derived_from, implemented_by, or
validates.

## Authority rules

1. Zotero owns the document and bibliographic source record.
2. Evidence records what a source says; evidence alone is not project truth.
3. The wiki owns curated navigation, interpretation, relations, and synthesis,
   with explicit provenance and review state.
4. Each project selects and records the authority for reusable numerical data
   and compatible parameter/correlation versions; a thermophysical-data
   registry is optional.
5. Engineering repositories own implementation behavior, fit runs, and
   validation outputs.
6. A derived statement must remain visibly derived and must link to all
   material supporting records.

## Scope rule

All Zotero sources are discoverable. Relevance is a many-to-many classification
across domains, projects, and research threads; the initial three project views
are not a limit on the corpus.
