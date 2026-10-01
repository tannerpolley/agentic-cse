# CSE-Pi

`cse-pi run --task /absolute/work-order.json --result-dir /absolute/new-run-directory` is a bounded, one-shot implementation worker for schema-version 3 build orders.

The worker creates a detached Git worktree at the frozen commit under `<result-dir>/worktree`, verifies the assigned read-file identity there, and removes the worktree after retaining evidence. It touches only the source repository's temporary worktree registry, not source checkout files. There is no input copy, candidate staging, or read-scope file/directory/depth cap.

Commands run in Bubblewrap with no network or host credentials, the worktree read-write at its absolute path, the common Git directory and declared dependencies read-only, and disposable tmpfs `/tmp` and `HOME`. Existing `.vite` and `.vite-temp` dependency cache directories receive disposable tmpfs overlays; dependencies themselves never become writable. The worker never installs dependencies.

The frozen specification, model/effort, deadlines, cancellation and budgets remain authoritative. Tools are `cse_run_command`, `cse_edit` (Pi exact-text replacement semantics), `cse_write` (create/overwrite one file), `cse_run_check` (declared check by id), and `cse_submit_result`. Pi built-in tools stay disabled. Edit/write paths must be regular non-symlink files inside explicit write scopes; `.git`, dependencies, forbidden paths and symlink ancestors are refused.

The candidate is the worktree diff against the frozen commit, including non-ignored untracked files. The evidence bundle retains `result.json`, `events.jsonl`, byte-exact command output, `candidate.diff`, changed-file after-content under `candidate/`, and before/after hashes. Any changed path outside the write scope or within forbidden/dependency paths fails with `scope_violation`; the diff is still retained. The parent decides what to apply.

The provisional, benchmark-independent build default is openai-codex/gpt-5.6-luna/high. A work-order worker override or CSE_PI_BUILD_{PROVIDER,MODEL,EFFORT} environment override is recorded in the result. Supported model identities are explicit; no live provider call is needed for --no-inference preflight.

Work orders provide an explicit model-turn budget. `output_bytes` bounds the result and each command's output, not worktree capacity or source size. Results retain the exact termination reason, `started_at`, `ended_at`, `wall_ms`, `worktree_commit`, `model_requests` independent of truncated runtime events, check results, and normalized token usage on both routes.

## Schema-v3 additions

- Required `workspace.commit`: a full lowercase 40- or 64-hex commit id, verified with `git rev-parse --verify <id>^{commit}`.
- Optional `workspace.dependency_paths`: relative directories in the source checkout. Each must exist, be ignored by Git, contain no tracked files, and have no symlink path components. They are mounted read-only at the same relative worktree paths.
- `scientific_checks` also accepts `{ "id": "suite", "kind": "command", "command": "npm test", "timeout_ms": 60000 }`; `timeout_ms` is optional (100–3,600,000 ms), capped by the command and remaining wall budgets. Check ids must be unique. Existing `json`, `convergence` and `plot_metadata` checks keep their fields and run against worktree paths.

`workspace.expected_identity` is unchanged: SHA-256 of sorted `path\0sha256` entries joined with `\n`, computed over the `read_paths` files in the frozen worktree. `access.write_paths` and matching explicit `access.write_scopes` still define permitted files/directories.

The worker can run checks during implementation. After submission the supervisor runs every declared check once on final worktree content; those recorded runs determine the final check results. Failed final checks fail a model run.

`--no-inference` creates the worktree, verifies identity, runs and records declared checks, retains evidence, and removes the worktree without authentication or model execution. It exits nonzero with `preflight` even when checks pass; failing checks are recorded without claiming acceptance. Omit it only with an authorized supported Pi subscription. The runtime never resumes sessions, starts a daemon, applies candidate changes to the source, or claims parent acceptance.

## T3 Code subagent route

Inside T3 Code the same worker can run as a visible Pi subagent instead of a headless process. Build `dist/`, then add a Pi provider instance in T3 (Settings → Providers → Add provider instance → Pi) with instance id `cse-pi` and launch arguments `--extension /absolute/path/to/cse-pi/dist/t3-extension.js`. A parent delegates with `delegate_task` to that instance, using the work order's worker model and effort, `mode: "async"`, and the task `/cse-build /absolute/work-order.json /absolute/new-run-directory`.

The extension runs the unchanged Build worker in that session: only the CSE-Pi worker tools are active, commands still run in Bubblewrap, and the host's skills, context files and other tools are out of the prompt until the run settles. Load it only in the dedicated instance: it blocks every other tool call in that Pi session, so a prompt that is not a well-formed `/cse-build` gets no tools. A child whose model differs from the work order records a failed result instead of running. A successful `cse_submit_result` settles the run even if Pi later emits plain final text. Usage is read from new entries in Pi's session manager, including retries and compaction, excluding earlier host work. `result.json` is written last and marks completion; the parent inspects the evidence exactly as after `cse-pi run`.
