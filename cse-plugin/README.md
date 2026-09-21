# Agentic Computational Science and Engineering

This repository is the source for the single `cse` plugin. The installable
payload lives in [`plugin/`](plugin/); contributor checks and setup commands
live in [`scripts/`](scripts/). Repository-only examples and tests stay outside
the payload; ScienceBench owns live workflow and routing evaluation.

## Where to work

- Scientific workflow, source, and rendering skills: [`plugin/skills/`](plugin/skills/)
- Shared doctrine and tool references: [`plugin/references/`](plugin/references/)
- Offline source validation: prepare the ignored `.venv` as documented below,
  then run `./scripts/validate.sh`. This does not invoke a host CLI, package
  resolver, renderer, or model.
- Isolated installation check: `python -m unittest discover -s tests/integration -p 'test_installation.py' -v`
- Selected rendering check: `python -m unittest discover -s tests/integration -p 'test_rendering.py' -v`
- Codex runtime check: `./scripts/sync-live.sh --check --zotero-source <absolute-checkout>` builds a task-owned Zotero wheel and verifies its CLI
  schemas. It is not the offline source command.
- Explicit reviewed Codex installation: `./scripts/sync-live.sh --validate --zotero-source <absolute-checkout>` applies the plugin and runtime transaction.

Prepare source-validation dependencies once without changing host state:

```bash
uv venv .venv --python 3.11
uv pip install --python .venv/bin/python -r requirements-validation.txt
CSE_VALIDATION_PYTHON=.venv/bin/python ./scripts/validate.sh
```

Codex and Claude Code use the same 22 skills and scientific content. See the
host-specific setup and diagnostics in
[`plugin/references/hosts/codex.md`](plugin/references/hosts/codex.md) and
[`plugin/references/hosts/claude.md`](plugin/references/hosts/claude.md).

The two execution phases are Research and design, then Execute and deliver.
Independent Review checks design readiness before execution and delivered
evidence afterward; it is not a third phase. Direct execution remains the
default. An explicitly selected installed Baton Pass skill coordinates roles
and handoffs; individual `cse:<skill>` requests keep CSE stages and acceptance
in this plugin.

Live model-backed workflow and routing trials belong to
[ScienceBench](https://github.com/agentic-cse/cse-sciencebench) and are never
part of plugin validation. Do not run live Zotero or corpus checks or live
installation while validating this candidate.
