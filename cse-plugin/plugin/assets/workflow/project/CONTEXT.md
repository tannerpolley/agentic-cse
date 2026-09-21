# Scientific context

repository role: analysis

## Agent role

Setup records one `agent role: <discipline and specialization>` line here,
followed by one paragraph of project-specific responsibilities. The role is a
working mandate applied to investigation, implementation, review, handoffs,
and responses; it is not a credential.

## Question and intended use

State the scientific question, intended decision or use, and the domain in which conclusions may apply.

## Owners

Name the accountable owners for the scientific question, source data, model,
analysis, and writing.

## Glossary

Every project term has a meaning and a source. Mark a missing source as
`sourceless` for later review; do not invent a source during Setup.

| Term | Meaning | Source | Scope |
|---|---|---|---|

## Avoid

Use one row per confirmed repository-specific preference. Scopes are
repository-relative POSIX globs; separate multiple scopes or exceptions with
semicolons. Keep personal preferences in `~/.config/cse/config.toml`.

| Avoid | Prefer | Meaning | Scope | Exceptions | Evidence |
|---|---|---|---|---|---|

Leave the table without data rows when the repository has no confirmed scoped
terminology rules; do not invent a preference during Setup.

## Scientific map

- Formulation: `docs/scientific/formulation.md` when enabled
- Methods: `docs/scientific/methods.md` when enabled
- Verification, validation, and uncertainty: `docs/scientific/evidence.md` when enabled
- Scientific decisions: `docs/scientific/decisions/` when enabled
- Analyses and notebooks: root `analyses/<short-id>/`
- Manuscript sources: `docs/scientific/latex/` when writing is enabled
- Bibliography: `docs/scientific/latex/references.bib` when writing is enabled
- Zotero Companion: record the configured capability and project collection,
  or state that no Companion authority is configured

## Source authority

Name the source hierarchy and exact location of project-approved equations, parameters, data, reference cases, and tolerances.

## Claim boundaries

State supported uses, excluded phenomena, validity limits, and unresolved scientific questions.
