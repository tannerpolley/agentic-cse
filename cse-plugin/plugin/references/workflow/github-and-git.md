# GitHub and Git

When a repository uses GitHub, its issues, Git, pull requests, remote rules, and current worktrees are authoritative. Do not create a parallel lifecycle store.

## GitHub issues

Use the installed `gh` CLI and its native commands. Inspect live help before assuming a flag or extension. Core support includes issue labels, milestones, Projects, types, parent relationships, blocking relationships, pull requests, and repository rules. Extensions may improve ergonomics but are never required for correctness.

For an issue-managed implementation, the issue body owns the complete current
plan: resolved scientific and architectural choices, existing owners,
implementation sequence, exclusions, checks, stop conditions, and progress.
Comments retain discussion, review findings, execution reports, and amendment
history. The accountable lead incorporates accepted amendments into the body
and removes superseded instructions so Build never assembles an active plan from
conflicting comments. Link precise equations, methods, decisions, and evidence
in their durable owners instead of copying a second editable scientific source.

Retrieve the exact repository and issue with `gh`, read the complete body and
relevant comments, and follow pagination. Do not proceed from search snippets,
truncated output, a previous agent summary, or an old local copy. A temporary
reading copy or publication draft stays untracked outside source; retain the
only draft when publication fails, and remove it after successful publication
and read-back. Record the captured body identity and implementation base in the
ordinary handoff, not a new plan database.

The current accountable task performs authorized issue writes; workers and
reviewers read the issue and return evidence. Keep the body current at meaningful start,
amendment, handoff, review, and completion points without commenting on every
tool call. Optional reviewer suggestions do not expand scope or acceptance until
accepted through the existing authority.

Standalone issues are normal. Use parent or sub-issue relationships only for genuine decomposition. Labels describe work and remain advisory; preserve existing labels and ask before creating a repository label set. Offer GitHub Projects during setup and explain that `gh auth refresh -s project` requires separate approval; never run it silently. A Project may add board fields such as Status and Priority across milestones; it never replaces the milestone section.

### Milestones

Milestones are a repository's standing sections: a small, constant set of
areas of the project where issues live. Hosts such as T3 Code list issues under
their milestone, sorted by milestone title.

- Every open issue belongs to one milestone through GitHub's native milestone
  field. Assign it when the issue is published; when no milestone fits, ask
  before creating one.
- Milestone titles are plain area names, such as `Thermodynamic Models`,
  `Column Solver`, `Manuscript`, or `Tooling`, with no number, category, or
  version prefix. A section stays open while the area exists, even when empty.
- The milestone description states the section's scope, the code paths or
  records it covers, and its exclusions.
- Issue titles state the work only. Do not prefix a category, component, or
  milestone such as `[Equilibrium]` or `M3:`; the milestone carries the grouping.
- Milestone titles carry no order. Native issue relationships own prerequisites.

Closed milestones and closed issue titles remain history and are not renamed.

Native dependency links record real prerequisites; parent relationships record
decomposition. Preserve satisfied links as ordering history and remove or
replace only genuinely obsolete prerequisites under current authority. A closed
cancelled issue, unreadable dependency, or closed-unmerged pull request does not
prove completion. Reconcile live readiness after relevant completion,
reopening, or relationship changes, using a repository's deterministic command
when one exists. Keep readiness, execution authority, scientific acceptance,
worker ownership, and integrated delivery distinct.

After every mutation, reread the issue, relationship, Project membership, pull request, or repository state. GitHub Actions and status checks are optional repository context unless the user names a specific check as acceptance evidence or branch rules require it.

## Synchronize before work

Discover the repository root, remotes, remote default branch, canonical checkout, current worktrees, and branch from live Git and GitHub state. Do not assume `origin` or `main`.

When repository guidance supplies the exact clean base and explicitly forbids
fetch, pull, merge, or other remote synchronization, treat the checked-out
commit as the captured base after verifying it locally. Create the feature
branch directly; the repository-specific prohibition overrides the general
synchronization sequence below.

Before capturing the implementation base:

1. fetch the primary remote with pruning;
2. require the canonical default-branch checkout to be clean;
3. fast-forward the local default branch to its remote-tracking branch with `git merge --ff-only`;
4. stop on dirty, ahead, diverged, detached, or ambiguous state;
5. create the feature branch or attached worktree from the synchronized commit;
6. verify command directory, task-visible checkout, branch, and recorded worktree agree.

Never reset, rebase, auto-stash, discard work, or branch from a stale local default to force preparation through.

## Integration authority

During opening alignment, record whether the endpoint includes commit, push, pull-request creation, merge, remote-head deletion, local branch removal, and worktree cleanup. Do not ask again when the exact approved conditions hold.

Private repositories without remote rules may use direct integration when selected. Public, collaborative, or protected repositories normally use a pull request. A remote rule that requires a pull request overrides a direct preference and must be reported.

Before direct integration, synchronize the clean default branch, run a nonmutating trial merge with `git merge-tree --write-tree`, perform the agreed scientific review, and use a squash merge when selected. Pull requests may merge independently; they need not be leaves or members of a larger set.

## Closeout

After GitHub confirms the pull request merged and the remote head is deleted:

1. fetch with pruning;
2. fast-forward the clean canonical default branch when safe;
3. run `git sync --delete` or a narrowly equivalent guarded cleanup only when cleanup authority exists;
4. remove only outcome-owned, clean merged worktrees and branches;
5. finish on the synchronized local default branch when the task controls that checkout.

Never delete the current branch, a default branch, a branch active in any worktree, a dirty or diverged branch, or an unverified branch. A squash or rebase merged branch may be force-deleted only when GitHub confirms the matching pull request merged. Preserve every skipped target and report why.

Git 2.43 has no native post-fetch hook. A post-merge hook cannot observe a remote GitHub merge. Keep synchronization explicit at construction and closeout.
