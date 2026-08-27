# Agentic Computational Science and Engineering plugin repository

This repository is the canonical source for the `cse` plugin, whose official
name is Agentic Computational Science and Engineering.

- Keep public skills thin and place shared doctrine under `references/`.
- Keep CSE self-contained. Do not add runtime dependencies on another workflow or skill family.
- Use scientific language: questions, equations, methods, reference cases, numerical behavior, uncertainty, evidence, interpretation, and claims.
- Reject generic coverage targets and helper-by-helper test expansion. Tests protect front-door behavior, scientific doctrine, installation, and destructive-operation safeguards.
- Keep GitHub issues and live Git state authoritative. Do not create a lifecycle database.
- Standalone issues are normal. Labels, milestones, Projects, issue relationships, and Actions remain optional context.
- Before reporting a plugin revision complete, run `./scripts/validate.sh`, commit, run `./scripts/sync-live.sh --validate`, install from the personal marketplace, verify the installed version, run the cleanup audit, and report every failed or skipped check.

Do not edit deployed copies or plugin caches. Edit this source checkout and use the supported sync script.
