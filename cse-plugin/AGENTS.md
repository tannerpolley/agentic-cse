# Agentic Computational Science and Engineering plugin repository

This repository is the canonical source for the `cse` plugin, whose official
name is Agentic Computational Science and Engineering.

- Keep public skills thin and place shared doctrine under `references/`.
- Keep CSE self-contained. Do not add runtime dependencies on another workflow or skill family.
- Use scientific language: questions, equations, methods, reference cases, numerical behavior, uncertainty, evidence, interpretation, and claims.
- Reject generic coverage targets and helper-by-helper test expansion. Tests protect front-door behavior, scientific doctrine, installation, and destructive-operation safeguards.
- Keep the issue tracker and live Git state authoritative. Do not create a lifecycle database.
- Standalone issues are normal. Every open issue belongs to one milestone under the shared milestone convention, reconciled by Setup; labels, Projects, issue relationships, and Actions remain optional repository context.
- Match validation to the requested scope and honor explicit test waivers; report checks not run. Model-backed workflow and routing evaluation is owned by tannerpolley/cse-sciencebench and is never part of plugin validation.
- Identify delivered plugin content by source commit and payload hash, not release numbers. No version bump, release tag, or benchmark score is required for merge. Verify installation when deployment is requested and run the cleanup audit after changes.

Do not edit deployed copies or plugin caches. Edit this source checkout and use the supported sync script.
