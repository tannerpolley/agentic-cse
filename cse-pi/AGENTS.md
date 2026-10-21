# CSE-Pi worker runtime

This repository owns the independent, one-shot CSE-Pi scientific worker.
Keep the runtime separate from the CSE plugin and benchmark repositories.

- Preserve Bubblewrap isolation, bounded execution, frozen work orders, and
  retained evidence checks.
- Never add benchmark-private references, hidden answers, or verifier logic.
- Keep provider credentials outside the repository and worker payload.
- Run `npm run check` and `npm test` after changes. Build `dist/` locally; it is
  generated and not versioned.
