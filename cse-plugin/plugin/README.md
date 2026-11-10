# Agentic Computational Science and Engineering

CSE helps an AI coding agent carry a scientific question through equations,
numerical work, checked results, and a readable explanation. It suits chemical
engineers and other researchers who work in Git repositories and want to
check what a calculation can support. You are the **investigator**: the person
who chooses the question, approves material decisions, and judges whether the
result is useful. The plugin supplies 22 skills as `cse:<skill>` for Claude
Code and Codex; external scientific software remains project-specific.

## Install

With Claude Code installed, run:

```bash
claude plugin marketplace add https://github.com/tannerpolley/agentic-cse.git
claude plugin install cse@cse
```

With Codex installed, run:

```bash
codex plugin marketplace add https://github.com/tannerpolley/agentic-cse.git
codex plugin add cse@cse
```

Use a host version with plugin marketplace support and read access to the Git
address. These commands use the repository-root catalog and load
`cse-plugin/plugin/`. The [Claude Code](references/hosts/claude.md) and
[Codex](references/hosts/codex.md) references record the documentation checked,
local-checkout installation, updates, and optional hooks. Hooks require
separate opt-in; they are unnecessary for a first run.

## Check your machine

Ask the agent to run this from the installed plugin root (the directory with
`skills/` and `scripts/`):

```bash
python3 scripts/workflow/check_readiness.py
```

In a source checkout, run it from `cse-plugin/plugin/`. It reports tools,
missing capabilities, and the skills they enable. It installs nothing and
contacts no paid service. The three tiers are independent additions:

| Tier | External tools | What you can do |
|---|---|---|
| Core | Git and Python | Setup, research planning, Design, Build, Analyze, Summarize, Review, and writing checks; running a model also needs that project's scientific software |
| Documents | Quarto; LuaLaTeX and `latexmk`; optional Snakemake | Render notebooks and sites, articles, slides, diagrams, and plots; Snakemake manages adopted calculation steps |
| Sources | `cse-zotero`; optional Mathpix credentials | Inspect and curate Zotero sources and scientific data; Mathpix transcribes PDFs when needed |

The readiness report distinguishes an executable being present from a complete
rendering toolchain or a configured source library. A missing tier leaves
independent work available.

## Your first five minutes

Open your project in the agent host and invoke `/cse:setup` in Claude Code or
`$cse:setup` in Codex. Setup inspects the repository, recommends `analysis`
(a study answering a question) or `tool` (reusable scientific software), and
asks one round of questions. It previews and writes two scientific records
and a managed protocol in `AGENTS.md`. Defaults are no hooks, no source/data
adoption, no Snakemake, and an analysis site only when Quarto is present.

Then start one bounded study:

1. `cse:design`: state the question, equations, method, a reference case to
   compare against, and an allowed numerical difference (the tolerance). Name
   a **falsifier**: an observation or check that would show the proposed claim
   is wrong. Accept the complete plan before execution.
2. `cse:build`: implement the agreed calculation and its checks.
3. `cse:analyze`: run it and inspect balances, residuals, convergence, and
   failed cases. Keep **retained values**: saved numerical inputs and results
   with their origin, so later figures can be checked against them.
4. `cse:summarize`: explain those saved results in the research notebook.
   To **promote** the work is to select supported results for a separate
   manuscript through `cse:write`; a rendered page alone does not establish
   scientific acceptance.
5. `cse:review`: independently check the evidence and the limits of the claim.
   Review also checks design readiness before Build.

These stages may take longer than five minutes; the first session establishes
the question and next action. See the
[worked chemical engineering examples folder](https://github.com/tannerpolley/agentic-cse/tree/main/cse-plugin/examples/)
(the study example is being added separately) and
[terminology](references/workflow/terminology.md) for the plugin's words.

Research and design covers Setup, Research, Diagnose, and Design.
Execute and deliver covers Build, Analyze, Summarize, and authorized Write
and delivery.
Independent `review` checks scientific support; `prose` checks writing quality.
Direct execution is the default, with native host delegation for bounded
independent work when useful.

## Platform limits

The plugin's commands and validation are tested on Linux. macOS and Windows
have not been tested. The always-on analysis preview needs a systemd user
manager; Setup skips that service when unavailable. Use the foreground
`python3 analyses/manuscript.py preview analyses/` fallback for a prepared
site. Preview process tracking uses Linux `/proc`; the fallback has not been
verified on macOS or Windows. No cross-platform support is claimed.

The [public source](https://github.com/tannerpolley/agentic-cse) identifies
payloads by source commit and content hash. Contributor checks live in the
parent `cse-plugin/README.md`.
