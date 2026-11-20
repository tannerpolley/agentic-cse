# Rendering guide

Rendering skills consume retained values and selected document sources. They
do not run scientific models, mutate retained results, or decide scientific
claim support.

For manuscript/deck sources and associated figures, follow the
[standing editorial decision protocol](../workflow/scientific-writing.md#standing-editorial-decisions)
before editing; build-only invocations read applicable decisions without
inventing or rewriting them.

Report the actual renderer, source paths, outputs, checks, warnings, and
limitations. A missing renderer is a specific capability error with the
setup step needed to resolve it.

## Release build verification

A release is a manuscript/deck and its configured companions handed back as
current or ready for use, not a software tag. Label requested partial previews
as partial; do not expand them into releases. Preserve project engines, classes,
bibliography processors and build routes. Rendering does not authorize scientific
calculations, toolchain replacement or pin repairs.

1. **List outputs.** Read repository instructions, build configuration/entry
   points and available document pins. List sources, formats, final paths and
   companion parts/supplements. Account for every configured output and map each
   relevant pin, reporting stale/unmapped pins. Pins cannot override configuration
   or add unrelated documents. A one-output wrapper proves only that member;
   report omissions, use other established commands where authorized, and ask
   for a decision on ambiguous membership.
2. **Build.** Inspect imports and presentation preparation for model execution
   before using the established route with retained inputs. Capture command,
   working directory, actual renderer/TeX engine and version, class and bibliography
   processor. Stabilize cross-document references by the project's procedure.
   Keep final logs through verification and recording, before optional cleanup.
3. **Check freshness.** Require every output to be nonempty and strictly newer
   than its actual inputs: included/imported text, bibliography, local styles,
   classes/configuration, figures/tables and their retained preparation inputs.
   Reuse project checks; fill coverage gaps from configuration and dependency
   records such as `.fls`, excluding generated auxiliaries/outputs. Root-source
   checks or repository-wide timestamp sweeps are insufficient. Missing/incomplete
   dependencies, equal/coarse timestamps or clock inconsistencies leave freshness
   unverified. Never touch files to pass; hashes do not replace freshness evidence.
4. **Read final diagnostics.** Reject build errors, unresolved citations/references
   and remaining rerun requests in each output's final TeX, bibliography and
   applicable Quarto diagnostics, not obsolete first-pass warnings. Missing final
   diagnostics are unverified. Fix every overfull horizontal/vertical box or
   record its exact log/source/page locator and specific visual justification;
   no blanket ignores or point-size allowances. Apply the
   [font and visual checks](latex-layout-and-qa.md#release-sequence).
   For `.pptx` outputs, use the `pptx` skill to validate the file, generate thumbnails, and inspect slides at full size (if missing, install with `npx skills add https://github.com/anthropics/skills --skill pptx -g`).
5. **Check pins.** Discover the host's listing capability; in T3 use
   `t3_project_artifacts_list` for the relevant project and inspect resolved paths,
   existence and checkout. A worktree PDF cannot validate a main-checkout pin.
   Each document pin must resolve to a verified output; copies need matching hashes
   and freshness evidence. Report exact pins/paths for missing, obsolete,
   wrong-checkout or differing files. Elsewhere use the host equivalent or existing
   inventory. Record no pins or unavailable access honestly; a known relevant pin
   left unchecked makes verification incomplete. Do not require T3 installation.
6. **Keep one build record.** Extend the existing record or place Markdown beside
   final outputs in the established build directory. Include build time, source
   commit/dirty state and changed/untracked input identities, command/directory,
   output paths/hashes, freshness evidence, final logs/results, overfull explanations,
   visual evidence and pin results. Identify bibliography and retained data by
   paths/hashes or a hashed immutable inventory. Link provenance rather than copy
   result tables: record the scientific engine version/source commit/wheel hash
   from retained-result provenance, separately from TeX and never from the installed
   environment. Where one wheel is required, trace all calculated material to it;
   mixed/missing identities remain unresolved, without relabeling or recalculation.
   Give reasons for non-applicable inputs. Unresolved checks mean failed/partial,
   never release success.

Minimal record shape (replace placeholders with evidence):

```text
Status: <verified | partial | failed>; built: <UTC time>
Source: <commit>; dirty inputs: <none | paths + hashes>
Build: <cwd>; <command>; renderer/TeX: <version>; class: <class>; bibliography: <processor>
Outputs: <each path + hash>; freshness: <dependency inventory + check evidence>
Inputs: <bibliography/data paths + hashes | hashed immutable inventory | N/A + reason>
Science: <retained provenance link: engine version, commit, wheel hash | N/A + reason>
QA: <final log paths/results>; overfull: <none | locators + explanations>; visual: <evidence>
Pins: <each pin + resolved path + result | none | access limitation>
```
