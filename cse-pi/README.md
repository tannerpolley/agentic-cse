# CSE-Pi

cse-pi run --task /absolute/work-order.json --result-dir /absolute/new-run-directory is a bounded, one-shot implementation worker for schema-version 3 build orders.

The build worker validates a frozen source identity, copies only assigned regular files, requires Bubblewrap, disables network/host credentials in candidate shell commands, enforces deadlines/cancellation, and retains result.json, events.jsonl, command evidence, and hashes outside the source workspace.

The build worker receives a frozen specification and writes through scoped candidate tools only. The source workspace stays untouched. The result retains a candidate copy, exact created/modified/deleted file hashes, and candidate.diff; the parent decides whether to apply anything.

The provisional, benchmark-independent build default is openai-codex/gpt-5.6-luna/high. A work-order worker override or CSE_PI_BUILD_{PROVIDER,MODEL,EFFORT} environment override is recorded in the result. Supported model identities are explicit; no live provider call is needed for --no-inference preflight.

Work orders provide an explicit model-turn budget. Results retain the exact termination reason and normalized token usage.

\`--no-inference\` is the deterministic validation path: it validates, snapshots, runs declared checks, and exits nonzero with \`preflight\`. Omit it only with an authorized supported Pi subscription. The runtime never resumes sessions, starts a daemon, applies candidate changes to the source, or claims parent acceptance.
