# Codex host reference

The CSE plugin is one shared payload for Codex and Claude Code. Codex exposes
the same 22 `cse:<skill>` skills, shared `references/`, and scientific assets;
this file records only Codex invocation, native interaction, installation, and
diagnostics. It does not add a second skill tree or require another host.

## Invoke and ask

Invoke a stage directly with `$cse:<skill>`, such as `$cse:setup` or
`$cse:review`. Shared skills own the scientific question, evidence, and claim
limits. Use Codex's native structured question input for a material choice
about role, purpose, method, evidence, authority, or delivery. If that native
input is unavailable, report the missing capability and pause only the dependent
action.

Codex native subagents are optional execution tools. Use them only when they
help with an independently bounded task; they are not a required CSE phase,
staffing policy, or generated role definition. If the host does not provide
them, continue the direct CSE route and report that limitation when it matters.

## Instruction discovery

Codex discovers the installed plugin's `skills/` directory from its native
plugin metadata and discovers project guidance from the repository's
`AGENTS.md` files. Confirm the actual installed entry and source with:

```bash
codex plugin list --json
```

The source checkout remains authoritative. Do not infer a source path from a
cache directory, and do not claim that a listed plugin means the current task
has loaded it or that hooks are trusted and active.

## Install and update

The repository's Codex adapter is the existing sync/check path:

```bash
./scripts/sync-live.sh --check --zotero-source <absolute-zotero-checkout>
./scripts/sync-live.sh --validate --zotero-source <absolute-zotero-checkout>
```

`--check` is the runtime check; `--validate` is the explicit
installation transaction and requires the source tree to be committed. These
commands also use the package inventory and source-commit/payload hash for
content identity. They are not the ordinary offline source check and do not
install hooks automatically.

## Opt-in hooks and diagnostics

Hooks are separate user-owned runtime files and must be opted in for each CSE
repository:

```bash
python3 plugin/scripts/workflow/install_cse_hooks.py \
  --agent codex --repo <absolute-repository>
python3 plugin/scripts/workflow/install_cse_hooks.py \
  --agent codex --diagnose --repo <absolute-repository>
python3 plugin/scripts/workflow/install_cse_hooks.py --check
```

The installer writes the stable runtime under
`$HOME/.local/share/cse/hooks` and the repository registration under
`.codex/hooks.json`. It preserves unrelated configuration, replaces only
recognized CSE registrations, remains safe to repeat, and keeps the four
`SessionStart`, `SubagentStart`, `UserPromptSubmit`, and `Stop` events. A
changed installed runtime requires the explicit `--replace-runtime` guard.
Plugin availability, native registration, enabled state, active-session
loading, trust, and observed hook execution are separate claims; diagnose and
report only what was actually observed.
