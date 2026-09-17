# Code-surface review

Use this reference for Design, Build, and Review when scientific code is added,
repaired, replaced, or removed.

## Earn every addition

Treat every new executable line, symbol, wrapper, fallback, dependency,
configuration option, test, fixture, and public name as removable until a
specific equation, method, numerical risk, input/output requirement, retained
format, or identified external caller earns it.

For every material addition, record:

- file and responsibility;
- requirement that earns retention;
- superseded implementation, caller, wrapper, test, fixture, configuration, or
  explanation removed;
- why each removal is obsolete;
- executable lines added and removed, separate from tests, documents, and
  generated files.

## Agree the code budget

Before executable changes, Design records an issue-specific ceiling for gross
added lines in executable files, an explicit base commit, and the rationale
in the existing task or issue. Use the accounting report's executable additions,
including comments and blanks; report tests, documents, generated files, and
other changes separately. Inspect classification rather than hiding runtime
code in another category. There is no universal ceiling, minimum, or target
to fill. Deletions do not buy extra additions.

At the ceiling, or when an overrun is foreseeable, Build pauses further
additions and proposes the smallest revised ceiling. Account for all additions
already made and still proposed, grouped by responsibility: what is genuinely
new relative to the existing code, which accepted requirement needs it, and
why reuse or replacement cannot avoid it. Novelty means missing capability,
not an excuse to invent a new algorithm. Identify inspected alternatives and
remaining obsolete code. The user, or an explicitly delegated acceptance
authority other than the implementer, must approve the increase in the same
task or issue before further additions. Missing budgets follow the same
approval route; agents do not silently choose or raise their own ceiling.

Keep the base and counting scope fixed across commits and resumptions. If an
overrun is discovered late, disclose it and withhold Pass until approved or
reduced. Preserve readable code, safeguards, and useful evidence: compression,
comment stripping, unrelated deletion, and weaker checks cannot satisfy the
budget. Staying below it proves neither correctness nor complete replacement.

## Produce the accounting evidence

Build owns the one change-accounting run for work that changes executable code,
tests, configuration, or scripts. Run it against the final tree and active base
and include it in the Build handoff:

```bash
python3 scripts/workflow/change_accounting.py --repo <project-root> --base <base-ref>
```

Use `--json` when the report must be retained or consumed by another command.
The report includes committed, staged, unstaged, and untracked non-ignored
files from the resolved merge base. It separates executable code, tests,
documents, generated files, and other files; reports binary changes without
inventing line counts. Use the executable additions to compare with the
accepted budget; the script does not approve or enforce a ceiling.

Build reports its changed surface and focused validation. This command
measures change composition only; it does not decide whether an addition is
earned, a removal is relevant, or a generated path is correctly classified.
Rerun with an explicit `--base` whenever
automatic default-branch detection does not represent the active issue
boundary.

## Replace an owned lifecycle

For replacement work, put one concise statement in the existing task or issue:
**Owner** (where the responsibility remains), **Callers** (paths that must use
it), **Retirement** (what disappears and why removal is safe), and **Evidence**
(behavior and reference cases that must survive). Build reconciles the final
tree with that statement; no parallel record is required.

When diagnosis establishes that an implementation path is fundamentally
wrong, prefer one fresh canonical path. Remove the superseded implementation,
callers, wrappers, aliases, fallbacks, tests, fixtures, configuration,
documentation, and generated interpretation that it alone owned. Preserve
unrelated valid behavior in the same file.

Inspect beyond the diff for another owner of the same responsibility. One-call
wrappers, one-implementation abstractions, duplicate formulas or solvers,
unused public symbols, speculative configuration, test-only routes, and one
campaign's bounds or filenames in generic numerical code require concrete
retention evidence.

Protect justified equation traceability, units and bases, numerical stability,
physical safeguards, calibration, provenance, uncertainty, independent
reference methods, established domain libraries, required interfaces, and
retained formats. Minimal code must preserve scientific meaning and visible
failure behavior.

## Reconcile the implementation before Pass

Before Pass, compare the implementation with every acceptance condition, hard
removal, and non-goal in the active issue. Passing numerical or interface
checks cannot override a structural contradiction. Copied or renamed code
counts as retained code when it preserves the displaced owner's
responsibility or lifecycle.

When the correction is clear, authorized, and inside the accepted issue,
return Revise and continue through the existing Design and Build route without
an unnecessary user stop. Preserve passing evidence whose claim and
dependencies are unaffected. When correction would change ownership,
mathematics, safeguards, scope, or an acceptance condition, name the exact
contradiction and return Block or Revise to Design before implementation or a
completion claim.

## Semantic ownership pass

For every added or materially changed scientific execution path, Review checks:

- **Numerical ownership:** equations, derivatives, normalization, projection,
  unit conversion, and physical transformation run in the accepted owner;
  validation and mapping transport named values and do not reconstruct native
  calculations.
- **Result-field meaning:** every changed field has one named producer,
  meaning, unit or basis, and availability rule. Shared values across distinct
  fields require mathematical and semantic identity evidence; positional values
  trace to named meanings, and unavailable values are explicit.
- **Failure preservation:** every changed `break`, `continue`, early return,
  exception conversion, missing row, `None`, nonfinite value, or fallback is
  inspected. Unavailability retains its cause and valid diagnostics; mapping
  does not turn typed failure into omission or apparent success.
- **Single scientific owner:** repeated equations, derivatives, limits,
  constants, bounds, tolerances, and physical defaults trace to their owner;
  secondary views use that owner rather than inline repetition.
- **Executable falsification:** each changed scientific branch or failure
  transition has the smallest result-level check that can expose its loss.
  Success cases do not replace missing-input, boundary, conditioning, or
  failure-preservation cases. No helper-by-helper suite or prose parser is
  added.

Review examines complete changed functions and their direct callers and
callees. Line accounting is composition evidence only. A material executable
change is reviewed independently against an explicit merge base and one
identified final commit or frozen tree; the reviewer did not implement it and
uses primary source and execution evidence. Any implementation correction
invalidates the prior post-implementation Pass; after the last correction,
Review repeats the complete semantic ownership pass.

## Review result

For replacements, explicitly answer: **Did this replace the responsibility, or
add another implementation?** Cite the final owner, affected callers, retired
paths, and exact locations and reasons for any intentional retention. Renaming
or wrapping the old owner is not retirement. Check the accepted budget and
any approved increase independently of the structural conclusion.

- **Block:** unsupported science, numerical risk, unearned code surface, a
  prohibited test, or disagreement with the active issue.
- **Revise:** the objective remains valid, but Design must correct the accepted
  implementation route before Build proceeds. Update the active issue when
  ownership, mathematics, safeguards, scope, or required checks change.
- **Pass:** the issue, implementation, evidence, retained tests, and selected
  outputs agree for the stated use and domain.

Review reports exact findings and routes Block or Revise to Design. Design
corrects the route and updates the active issue when its accepted decisions
change. Build changes the implementation, Analyze regenerates affected
evidence, and Review runs again.
