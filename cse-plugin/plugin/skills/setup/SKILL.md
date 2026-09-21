---
name: setup
description: "CSE Research and design — Establish or revise a repository's scientific records, vocabulary, retained-data ownership, and available routes."
metadata:
  cse-kind: "workflow"
  cse-family: "workflow"
  cse-order: "01"
  cse-tags: "workflow"
  cse-routing:
    direct: [operating-model]
    conditional: [scientific-projects, github-and-git]
---

# Establish or revise repository setup

Inspect repository guidance, existing scientific records, terminology, inputs,
analyses, documents, Git state, and available commands. Activate
`scientific-projects` for record ownership or migration and `github-and-git`
for issue and integration rules. Use `cse:zotero` or
`cse:data` after checking the requested external capability when source authority
or lineage is unresolved. Use CSE rendering only for a selected render output or
the root Quarto Manuscript assets for a confirmed analysis; `tool` gets no
Quarto Manuscript by default. If the renderer is absent, finish independent
setup and report the exact missing capability; never silently install one.
Apply the shared decision-frontier rule to role, purpose, and owner choices
after inspection; confirm the investigator's `analysis` or `tool` role on
every Setup run; continuing handoffs inherit an answer.
When root `AGENTS.md` has no project execution preference, offer `direct` or
`baton` once and record the selection as a separate plain paragraph:
`CSE execution mode: direct.` or `CSE execution mode: baton.` Direct is the
default until a preference is recorded. Keep this independent of repository
role, preserve unrelated guidance, and do not rewrite it for a task override.
Workflow reads the paragraph directly; create no parser, configuration file,
or duplicate preference in `CONTEXT.md`.
Use this workflow for both initial preparation and later reconciliation when
the repository's scientific setup, ownership, vocabulary, or available routes
need to change. Preserve accepted existing setup and revise only the unresolved
or outdated subset. Fresh preparation creates only root
`docs/scientific/README.md` and `docs/scientific/CONTEXT.md` by default;
formulation, methods, evidence, decisions, and writing records are optional
Markdown selections offered together through multi-select input when available.
Pass selected names as a comma-separated `--optional` value to deterministic
preparation. Manuscript LaTeX and bibliography belong only under
`docs/scientific/latex/` when writing is selected.
Align only the unresolved material subset. Inspect purpose and owners, recommend
`analysis` or `tool` with a reason, and obtain confirmation every run.
`python3 scripts/workflow/setup_scientific_project.py --repo <root> --check-routing` and
`--reconcile` produce a complete read-only move, merge, delete, and caller/link
plan; add `--role analysis` or `--role tool` for a confirmed preview. They
write nothing until the same plan is rerun with `--approve --role <role>`. Merge
every root or nested `CONTEXT.md` into the one root `CONTEXT.md`, including
its sourced glossary and avoid table, and mark missing sources as `sourceless`.
The scientific context owns the question, intended use, owners, one
confirmed `repository role: analysis | tool` line consumed by Design and the
stance hook, and one `agent role: <discipline and specialization>` line with
its responsibilities paragraph under `## Agent role`.
Preview user configuration,
repository guidance, files to create or migrate, and optional integrations
before mutation. Reuse the project assets for a populated `docs/scientific/`
core; do not create placeholders, generic ADR starters, competing owners, or
unused metadata. Audit the root `AGENTS.md` for exactly one managed CSE Protocol
section between `<!-- CSE:BEGIN PROTOCOL -->` and `<!-- CSE:END PROTOCOL -->`,
placed after the document title, whose first instruction is the confirmed agent
role followed by the repository role and concise working instructions. Setup
generates it from `docs/scientific/CONTEXT.md`; never hand-edit it or keep a
second copy. In the material-choice round ask once for a missing scientific
discipline and specialization and one paragraph of project responsibilities;
retain confirmed values on later passes and ask only about proposed changes.
`python3 scripts/workflow/setup_scientific_project.py --repo <root> --check-routing`
reports a missing, stale, or malformed block, a missing agent role, and the exact
proposed repair; approved application replaces the legacy pointer paragraph and
preserves all other guidance. Duplicate or unmatched markers require manual
reconciliation, never a guessed overwrite. A drifted block is shown as a diff;
approved regeneration uses the retained scientific context unless the
investigator supplies a new decision. Migrate
established records with exact caller and link updates, preserving ownership;
use `git mv` where practical and leave no alias, duplicate, or redirect. Create only
populated analysis inputs, scripts, results, and figures; new sets use
`analyses/<short-id>/{inputs,scripts,results,figures}`. For a confirmed `analysis`,
Setup confirms purpose, root/home content, and adoption, then invokes
`manuscript.py init` when the renderer is available to initialize or safely adopt the
populated root Quarto Manuscript; do not rename or migrate it solely to match the
default. Setup does not create substantive per-analysis report; Summarize owns it.
A confirmed `tool` gets no default Quarto Manuscript; without a renderer, report
the exact missing capability.
For confirmed deterministic preparation, use
`python3 scripts/workflow/setup_scientific_project.py --role <role> --agent-role "<discipline and specialization>" --responsibilities "<paragraph>"`;
the same two options apply to `--reconcile --approve`, and omitted values are
retained from the existing scientific context.
Preflight all destinations before the first write, then verify the final pointer and both readable
scientific files. Setup prepares scientific records and project guidance; existing hook
configuration stays untouched. For host invocation, structured questions, native
subagents, instruction discovery, installation, and diagnostics, read the applicable
[`Codex host reference`](../../references/hosts/codex.md) or
[`Claude Code host reference`](../../references/hosts/claude.md). Hooks require a
separate explicit opt-in through `scripts/workflow/install_cse_hooks.py --agent
<host> --repo <root>`. Use its `--diagnose` option for read-only inspection. In Claude Code,
ensure root `CLAUDE.md` imports `@AGENTS.md`, preserving existing guidance,
before claiming automatic project-guidance loading. Write personal terminology,
Companion state, or remote records only after their required approval. Verify
needed capabilities and report the exact missing one instead of inventing a default.
Continue to `cse:research`, `cse:diagnose`, or `cse:design`.
