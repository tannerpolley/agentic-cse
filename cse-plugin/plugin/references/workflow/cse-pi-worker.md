# CSE-Pi worker

CSE-Pi is an optional, independent, one-shot Build boundary. The owning CSE
Build stage supplies the accepted frozen specification and remains responsible
for candidate acceptance; worker output is evidence and never parent
acceptance.

## Build work order

Schema version 3 supports only role `build`. The existing CLI accepts optional
`--role build`; when present it must match the work order.

A Build order binds the task and scientific question, absolute workspace identity,
hashed context files, known context, constraints, non-goals, read and candidate
write paths with exact `write_scopes`, `write_policy: candidate`,
`network_policy: none`, expected artifacts, acceptance criteria, validation,
scientific checks, parent identity, bounded budgets, optional worker overrides,
and a frozen `specification` with required, forbidden, and permitted paths.
`budget.wall_timeout_ms`, `model_turn_limit`, `command_timeout_ms`, and
`output_bytes` bound wall time, model turns, command time, and retained output;
worker provider, model, and effort overrides remain explicit and recorded.

The parent computes task-file and scientific-check hashes from the source. Hashes
supplied by another worker are never trusted.

## Build profile

The worker receives the frozen specification in an isolated candidate copy and
uses only scoped candidate-write tools for declared paths. It retains candidate
files, operations, a unified evidence diff, and hashes outside the source
checkout; the parent independently inspects the candidate and decides whether
anything may be applied.

The default is `openai-codex/gpt-5.6-luna/high`. A work-order `worker`
override, `CSE_PI_BUILD_{PROVIDER,MODEL,EFFORT}`, or fallback
`CSE_PI_{PROVIDER,MODEL,EFFORT}` environment override is recorded as the
requested identity and validated against the supported provider, model, and
effort. These defaults are an operational convenience, not a model leaderboard.

Results retain the exact termination reason and normalized token usage.

## Trust isolation

The worker launcher uses Bubblewrap with no network and no host credentials.
Candidate shell commands see read-only `/workspace`; scoped candidate writes go
through named tools whose paths are checked against the frozen order. Traversal,
symlinks, hardlinks, special files, and administrative paths are rejected.
Worker execution never applies source edits.

The worker retains supervisor logs and byte-exact output hashes outside the
source workspace. The parent checks result, run, task, and parent identities,
then independently inspects candidate evidence and reruns important validation
before use. Cancellation, deadlines, and descendant cleanup remain bounded.

A completed worker means only that structured submission evidence was retained.
It does not establish parent acceptance or a scientific claim.

## Invocation

Both launchers run the same Build worker, tools, snapshot, Bubblewrap commands,
and retained evidence. Choose by host:

### Inside T3 Code

Use a visible T3 Code subagent when the host exposes `orchestrator_capabilities`
and `delegate_task`, and `orchestrator_capabilities` lists a Pi provider
instance whose launch arguments load CSE-Pi's `dist/t3-extension.js` (by
convention the instance id `cse-pi`). Call `delegate_task` with exactly this
shape:

```json
{
  "task": "/cse-build /absolute/path/to/work-order.json /absolute/path/to/new-evidence-directory",
  "target": {
    "providerInstanceId": "cse-pi",
    "model": "openai-codex/gpt-5.6-luna",
    "options": { "thinking": "high" }
  },
  "mode": "async"
}
```

`model` is the work order's worker provider and model joined as
`provider/model`, and `thinking` is its effort. Omit `role`: T3 Code prefixes
the task for any role other than `general`, so the child no longer receives
the `/cse-build` command. The CSE-Pi session blocks every tool except the
worker's own, so a malformed task runs no tools and writes no `result.json`.

Follow the child with `task_status` rather than a long synchronous wait. The
child may finish shortly before its evidence is complete; `result.json` is
written last, so wait for that file before inspecting the retained evidence.
If the child is terminal and no `result.json` appears within a minute, report a
failed delegation rather than waiting further.
A child whose model differs from the work order writes a failed `result.json`
without running. The extension setup is recorded in the CSE-Pi `README.md`.

### Without T3 Code

Run a complete hash-bound work order directly:

```text
cse-pi run \
  --task /absolute/path/to/work-order.json \
  --result-dir /absolute/path/to/new-evidence-directory \
  --no-inference
```

Add optional `--role build` when the caller wants the CLI to assert the order's
role. Use `--no-inference` for deterministic validation. Omit it only for an
explicitly authorized live run with a supported Pi subscription. The plugin
does not infer a sibling checkout or add a second launcher around the installed
CLI.

The plugin remains useful when CSE-Pi is unavailable: the parent continues
through the normal CSE Build route and reports bounded delegation failure. No
daemon, queue, UI, provider client, or mandatory delegation is introduced.

A live smoke run requires an already-authorized worker, model, and effort; it is not a validation substitute.
