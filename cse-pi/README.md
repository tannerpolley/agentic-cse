# CSE-Pi

cse-pi run --task /absolute/work-order.json --result-dir /absolute/new-run-directory is a bounded, one-shot implementation worker for schema-version 3 build orders.

The build worker validates a frozen source identity, copies only assigned regular files, requires Bubblewrap, disables network/host credentials in candidate shell commands, enforces deadlines/cancellation, and retains result.json, events.jsonl, command evidence, and hashes outside the source workspace.

The build worker receives a frozen specification and writes through scoped candidate tools only. The source workspace stays untouched. The result retains a candidate copy, exact created/modified/deleted file hashes, and candidate.diff; the parent decides whether to apply anything.

The provisional, benchmark-independent build default is openai-codex/gpt-5.6-luna/high. A work-order worker override or CSE_PI_BUILD_{PROVIDER,MODEL,EFFORT} environment override is recorded in the result. Supported model identities are explicit; no live provider call is needed for --no-inference preflight.

Work orders provide an explicit model-turn budget. Results retain the exact termination reason and normalized token usage.

\`--no-inference\` is the deterministic validation path: it validates, snapshots, runs declared checks, and exits nonzero with \`preflight\`. Omit it only with an authorized supported Pi subscription. The runtime never resumes sessions, starts a daemon, applies candidate changes to the source, or claims parent acceptance.

## T3 Code subagent route

Inside T3 Code the same worker can run as a visible Pi subagent instead of a headless process. Build `dist/`, then add a Pi provider instance in T3 (Settings → Providers → Add provider instance → Pi) with instance id `cse-pi` and launch arguments `--extension /absolute/path/to/cse-pi/dist/t3-extension.js`. A parent delegates with `delegate_task` to that instance, using the work order's worker model and effort, `mode: "async"`, and the task `/cse-build /absolute/work-order.json /absolute/new-run-directory`.

The extension runs the unchanged Build worker in that session: only the CSE-Pi worker tools are active, commands still run in Bubblewrap, and the host's skills, context files and other tools are out of the prompt until the run ends. A child whose model differs from the work order records a failed result instead of running. `result.json` is written last and marks completion; the parent inspects the evidence exactly as after `cse-pi run`.
