# LaTeX article profiles

Use this reference for the LaTeX setup of author-controlled scientific articles.
Use one profile per rendered document. Use the [manuscript profile](#manuscript-profile) for a manuscript.

## Shared article requirements

- Use LuaLaTeX and KOMA-Script `scrartcl` for the author-controlled default.
  Let KOMA-Script own headings and page furniture. It also owns the manuscript
  type area.
- Keep a one-column body so equations, process diagrams, multipanel figures,
  and scientific tables retain readable width.
- Use the scientific core from [latex-packages](latex-packages.md). Every article-capable tool
  in that reference is available when the article needs its capability.
- Load a package or extension only when the document exercises its capability.
  Select one owner for overlapping capabilities and keep profile styling out
  of shared notation and figure source.
- See [quarto-execution](quarto-execution.md) for a Quarto project. Let Quarto own document
  assembly, presentation tables, citations, cross-references, and code
  highlighting. Keep execution disabled by default and never run the
  scientific model during document rendering. Keep stable LaTeX notation,
  packages, and semantic figure styles in reviewed headers.
- Apply [latex-layout-and-qa](latex-layout-and-qa.md) to every selected PDF output. Compilation,
  resolved references, automated visual QA, and full-size page inspection are
  required.

Follow the [writing principles](../workflow/scientific-writing.md#shared-article-requirements)
for display choice, captions, and scientific tables.

## Manuscript profile

The manuscript presents one scientific argument from abstract through conclusion,
with every section advancing the same question and conclusion. See the
[writing principles](../workflow/scientific-writing.md#structure) for manuscript
structure, skeletons, supplement, and evidence selection.

### Appearance

- Use `scrartcl`, 11 pt, one-sided, one column, `DIV=calc`, normal heading
  size, conventional paragraph indentation, and restrained vertical spacing.
- Use a compact title block followed immediately by the abstract and
  keywords. Omit a table of contents and chapter-style title pages.
- Use black body text. Reserve the project color palette for figures, links,
  and small semantic accents that remain meaningful in grayscale.
- Use numbered sections and equations. Keep headers quiet and page numbers
  visible. Do not imitate a named publisher, masthead, volume, issue, or DOI.
- Place figures and tables near their first substantive discussion. Use float
  barriers only at real semantic boundaries.

## Manuscript writing and source organization

Treat mechanical correctness as the first check. A manuscript build must have
no unresolved references, duplicate labels, or missing citation keys. Review
the assembled manuscript for statements whose meaning still depends on
information outside the document. See the [scientific completeness](../workflow/scientific-writing.md#methods-reproducibility)
and [scientific prose](../workflow/scientific-writing.md#scientific-prose)
principles for publication review.

### Keep one authoritative manuscript edition

- Advertise one current manuscript entrypoint and one current build command.
- Remove an obsolete draft from ordinary navigation and build commands, or mark it unmistakably as historical and outside current scientific claims.
- Do not let a writing checker silently exclude an older edition that is still advertised as buildable.
- Search legacy sections, appendices, README instructions, and build scripts for publication claims that disagree with the current manuscript.

### Make paragraphs and sentences inspectable

LaTeX sections, equations, figures, and tables have explicit commands and
labels; ordinary paragraphs and sentences do not. Use source layout to make
prose reviewable without adding rendered structure:

1. Put one complete sentence on each physical source line.
2. Keep blank lines as paragraph boundaries.
3. Add one stable comment identifier before each paragraph, using a section-based form such as `% P:introduction-05`.
4. Derive a sentence identifier from the paragraph identifier and sentence order when a review tool needs one; do not store a second sentence map in the manuscript source.
5. Generate any paragraph- or sentence-cohesion report under `builds/`; do not maintain a duplicated manuscript map.
6. Do not use `\paragraph{}` or sentence-wrapper macros merely to create tracking identifiers. They add formatting or command semantics without improving the scientific argument.

See a [source paragraph example](../workflow/writing-examples.md#example-source-paragraph).

### Drafting versus final review

Use the [story-spine triggers](../workflow/manuscript-review.md#story-spine-read) during
revisions and the [final manuscript checkpoint](../workflow/manuscript-review.md#final-manuscript-checkpoint)
for mechanical checks and cohesion review at a final check or publication handoff.

### Separate scientific correction from source reflow

Correct missing identities, assumptions, methods, conditions, and claims before
reflowing the source. Commit the scientific prose correction separately, then
make the one-sentence-per-line conversion as a formatting-only commit. The
separate diff keeps scientific review focused and makes later source
reorganization mechanically checkable.

## Evidence selection for manuscripts

Select investigator-promoted results and present them as one scientific
argument. Share retained tables, figure sources, notation, and bibliography
keys with the analysis where applicable. Follow the
[investigator promotion procedure](../workflow/operating-model.md#continuation-and-investigator-promotion).
