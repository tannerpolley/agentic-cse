# CSE-Pi (Phase 3)

\`cse-pi run --task /absolute/work-order.json --result-dir /absolute/new-run-directory\` is a bounded, one-shot scientific worker. It preserves schema-version 1 \`investigate\` orders and supports schema-version 2 \`implement\`, \`analyze\`, and \`review\`.

All roles validate a frozen source identity, copy only assigned regular files, require Bubblewrap, disable network/host credentials in candidate shell commands, enforce deadlines/cancellation, and retain \`result.json\`, \`events.jsonl\`, command evidence, and hashes outside the source workspace.

Phase 3 roles:

- \`implement\` receives a frozen specification and writes through scoped candidate tools only. The source workspace stays untouched. The result retains a candidate copy, exact created/modified/deleted file hashes, and \`candidate.diff\`; the parent decides whether to apply anything.
- \`analyze\` executes bounded commands against a read-only snapshot and writes only exact file names declared in \`output_paths\` under the run's \`analysis/\` directory. Output is evidence, not a claim of scientific correctness.
- \`review\` starts a fresh read-only session and returns prioritized findings with evidence, impact, confidence, and blocking status. It cannot edit source or evidence.

Role defaults are provisional and benchmark-independent: implement uses \`openai-codex/gpt-5.6-luna/high\`, analyze uses \`openai-codex/gpt-5.6-terra/high\`, and review uses \`openai-codex/gpt-5.6-sol/high\`. A work-order \`worker\` override or \`CSE_PI_<ROLE>_{PROVIDER,MODEL,EFFORT}\` environment override is recorded in the result. Supported model identities are explicit; no live provider call is needed for \`--no-inference\` preflight.

Work orders provide an explicit model-turn budget. Results retain the exact termination reason and normalized token usage.

\`--no-inference\` is the deterministic validation path: it validates, snapshots, runs declared checks, and exits nonzero with \`preflight\`. Omit it only with an authorized supported Pi subscription. The runtime never resumes sessions, starts a daemon, applies candidate changes to the source, or claims parent acceptance.
