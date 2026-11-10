# Science findings for a retrospective

For a requested `/retro` session retrospective, include these categories
alongside engineering findings. Every candidate must trace to a specific
moment in the session. Present candidates by severity; change nothing until
the user picks one.

| Session finding | CSE owner for the fix |
|---|---|
| A verifier, task, or benchmark depended on an unstated convention | Design records the convention and reference case; Build adds the check in the owning verifier or task. Private benchmark fixes stay in `cse-sciencebench`, outside candidate payloads. |
| A CSE stage was missed or sent to the wrong skill | Setup repairs navigation; the owning skill and Workflow clarify the scientific handoff. |
| Review found claims unsupported | Review names the missing evidence or claim limit; Analyze regenerates evidence, Summarize corrects the notebook, and Write corrects promoted prose. |
| Source or data provenance was missing | Research and Zotero resolve source authority; Data resolves retained-data lineage; Setup records the owner. |
| A notebook or figure failed | Summarize owns the notebook; Quarto and the selected figure skill repair presentation; Analyze owns missing numerical values. |
| A tolerance or numerical method surprised the session | Diagnose establishes the cause; Design records the accepted method and tolerance; Build changes only that decision. |

Mechanical problems become deterministic checks in the existing owning command,
not more steering prose. Inspect existing checks first: an unwired or broken
check is the finding, not a reason to duplicate it. Reserve reviewer guidance
for judgments a check cannot make. Keep always-loaded guidance to navigation.
