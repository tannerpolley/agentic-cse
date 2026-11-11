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
    conditional: [scientific-projects, setup-maintenance, github-and-git, skill-families, analysis-sets]
---

# Prepare a first scientific project

Read [operating-model](../../references/workflow/operating-model.md) first.
Run the read-only readiness command from the plugin root:
`python3 scripts/workflow/check_readiness.py`. Report missing capabilities;
never silently install them. Paths below are relative to that root (prefix
`plugin/` from a contributor checkout).

For record ownership, load [scientific-projects](../../references/workflow/scientific-projects.md);
for analysis sets and site ownership, load [analysis-sets](../../references/workflow/analysis-sets.md).

1. Inspect repository guidance, Git state, scientific records, vocabulary,
   inputs, analyses, documents, and available commands. Recommend `analysis`
   (a repository answering a scientific question) or `tool` (reusable scientific
   software), with a reason. For existing records, migration, vocabulary,
   tracker reconciliation, a Quarto site, or requested hooks, load
   [Setup maintenance](../../references/workflow/setup-maintenance.md) only
   for the applicable work; it owns preview, approval, and preservation rules.
2. Ask one round of native structured questions to confirm the role, purpose,
   scientific discipline and specialization, and one paragraph of project
   responsibilities. Retain confirmed answers on later passes. Offer optional
   records and integrations in that round. First-run defaults when no choice
   is made: no hooks, source/data adoption `none`, no Snakemake, and a Quarto
   site only for `analysis` when Quarto is present. Existing decisions survive
   omitted choices. Use the shared
   [decision-frontier rule](../../references/workflow/operating-model.md#decision-frontier-handoff-and-reference-reuse)
   for unresolved material choices.
3. Preview the exact files and guidance to be written before mutation:
   `python3 scripts/workflow/setup_scientific_project.py --repo <root>
   --reconcile --role <role>`. After acceptance, rerun with `--approve`,
   `--agent-role "<discipline and specialization>"`,
   `--responsibilities "<paragraph>"`, and the confirmed
   `--source-data-adoption <none|zotero|project-data>`. Fresh preparation writes
   the populated core `docs/scientific/README.md` and
   `docs/scientific/CONTEXT.md` and generates the role-first `AGENTS.md` CSE
   Protocol block. Never hand-edit that managed block. The scientific context
   owns the question, intended use, owners, `repository role: analysis | tool`,
   and `agent role: <discipline and specialization>` with responsibilities.
   Record `CSE execution mode: direct.` as a separate root `AGENTS.md`
   paragraph, preserving other guidance. Create no parser, configuration file,
   or duplicate preference in `CONTEXT.md`. For Claude Code, preserve root
   `CLAUDE.md` guidance and ensure it imports `@AGENTS.md` before claiming
   automatic guidance loading.
4. Verify both core records are readable and `--check-routing` reports the
   correct protocol and roles. Finish approved optional work using Setup
   maintenance. Skip the preview service unless a systemd user manager is
   available; that reference gives the foreground `manuscript.py preview`
   fallback. Stop and report the files, choices, missing capabilities, and
   next study step (`cse:design`, or `cse:research` / `cse:diagnose` if needed).
