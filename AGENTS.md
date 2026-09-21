# CSE workspace

This directory is the `agentic-cse/cse` superproject. Each child project is a
Git submodule tracking its own `main`; a parent commit records the set of child
revisions that were validated together.

- `.github/` owns the GitHub organization profile and shared community files.
- `cse-plugin/` owns the existing CSE plugin and its Git history.
- `cse-pi/` is reserved for the independent headless scientific worker runtime.
- `cse-sciencebench/` is reserved for the private scientific benchmark.
- `cse-zotero/` owns the source-linked research and scientific data companion.

Before changing a child project, read its `AGENTS.md` when present and inspect
its actual repository root, branch, and working tree. Run repository commands
from that child directory. Keep each project's Git history independent: commit
and open pull requests in the child, then bump the submodule pointer here in a
separate parent commit once the child change is merged. Keep submodules on
`main` (`git submodule update --remote --merge`), never commit on a detached
HEAD inside one, and never stage this parent checkout into a candidate or
benchmark environment.

Keep the parent for cross-project planning and coordination. Runtime work belongs
in the owning child project. The former embedded CSE-Pi harness remains
recoverable from `cse-plugin` Git history.

Keep hidden benchmark answers and verifiers out of plugin and worker payloads
and out of benchmark candidate environments. Folder organization alone does not
provide that isolation.
