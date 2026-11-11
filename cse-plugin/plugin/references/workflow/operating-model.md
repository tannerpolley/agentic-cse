# Operating model

CSE owns the work from the invoked workflow stage or supporting tool to the
endpoint selected by the investigator. Public skills form one workflow spine;
supporting tools serve that spine and do not replace it.

## Smallest sufficient route

Use the smallest clear route that supports the scientific claim and reaches the
investigator's endpoint. Reuse an
existing skill, reference case, standard-library or native capability before
adding code, records, dependencies, or outputs. Keep evidence, validation,
provenance, uncertainty, failure meaning, and data safety when simplifying.

The two execution phases and independent Review checkpoints are:

```text
Research and design -- readiness Review --> Execute and deliver -- delivered Review --> endpoint
        ^                    | Revise/Block              | Not supported
        +--------------------+----------------------------+
```

Research and design contains Setup when needed, Research, Diagnose, and Design.
It loops until the question, equations, and numerical falsifier are settled;
nothing is built there. Execute and deliver contains Build, Analyze, Summarize,
and authorized Write and delivery. These are ownership groupings, not a demand
to run every stage. Review independently checks design readiness before Build
and delivered results or capabilities afterward. Audit and Prose are supporting
tools, not execution phases.

Direct tool requests return to the stage that owns the question or claim.

All 19 `cse:<skill>` skills are exposed by one plugin. Source skills supply
evidence, rendering skills consume retained values or supported claims, and
Prose inspects scientific writing without authoring it.
Inspect the requested external capability; never infer Zotero, corpus,
authentication, or renderer readiness from package presence, and never inspect
plugin caches. Any stage that finds a relevant paper missing from the project's
Zotero library adds it through `cse:zotero`
[acquisition](../sources/zotero-companion.md#writes-acquisition-and-bibliography)
without asking.

## Coordinate work across stages

Direct execution is the default: keep the accountable lead in the current task and
continue through the applicable stages. Use native host delegation for bounded
independent work when useful, and follow the host's return and wait behavior.
No fixed role hierarchy or separate coordination records are required.

CSE owns its scientific stages, evidence, and acceptance. Design and Review
retain their specialized safeguards; no generic coordination rule replaces them.

The current accountable task owns authorized Git and tracker writes. Helpers
read the accepted Design handoff and return findings and evidence to that task. Activate
[github-and-git](github-and-git.md) for issue, branch, or delivery work.

For host-specific invocation, native structured questions and subagents,
instruction discovery, installation, and diagnostics, read the applicable
[Codex host reference](../hosts/codex.md) or
[Claude Code host reference](../hosts/claude.md). The shared
workflow remains host-independent and does not require the other host or a
host-specific coordination wrapper.

## Explore and Promote

Use **Explore** for disposable calculations, scratch notes, rejected methods,
and short-lived branches that compare formulations, methods, initializations,
or solver settings. Explore supports no accepted claim, persistent test, or
analysis research notebook. Remove rejected implementations and
disposable checks when the question is answered.

Use **Promote** when a selected formulation, method, result, record, or test
becomes durable. Promotion requires the applicable Design, Build, Analyze,
Summarize, and delivered Review evidence. A persistent
repository test is Promote work even when it began as an exploratory check.
Explore and Promote are evidence boundaries, not additional workflow stages.

## Instruction strengths

- **Must — invariant:** preserve authority, scientific validity, provenance,
  units, uncertainty, failure meaning, review boundaries, and
  approved remote or destructive-operation controls.
- **Should — default:** use the stated route, review method, output format,
  rendering backend, and verification depth unless repository evidence or
  intended use supports an equivalent route with the same safeguards.
- **May — option:** add specialist tools, reviewers, records, bibliography
  operations, formats, or extended analyses when the question or repository
  requires them.

## Decision frontier, handoff, and reference reuse

Each skill's frontmatter declares a small `cse-routing.direct` reference list
and named `cse-routing.conditional` identifiers. The skill body states the
trigger for every conditional identifier. Read only the direct list on entry,
then activate a conditional reference when its trigger is present. Prefer the
section that owns the decision over a whole-file read.

At every Setup, Research, Diagnose, or Design entry, finish all currently
authorized independent inspection before presenting questions. Inspect
discoverable repository guidance, scientific context, equations, results, and
Git state yourself. Present the complete currently answerable consequential
choices together, with recommendations and enough scientific context to decide,
using native structured input for bounded choices; split questions only for a
real tool limit or dependency. Ask only when an answer changes scientific
meaning, scope, method, evidence, authority, or the next action. If no material
choice remains, continue without a ritual question. Obtain confirmation before
a nontrivial mutation unless the request already grants that authority.

Before the first scientific write, state the selected starting stage and one
sentence explaining why it owns the unresolved question. Use approved defaults
and recorded assumptions for bounded experiments; stop only when a missing
decision would make the result undefined, unsafe, or unauthorized.

When a question pauses the interface, pause only the affected route, retain
independent findings, and resume that route from the answer. Do not promise
simultaneous work while waiting, reopen settled facts, or invent questions. An
internal CSE handoff inherits the confirmed question, assumptions, repository
role, scope, endpoint, authority, and choices. Ask only delta questions
justified by new evidence or a new decision. It must not reread an unchanged
shared reference merely because the receiving skill links it. Reread when the
relevant decision changed, conversation compaction made the rule unavailable, the
reference changed, or the next stage needs an unused section. This reuse is
local to one task; each readiness or delivered reviewer independently loads the
references needed for its assigned risk lens.

Specialist handoffs inherit units or basis, uncertainty, provenance, authority,
claim limits, and approval state. Source skills return exact evidence and QA
state without judging the claim. Rendering skills return exact sources, commands,
outputs, same-source comparisons, visual checks, and limitations without running
the scientific model. Every material output returns to Review.

## Continuation and investigator promotion

Continue through the stages needed for the selected endpoint. Stop for a
material decision, missing authority, unavailable required input or tool, unsafe
Git state, or an unresolved scientific contradiction. Report the evidence,
limitation, and smallest next decision.

A missing external capability is a capability limitation, not a scientific
failure. When a source or rendering capability is required, name the missing
executable, corpus, authentication, or renderer, give the setup step needed,
and stop before making an unsupported claim.

Summarize creates or refreshes the working notebook only after a useful
method-specific numerical result exists, then renders selected views without
rerunning the model. Delivered Review inspects that complete notebook and those
views. Review Pass is bounded to the stated use and domain, and material changes
to the result, notebook, figure, method, or interpretation require Review again.

Review does not authorize manuscript use. Immediately before Write uses a
reviewed notebook, the investigator confirms the exact notebook commit,
intended use, and limitations. Record that promotion in one plain sentence;
do not create a status file or decision record.

## Language and repository boundaries

Activate `terminology` (`references/workflow/terminology.md`) and `BANNED` (`BANNED.md`)
for durable CSE-authored scientific prose,
issues, figures, notebooks, manuscripts, and review records. Routine inspection,
questions, commands, and terse progress updates need not load the
full language references unless they create durable prose or the relevant rule
is in question.

Keep CSE self-contained. Never substitute a generic workflow family. Separate
where work runs from where changes are tracked: a private Git remote, issue,
pull request, or branch rule does not imply public users, deployment,
compatibility support, or release work. Preserve repository and user authority
for all remote and destructive actions.
