# Agentic CSE

This repository holds every Agentic CSE project in one Git history. Each folder
was a separate repository until 2026-10-21; its earlier history is preserved
under the folder, and the old repositories are archived.

- `cse-plugin/` owns the CSE plugin: skills, references, assets, packaging, and Setup.
- `cse-zotero/` owns the source-linked research and scientific data companion.
- `cse-pi/` owns the headless scientific worker runtime.
- `.github/` owns the issue and pull request templates and the shared contributing and security files.

Before changing a project, read its `AGENTS.md` when present and run its
commands from that folder. One branch, commit, or pull request may span several
folders when the change belongs together.

The private benchmark and its run base stay in their own repositories,
`tannerpolley/cse-sciencebench` and `tannerpolley/cse-workflow-benchmark`, so a
checkout of this repository never contains hidden answers or trusted
verifiers. Never copy benchmark material here, and never hand a checkout of
this repository to a benchmark candidate.
