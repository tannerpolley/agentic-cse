# Git, issue tracking, and delivery

The repository's tracker is the one provided by the Git host named in `origin`:
use `gh` for GitHub and `fj` for Forgejo. For another host, inspect its live
command help before using its tracker. If no tracker exists, Design presents
the complete plan in the conversation; the investigator's acceptance there is
the handoff, and the commit message records the question, reference case,
tolerance and its origin for a correctness check, and comparisons for agreement
with data. Create no additional record file or lifecycle store.

## Issue plans

When a tracker exists, its issue body owns the complete current plan: settled
scientific and architectural choices, owners, implementation sequence,
exclusions, checks, stop conditions, and progress. Comments retain discussion,
review findings, execution reports, and amendment history. The accountable lead
incorporates accepted amendments into the body and removes superseded
instructions so Build does not assemble an active plan from conflicting
comments. Link equations, methods, decisions, and evidence in their durable
owners rather than copying a second editable scientific source.

Retrieve the exact repository and issue with the host command, read the complete
body and relevant comments, and follow pagination. Do not proceed from search
snippets, truncated output, a previous agent summary, or an old local copy. A
temporary reading copy or publication draft stays untracked outside source;
retain the only draft when publication fails, and remove it after successful
publication and read-back. Record the captured body identity and implementation
base in the ordinary handoff, not a new plan database.

The accountable task performs authorized tracker writes; workers and reviewers
read the issue and return evidence. Keep the body current at meaningful start,
amendment, handoff, review, and completion points. Optional reviewer suggestions
do not expand scope or acceptance until accepted through the existing
authority.

Standalone issues are normal. Use parent or sub-issue relationships only for
genuine decomposition. Labels describe work and remain advisory; preserve
existing labels and ask before creating a repository label set. Tracker
features such as issue types, Projects, blocking relationships, and repository
rules are optional. Inspect live help before using them; request any required
new permission before changing credentials. A Project may add board fields such
as Status and Priority, but does not replace milestone ownership.

### Milestones

Milestones are a repository's standing sections: a small, constant set of
project areas where issues live.

- Every open issue belongs to one milestone through the host's native field.
  Assign it when published; when no milestone fits, ask before creating one.
- Titles are plain area names, such as `Thermodynamic Models`, `Column Solver`,
  `Manuscript`, or `Tooling`, without number, category, or version prefixes.
  A section stays open while the area exists, even when empty.
- The description states the section's scope, covered code paths or records,
  and exclusions.
- Issue titles state the work only. The milestone carries the grouping.
- Milestone titles carry no order. Native issue relationships own prerequisites.

Closed milestones and issue titles remain history and are not renamed.

Native dependency links record real prerequisites; parent relationships record
decomposition. Preserve satisfied links as ordering history and remove or
replace only genuinely obsolete prerequisites under current authority. A closed
cancelled issue, unreadable dependency, or closed-unmerged pull request does
not prove completion. Reconcile live readiness after relevant completion,
reopening, or relationship changes, using a repository's deterministic command
when one exists. Keep readiness, execution authority, scientific acceptance,
worker ownership, and integrated delivery distinct.

After every mutation, reread the issue, relationship, Project membership, pull
request, or repository state. Automated checks are optional repository context
unless the investigator names one as acceptance evidence or branch rules
require it.

## Synchronize before work

Discover the repository root, remotes, remote default branch, canonical
checkout, current worktrees, and branch from live Git and origin-host state. Do
not assume `origin` or `main` exists.

When repository guidance supplies the exact clean base and explicitly forbids
fetch, pull, merge, or other remote synchronization, treat the checked-out
commit as the captured base after verifying it locally. Create the feature
branch directly; that repository-specific prohibition overrides the general
synchronization sequence below.

When no remote exists, verify the intended local base and clean checkout from
live Git state, then create the feature branch or attached worktree from that
local commit. Keep the accepted conversation handoff and delivery local; create
no additional record store. Verify command directory, checkout, branch, and
recorded worktree agree.

When a remote exists, before capturing the implementation base:

1. Fetch the primary remote with pruning.
2. Require the canonical default-branch checkout to be clean.
3. Fast-forward the local default branch to its remote-tracking branch with
   `git merge --ff-only`.
4. Stop on dirty, ahead, diverged, detached, or ambiguous state.
5. Create the feature branch or attached worktree from the synchronized commit.
6. Verify command directory, task-visible checkout, branch, and recorded
   worktree agree.

Never reset, rebase, auto-stash, discard work, or branch from a stale local
default to force preparation through.

## Integration authority

During opening alignment, record whether the endpoint includes commit, push,
pull-request creation, merge, remote-head deletion, local branch removal, and
worktree cleanup. Do not ask again when the exact approved conditions hold.

Private repositories without remote rules may use direct integration when
selected. Public, collaborative, or protected repositories normally use a pull
request. A remote rule that requires a pull request overrides a direct
preference and must be reported.

Before direct integration, synchronize the clean default branch, run a
nonmutating trial merge with `git merge-tree --write-tree`, perform the agreed
scientific review, and use a squash merge when selected. Pull requests may merge
independently; they need not be leaves or members of a larger set.

## Closeout

After the host confirms the pull request merged and the remote head is deleted:

1. Fetch with pruning.
2. Fast-forward the clean canonical default branch when safe.
3. Run `git sync --delete` or a narrowly equivalent guarded cleanup only when
   cleanup authority exists.
4. Remove only outcome-owned, clean merged worktrees and branches.
5. Finish on the synchronized local default branch when the task controls that
   checkout.

Never delete the current branch, a default branch, a branch active in any
worktree, a dirty or diverged branch, or an unverified branch. A squash- or
rebase-merged branch may be force-deleted only when the host confirms its
matching pull request merged. Preserve each skipped target and report why.

Git hooks do not report host-side merges. Keep synchronization explicit at
construction and closeout.
