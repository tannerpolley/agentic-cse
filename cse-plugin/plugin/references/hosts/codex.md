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

Codex reads the same native local marketplace catalog at the repository root as
Claude Code. Install CSE as `cse@cse` with the checkout's absolute path:

```bash
codex plugin marketplace add <absolute-repository>
codex plugin add cse@cse
codex plugin list --json
codex plugin marketplace list --json
```

The catalog's only entry is the local `./plugin` source. Codex copies it into
its plugin cache, so rerun `codex plugin add cse@cse` to refresh the cache
after the source changes. Do not install a second copy through another
marketplace.

From the root of a cse-plugin source checkout (not from the installed plugin),
`sync-live.sh` wraps that install with the Zotero runtime and checks:

```bash
./scripts/sync-live.sh --check --zotero-source <absolute-zotero-checkout>
./scripts/sync-live.sh --validate --zotero-source <absolute-zotero-checkout>
```

`--check` builds and checks the Zotero runtime without changing host state.
`--validate` requires a committed source tree, installs the Zotero runtime,
runs the two commands above, and verifies that `cse@cse` is enabled from this
checkout with a current cache. On failure it restores the prior Zotero runtime
and removes a marketplace or `cse@cse` install it created; an existing
`cse@cse` keeps the refreshed cache because a local marketplace keeps no prior
copy. Both modes report the source commit and payload hash for content
identity. They are not the ordinary offline source check and do not install
hooks automatically.

## Opt-in hooks and diagnostics

Hooks are separate user-owned runtime files and an explicit opt-in. Register
them once at user level (`--user`): they then run in every CSE repository and
worktree and stay silent outside a repository with `docs/scientific/CONTEXT.md`.
A repository registration (`--repo`) remains supported; do not keep both, or
each hook runs twice (`--remove` drops CSE registrations only). Run the
installer from the installed plugin root (the directory containing `skills/`);
from a cse-plugin source checkout, prefix the path with `plugin/`:

```bash
python3 scripts/workflow/install_cse_hooks.py --agent codex --user
python3 scripts/workflow/install_cse_hooks.py \
  --agent codex --remove --repo <absolute-repository>
python3 scripts/workflow/install_cse_hooks.py \
  --agent codex --diagnose --repo <absolute-repository>
python3 scripts/workflow/install_cse_hooks.py --check
```

The installer writes the stable runtime under
`$HOME/.local/share/cse/hooks` and the repository registration under
`.codex/hooks.json`. It preserves unrelated configuration, replaces only
recognized CSE registrations, remains safe to repeat, and keeps the four
`SessionStart`, `SubagentStart`, `UserPromptSubmit`, and `Stop` events. A
changed installed runtime requires the explicit `--replace-runtime` guard.

Codex never runs a hook that lacks persisted trust, and T3 Code has no hook
review screen. After registering, the installer therefore asks `codex
app-server` (`hooks/list`, then one `config/value/write` upsert under
`hooks.state`) to record trust for exactly the CSE hooks it wrote to the
repository's `.codex/hooks.json`, and prints which it trusted. It never trusts
other hooks. Codex also ignores project hooks until the project itself is
trusted in Codex. Trust is recorded in the `CODEX_HOME` of the `codex` CLI the
installer runs (`CSE_CODEX_BIN` selects it), so run it with the same Codex home
the agents use. Trust is keyed by the absolute path of `.codex/hooks.json`, so a
separate worktree checkout needs its own trust. If the `codex` CLI is missing, the call fails or times out
(30 s), or Codex lists no CSE hooks, the registration stays and the installer
warns that Codex will skip the hooks until trusted (for example with `/hooks`
in the Codex TUI). `--diagnose` reports `codex_hook_trust` (`trusted`,
`untrusted`, or `unknown` when Codex is unavailable) without changing anything.
It checks the effective registration, the repository's `.codex/hooks.json`
when present and otherwise the user-level `.codex/hooks.json` under `--home`,
and names that file as `source`.

Plugin availability, native registration, enabled state, active-session
loading, trust, and observed hook execution are separate claims; installed
files and registrations do not prove observed execution. For the
exact fresh-session check, open a new Codex session in the repository, run
`/hooks`, and verify that `SessionStart` prints the CSE stance with the
repository role, confirmed agent role, and the `AGENTS.md` CSE Protocol
pointer.
