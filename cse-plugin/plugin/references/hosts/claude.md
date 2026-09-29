# Claude Code host reference

The CSE plugin is one shared payload for Claude Code and Codex. Claude Code
discovers the same 22 `cse:<skill>` skills, shared `references/`, and scientific
assets. This file records only Claude Code invocation, native interaction,
installation, and diagnostics; it does not copy skills or create generated
agents.

## Invoke and ask

Invoke a stage directly with `/cse:<skill>`, such as `/cse:setup` or
`/cse:review`. Use Claude Code's native structured question prompt for a
material choice about role, purpose, method, evidence, authority, or delivery.
If that native input is unavailable, report the missing capability and pause
only the dependent action.

Claude Code native subagents are optional execution tools. Use them only for
independently bounded work; they are not a required CSE phase, staffing policy,
or generated role definition. If unavailable, continue directly and report the
limitation when it matters.

## Instruction discovery

Claude Code discovers plugin skills from the plugin's native metadata and
project guidance from `CLAUDE.md`. Preserve existing guidance and ensure the
repository root `CLAUDE.md` contains the native import:

```text
@AGENTS.md
```

That import is required before claiming automatic loading of the shared
`AGENTS.md` guidance. A plugin listing does not by itself prove that the
current task loaded the plugin, trusted the repository, or activated hooks.

For disposable local development, load the source directory in place from
the root of a cse-plugin source checkout:

```bash
claude --plugin-dir <absolute-repository>/plugin
claude --plugin-dir plugin plugin details cse@inline
```

The `plugin details` result is the CLI-observed source root and skill
discovery. Hash the observed `plugin/` content for source comparison; do not
require Codex's deployment-root identity file for an inline or local-directory
load.

## Install and update

The repository root contains the native local marketplace catalog. From the
checkout's parent or with its absolute path, use Claude Code's marketplace
commands:

```bash
claude plugin marketplace add <absolute-repository>
claude plugin install cse@cse
claude plugin marketplace update cse
claude plugin update cse@cse
claude plugin list --json
claude plugin marketplace list --json
```

The catalog's only entry is the local `./plugin` source. A local source can be
observed in place during development without reinstalling; an installed
marketplace copy still needs the host's update command when that is how it is
loaded. `claude plugin validate plugin --json`, run from the source checkout
root, is a native metadata check;
version or author warnings do not authorize adding release numbers to the CSE
manifests.

## Opt-in hooks and diagnostics

Hooks are separate user-owned runtime files and an explicit opt-in. Register
them once at user level (`--user`): they then run in every CSE repository and
worktree and stay silent outside a repository with `docs/scientific/CONTEXT.md`.
A repository registration (`--repo`) remains supported; do not keep both, or
each hook runs twice (`--remove` drops CSE registrations only). Run the
installer from the installed plugin root (the directory containing `skills/`);
from a cse-plugin source checkout, prefix the path with `plugin/`:

```bash
python3 scripts/workflow/install_cse_hooks.py --agent claude --user
python3 scripts/workflow/install_cse_hooks.py \
  --agent claude --remove --repo <absolute-repository>
python3 scripts/workflow/install_cse_hooks.py \
  --agent claude --diagnose --repo <absolute-repository>
python3 scripts/workflow/install_cse_hooks.py --check
```

The installer writes the stable runtime under
`$HOME/.local/share/cse/hooks` and the repository registration under
`.claude/settings.json`. It preserves unrelated configuration, removes only
recognized CSE registrations, keeps each handler's `statusMessage`, remains
safe to repeat, and keeps the four `SessionStart`, `SubagentStart`,
`UserPromptSubmit`, and `Stop` events. A changed installed runtime requires
the explicit `--replace-runtime` guard. Plugin discovery, native registration,
enabled state, active-session loading, trust, and observed hook execution are
separate claims; installed files and registrations do not prove host trust or
observed execution. For the exact fresh-session check, close the current
Claude Code session, open a new session in the repository with the plugin
loaded, and verify that `SessionStart` prints the CSE stance with the repository
role, confirmed agent role, and the `AGENTS.md` CSE Protocol pointer.
