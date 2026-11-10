# Setup reconciliation and optional integrations

Load this reference for existing scientific records, migration, vocabulary,
tracker reconciliation, a Quarto site, or requested hooks. Preserve accepted
setup and revise only the unresolved subset. Confirm `analysis` or `tool` on
reconciliation runs; continuing handoffs inherit an answer. Use
[scientific-projects](scientific-projects.md) for record ownership and migration,
and [skill families](skill-families.md) when installed engineering skills overlap.

## Preview and apply

`python3 scripts/workflow/setup_scientific_project.py --repo <root>
--check-routing` and `--reconcile` produce a read-only move, merge, delete,
and caller/link plan; add `--role analysis` or `--role tool` for a confirmed
preview. Nothing is written until the same plan is rerun with
`--approve --role <role>`. Supply confirmed `--agent-role`,
`--responsibilities`, and `--source-data-adoption` choices on that application.
Omitted choices preserve existing records. Preflight every destination before
the first write; verify both readable core files and the final protocol block.

Use project assets for populated records. Optional formulation, methods,
evidence, decisions, and writing records are Markdown selections offered in
one multi-select input when available; pass names as comma-separated
`--optional` values to deterministic preparation. Manuscript LaTeX and
bibliography belong under `docs/scientific/latex/` when writing is selected.
Create only populated analysis inputs, scripts, results, and figures; new
sets use `analyses/<short-id>/{inputs,scripts,results,figures}`.
Setup creates no substantive per-analysis report; Summarize owns it.

Merge content from CSE-format stray `CONTEXT.md` files only when those files
will be removed. Do not copy prose from files that stay in place. Preserve
ownership with exact caller and link updates; use `git mv` where practical
and leave no alias, duplicate, or redirect. Keep the existing caller rewriting;
literal rewrites miss code-built paths and fixed parent-directory climbs,
which need manual checks after approved moves.

## Vocabulary and managed guidance

Only CSE-owned tables under `## Glossary` and `## Avoid` are migration
candidates. Move a glossary row only when every column maps exactly to the
project vocabulary format: term, definition, required `Source:`, and optional
code-span `Scope:` paths. Mark missing sources `sourceless`; preserve existing
definitions and sources. A plain synonym becomes `_Avoid_:` only when its
scope matches the term and it has no exceptions or other information to lose.
Move other complete avoid rules, with every column, into
`## Prose avoid rules` in `docs/scientific/CONTEXT.md`, creating that section
if absent. Keep unrelated tables, malformed rows, and conflicting definitions
in place; preview each retained row and its reason. Never delete a file that
still holds unmapped vocabulary.

Existing `GLOSSARY.md`, `GLOSSARY-MAP.md`, and vocabulary-format `CONTEXT.md`
and `CONTEXT-MAP.md` files have independent ownership. Never move, rename,
or merge them as CSE stray records or create a map. Report the applicable
[optional integration's upgrade step](personal-tool-integrations.md) for
pre-1.3 files; leave contents, relationships, and links untouched. Read existing
mapped glossaries; missing ones are lazy, not configuration errors. Without
explicit scope, a mapped glossary applies in its own directory. The scientific context
links to vocabulary and owns project prose rules.

Audit root `AGENTS.md` for exactly one managed CSE Protocol section between
`<!-- CSE:BEGIN PROTOCOL -->` and `<!-- CSE:END PROTOCOL -->`, after the title.
Its first instruction is the confirmed agent role, followed by the repository
role and working instructions. Generate it from `docs/scientific/CONTEXT.md`;
never hand-edit it or keep a second copy. `--check-routing` reports missing,
stale, or malformed blocks, missing roles, and the exact proposed repair.
Approved application replaces a legacy pointer while preserving other guidance.
Duplicate or unmatched markers need manual reconciliation, never a guessed
overwrite. Show drift as a diff; regenerate from retained scientific context
unless the investigator supplies a new decision. Reconcile a retired Baton
execution preference to the separate `CSE execution mode: direct.` paragraph.

## Tracker and source adoption

For a repository with a tracker, follow
[tracker selection and milestones](github-and-git.md). On each Setup run,
read all milestones and open issues, preview exact milestone renames, merges,
missing descriptions, title-prefix removals, and a proposed milestone for each
unassigned issue or issue in a milestone being merged away. Apply only the
approved subset and read it back. When there is no tracker, use that reference's
conversation handoff; create no replacement store.

Use `cse:zotero` or `cse:data` after checking capabilities when source authority
or lineage is unresolved. With adoption `zotero` and Companion capability
`project-libraries-v1`, follow the
[project library](../sources/zotero-companion.md#project-library) instructions:
show `project-register` preview for an existing collection or a new one under
the root, then apply only after approval. Write personal terminology,
Companion state, or remote records only after their required approval.

## Optional analysis site

For confirmed `analysis`, confirm purpose, home content, and adoption in the
same question round. When Quarto is present, use `manuscript.py init` to
initialize or safely adopt the populated root Quarto analysis site. Preserve an
existing root instead of migrating it solely to match the default. A `tool`
gets no site by default. Without the required renderer, finish independent
setup, report the missing executable, and install nothing.

Before attempting the always-on service, check that `systemctl` exists and
`systemctl --user show-environment` succeeds. Only with that capability, run
`python3 analyses/manuscript.py service analyses/` once from the main checkout
as part of approved Setup, using the project's interpreter. Follow
[Quarto execution](../visualize/quarto-execution.md#main-checkout-preview-service)
and report `serving <url>`, the not-answering journal command, or the missing
capability. Without a systemd user manager, skip `service` and give
`python3 analyses/manuscript.py preview analyses/` as the foreground fallback.
Offer Snakemake adoption for a populated analysis only as an option; read
[Snakemake](snakemake.md) when selected and record the choice.

## Requested hooks

In the material-choice round, diagnose the selected host and actual checkout:
`scripts/workflow/install_cse_hooks.py --diagnose --agent <host> --repo <root>`.
Explain once that hooks inject confirmed roles at entry and request a bounded
semantic completion review at Stop; installed files establish neither trust
nor scientific truth. On explicit opt-in use `--agent <host> --user` once per
host for all CSE repositories and worktrees, preserving unrelated settings.
Move an existing repository registration with `--remove --repo <root>` so it
does not run twice. Keep existing hook configuration otherwise. A declined
choice is not failure; retain the managed protocol and do not re-ask unless
host state materially changes. Read the applicable
[Codex](../hosts/codex.md) or [Claude Code](../hosts/claude.md) host reference
for installation, trust, diagnostics, and invocation.
