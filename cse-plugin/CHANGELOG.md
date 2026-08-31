# Changelog

## 2.0.0

- Split optional companion skills into `cse-sources` and `cse-visualize`; core
  `cse` keeps its nine workflow skills.
- **Breaking:** `cse:{zotero,mathpix,data,digitize}` moved to
  `cse-sources:*` and `cse:{plot,tikz,pgfplots,latex,quarto,revealjs,beamer}`
  moved to `cse-visualize:*`. The old `cse:*` names have no compatibility
  aliases.

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

## Version policy

- Patch releases correct behavior without changing skill or hook behavior.
- Minor releases add a skill, supporting tool, hook behavior, or material
  workflow improvement.
- Major releases make an incompatible rename, removal, or CSE detection
  change.
