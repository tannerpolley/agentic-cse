# Dependent scientific changes

Use these rules only for a real dependency, such as establishing one native
numerical owner before removing its predecessor. Keep an ordinary bounded change as one
standalone issue. Use one parent invariant and bounded leaf issues with exact
dependencies only for genuine ownership or proof order. Assign one accountable
owner per leaf and one writer per overlapping file. Work sequentially whenever
leaves overlap semantically or structurally.

## Reconcile and trace

Before issue publication or a Build handoff, inspect the live repository,
tracker, accepted scientific records and decisions, real callers and owners,
public behavior, retained evidence, and applicable validation commands. Remove
disproved premises. Preserve satisfied native dependency links as the record of
ordering; remove or replace a prerequisite only when it is genuinely obsolete
and current authority permits that relationship change.

For a material change to scientific ownership, equations, numerical methods,
state lifetime, language or process boundaries, retained evidence, or another
hard-to-reverse responsibility, trace:

```text
public input -> formulation or data owner -> numerical owner
             -> retained evidence -> public result
```

Name the current and intended owners, state lifetime, allowed dependency
direction, public behavior to preserve, and displaced paths.

A bounded issue is root-cause closed, not limited to named symptoms, files, or
diff hunks. For each changed scientific responsibility, trace the smallest
complete surface:

```text
public input -> validation or mapping boundary -> formulation and numerical owner
             -> result construction -> failure representation -> public output
```

Inspect the complete changed functions, direct callers and callees, alternative
owners of equations, constants, limits, defaults, results, and failure
meanings, transported fields and units, superseded routes, and the generator or
check boundary where the defect can recur. Include every correction needed to
restore accepted ownership, dependency direction, failure meaning, public
behavior, and physical limits. This does not authorize a new model, method,
owner, claim, or destructive action.

## Findings and authority

Every finding separates:

1. **Observed state:** direct source, call-graph, symbol, numerical, runtime,
   tracker, or retained-evidence inspection.
2. **Interpretation:** why that observation threatens scientific behavior,
   reproducibility, or maintainable ownership.
3. **Proposed correction:** the smallest remedy, subject to independent
   verification and user authority.

An observation may remain valid when its proposed correction is rejected.
Reviewer recommendations are hypotheses, not authority.

Obtain or cite current explicit user authorization before retiring, merging,
or replacing a distinct scientific algorithm or model; changing issue
dependencies or siblings; changing the scientific owner, governing equation,
or numerical method; removing a required dependency, precision path, or exact
representation; changing public scientific behavior, units, conventions,
branches, or safeguards; or materially changing an acceptance threshold
with a [named origin](numerical-testing.md#tolerances), evidence requirement, or
claim boundary. Relabelling an untraced limit as a target needs no
authorization. Present the evidence, recommended
choice, credible alternatives, and effects on scope and evidence. An
unconfirmed material choice returns **Block**. Restoring an already authorized
invariant needs no redundant confirmation unless the correction changes one of
these decisions.

## Bounded sequence

For each leaf:

1. implement and run proportional scientific validation in one isolated
   feature checkout;
2. obtain independent review against executable numerical claims and structural
   source, build, and link claims;
3. merge, validate the default branch, close the issue, remove the clean
   checkout, and clean merged branches before starting the next dependent leaf.

Before an expensive run, ask the explicit decision question it can answer and
run the cheapest discriminating check first. Record exact installed-distribution identity,
content hashes, commands, tolerances, hardware, worker count,
failures, rejected rows, and claim boundaries when they affect interpretation.
A measurement that does not justify a proposed optimization or dependency is
an accepted no-change outcome.
