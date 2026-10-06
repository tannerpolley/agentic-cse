---
name: setup
description: "Prepare or reconcile a repository's scientific records, vocabulary, analysis or tool role, retained-data owners, and optional CSE hooks. Use when starting CSE in a repo (\"set up this project\"), installing CSE hooks, or migrating scientific records and ownership."
metadata:
  cse-kind: "workflow"
  cse-family: "workflow"
  cse-order: "01"
  cse-tags: "workflow"
  cse-routing:
    direct: [operating-model]
    conditional: [scientific-projects, github-and-git, skill-families]
---

# Establish or revise repository setup

Read first: [operating-model](../../references/workflow/operating-model.md).

Inspect repository guidance, existing scientific records, terminology, inputs,
analyses, documents, Git state, and available commands. Activate
[scientific-projects](../../references/workflow/scientific-projects.md) for record ownership or migration and [github-and-git](../../references/workflow/github-and-git.md)
for issue and integration rules. When CSE and engineering skills overlap, use
[skill families](../../references/workflow/skill-families.md) to choose by subject.
For a GitHub repository, reconcile its
[milestones](../../references/workflow/github-and-git.md#milestones) on every
run: read all milestones and open issues with `gh`, then preview the exact
milestone renames and missing descriptions, issue title-prefix removals, and a
proposed milestone for each unassigned open issue. Apply only the approved
subset and read it back. Use `cse:zotero` or
`cse:data` after checking the requested external capability when source authority
or lineage is unresolved. Use CSE rendering only for a selected render output or
the root Quarto analysis site assets for a confirmed analysis; `tool` gets no
Quarto analysis site by default. If the renderer is absent, finish independent
setup and report the exact missing capability; never silently install one.
Apply the shared [decision-frontier rule](../../references/workflow/operating-model.md#decision-frontier-handoff-and-reference-reuse) to role, purpose, and owner choices
after inspection; confirm the investigator's `analysis` or `tool` role on
every Setup run; continuing handoffs inherit an answer.
Record the default execution preference in root `AGENTS.md` as a separate
plain paragraph: `CSE execution mode: direct.` Reconcile a retired Baton
preference to direct. Workflow uses direct work and native host delegation,
including T3 Code delegated tasks when useful. Keep this independent of
repository role and preserve unrelated guidance; create no parser,
configuration file, or duplicate preference in `CONTEXT.md`.
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
the non-glossary content of stray `CONTEXT.md` files into the scientific records.
Only tables under `## Glossary` and `## Avoid` are migration candidates. Move a
glossary row only when every column maps exactly to Matt's vocabulary format:
term, definition, required `Source:`, and optional code-span `Scope:` paths.
Mark missing sources `sourceless`; preserve existing definitions and sources.
A plain synonym becomes `_Avoid_:` only when its scope matches the term and
it has no exceptions or other information to lose. All other complete avoid
rules move, with every column, to `## Prose avoid rules` in
`docs/scientific/CONTEXT.md`. Keep unrelated tables, malformed rows, and
conflicting definitions in place; preview each retained row and the reason.
Never delete a file that still holds unmapped vocabulary.

Detect Matt-format stray `CONTEXT.md` files with the glossary entry reader.
When no root glossary exists, rename the file to `GLOSSARY.md` with `git mv`;
otherwise merge its entries without losing conflicts. Likewise upgrade
`CONTEXT-MAP.md` to `GLOSSARY-MAP.md` only when no glossary map exists.
Rewrite callers, including dot-relative links. Never delete, rename, or merge
away an existing `GLOSSARY.md` or `GLOSSARY-MAP.md`, and never create a map.
Read existing mapped glossaries; missing ones are lazy, not configuration errors.
Without explicit scope, a mapped glossary applies in its own directory.
The scientific context links to vocabulary and owns project prose rules.
Literal caller rewrites miss code-built paths and fixed parent-directory climbs;
check those manually after approved moves.
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
Offer the explicit source/data adoption choice `none`, `zotero`, or
`project-data`; when supplied, persist it in `docs/scientific/CONTEXT.md` and
regenerate the managed protocol pointer from that record. An omitted choice
preserves an existing adoption decision and adds no pointer to an existing
repository.
When adoption is `zotero` and Companion reports `project-libraries-v1`, bind the
project to its Zotero collection as in the
[project library](../../references/sources/zotero-companion.md#project-library)
reference. Show the `project-register` preview (an existing collection or a new
one under the root), then apply only after approval.
The same `--check-routing` plan also reports a missing, stale, or malformed block, a missing agent role, and the exact
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
populated root Quarto analysis site; do not rename or migrate it solely to match the
default. With the renderer available, Setup then runs
`python3 analyses/manuscript.py service analyses/` from the main checkout with the
project's presentation interpreter (`--python <path>` when it is not the one
running the command), as described in
[quarto-execution](../../references/visualize/quarto-execution.md#main-checkout-preview-service),
and reports `serving <url>`, the not-answering journal command, or the exact
missing capability.
Setup does not create substantive per-analysis report; Summarize owns it.
A confirmed `tool` gets no default Quarto analysis site; without a renderer, report
the exact missing capability.
For a populated analysis, offer optional adoption of the local Snakemake
workflow and record the investigator's choice; do not require Snakemake for
Setup or for repositories that do not adopt it. Read the [Snakemake workflow reference](../../references/workflow/snakemake.md).
For confirmed deterministic preparation, use
`python3 scripts/workflow/setup_scientific_project.py --role <role> --agent-role "<discipline and specialization>" --responsibilities "<paragraph>"`;
add `--source-data-adoption <none|zotero|project-data>` when the investigator
confirms that material choice. The same option applies to
`--reconcile --approve`; omitted values are retained from the existing
scientific records.
Preflight all destinations before the first write, then verify the final pointer and both readable
scientific files. In the existing material-choice round, inspect the selected host's hook state with
`scripts/workflow/install_cse_hooks.py --diagnose --agent <host> --repo <root>` (always name the
selected host and the actual repository or worktree so the report describes that checkout) and explain once that the reinforcement injects the
confirmed agent and repository roles at entry and requests one bounded semantic completion review at the
first Stop; installed files do not establish host trust or scientific truth. On explicit opt-in, invoke the
same installer with `--agent <host> --user` (once per host; it covers every CSE repository and worktree)
and preserve unrelated settings; a repository already registered with `--repo` is moved with `--remove --repo <root>`. Whether hooks are
accepted or declined, Setup maintains the role-first `AGENTS.md` protocol and scientific guidance; declining
is not Setup failure. Do not re-ask
after the choice is settled unless host state materially changes. Setup prepares scientific records and project
guidance; existing hook configuration stays untouched otherwise. For host invocation, structured questions, native
subagents, instruction discovery, installation, and diagnostics, read the applicable
[`Codex host reference`](../../references/hosts/codex.md) or
[`Claude Code host reference`](../../references/hosts/claude.md). In Claude Code,
ensure root `CLAUDE.md` imports `@AGENTS.md`, preserving existing guidance,
before claiming automatic project-guidance loading. Write personal terminology,
Companion state, or remote records only after their required approval. Verify
needed capabilities and report the exact missing one instead of inventing a default.
Continue to `cse:research`, `cse:diagnose`, or `cse:design`.
