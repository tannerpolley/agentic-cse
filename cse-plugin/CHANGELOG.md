# Changelog

## 2.3.0

- Make ordinary Quarto HTML the living analysis-notebook view.
- Add a guarded no-execute notebook scaffold and an opt-in LuaLaTeX PDF profile.
- Remove the retired interactive companion from the active Visualize package.

## 2.2.1

- Require one claim-led figure for each central retained numerical relationship
  or comparison; a table, summary statistic, or CSV link cannot replace it.
- Keep table-only results for a few scalar or categorical values, exact lookups,
  and diagnosed negative results when the notebook explains why plotting would
  not clarify the claim.
- Route plottable Analyze and Summarize results through CSE Plot when installed,
  and return table-only central comparisons from Review as Revise.
- Move the six CSE lifecycle hooks out of the versioned plugin runtime into one
  stable user-owned executable selected only by repository-local CSE hook files.

## 2.2.0

- Reconcile existing repository routing during Setup without overwriting custom
  guidance, and stop copying generic decision-record starters.
- Add the read-only `cse:audit` supporting skill and replace software ceremony
  with direct scientific questions, values, diagnostics, and checks.
- Require useful method-specific numerical results before completion or
  notebook creation; retain failed cases only when they bound real results.
- Create and render the working analysis notebook before Review, keep Review
  advisory, and reserve manuscript promotion to the investigator.

## 2.1.0

- Replace the disabled broad Review Stop hook with a session-baselined gate
  that blocks completion only for unapproved persistent test growth.
- Add an Explore-to-Promote boundary, generated-repository fallback doctrine,
  and proportional named CSE reviewer protocols.

## 2.0.0

- Split optional companion skills into `cse-sources` and `cse-visualize`; core
  `cse` keeps its nine workflow skills.
- **Breaking:** `cse:{zotero,mathpix,data,digitize}` moved to
  `cse-sources:*` and `cse:{plot,tikz,pgfplots,latex,quarto,revealjs,beamer}`
  moved to `cse-visualize:*`. The old `cse:*` names have no compatibility
  aliases.
- Allow Setup to adopt a clear repository-owned analysis path and meaningful
  child names while keeping `analyses/<short-id>/` as the creation default.

## 1.1.1

- Remove repository profile labels; the CSE plugin and its canonical context
  now own scientific-repository setup.
- Keep the CSE Review reminder and activate it from
  `docs/scientific/CONTEXT.md` instead of an `AGENTS.md` profile line.
- Temporarily disable the Stop hook after repository-wide change accounting
  overrode legitimate user-decision stops; retain its script for redesign.
- Make the sole analysis-notebook template use the reviewed compact 10 pt,
  explicit-margin, and table-spacing defaults without changing manuscripts or
  presentations.

## 1.1.0

- Replace central research journals with analysis-local research notebooks.
- Add personal and repository-scoped terminology enforcement.
- Reconcile structural acceptance before Review Pass.
- Require claim-led figures and an intended-use disposition before notebook
  completion.
- Add representative routing checks, installed-plugin verification, and an
  opt-in CSE Review reminder for scientific-computing repositories.
