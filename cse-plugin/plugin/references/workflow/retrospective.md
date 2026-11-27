# Science retrospectives and history audits

For a requested `/retro` session retrospective, include these categories
alongside engineering findings. Every candidate must trace to a specific
moment in the session. Present candidates by severity; change nothing until
the user picks one.

| Session finding | CSE owner for the fix |
|---|---|
| A verifier, task, or benchmark depended on an unstated convention | Design records the convention and reference case; Build adds the check in the owning verifier or task. Private benchmark fixes stay in `cse-sciencebench`, outside candidate payloads. |
| A CSE stage was missed or sent to the wrong skill | Setup repairs navigation; the owning skill and Workflow clarify the scientific handoff. |
| Review found claims unsupported | Review names the missing evidence or claim limit; Analyze corrects retained evidence and interpretation, and Write corrects promoted prose. |
| A manuscript drifted through drafting or revision | Write, Prose, or Review identifies missed [writing principles](scientific-writing.md), [structure or reader-story triggers](manuscript-review.md#story-spine-read) that did not fire, and gaps in [STYLE coverage](writing-editorial.md#standing-editorial-decisions). |
| Source or data provenance was missing | Research and Zotero resolve source authority; Data resolves retained-data lineage; Setup records the owner. |
| A figure or document failed | Quarto and the selected figure skill repair presentation; Analyze owns missing numerical values. |
| A tolerance or numerical method surprised the session | Diagnose establishes the cause; Design records the accepted method and tolerance; Build changes only that decision. |

Mechanical problems become deterministic checks in the existing owning command,
not more steering prose. Inspect existing checks first: an unwired or broken
check is the finding, not a reason to duplicate it. Reserve reviewer guidance
for judgments a check cannot make. Keep always-loaded guidance to navigation.

## Cross-session history audit

1. **Sources and completeness:** establish the requested projects, threads, and
   date interval. Read every owner-typed message and stored free-text answer in
   those threads from the host’s thread store or complete supported export,
   following pagination. Inspect authorship/origin metadata: agent briefs and
   generated prompts are not owner testimony even when a host gives them a user
   role. In T3, distinguish owner-typed messages from agent briefs and include
   stored question responses. Read surrounding exchanges to interpret the
   owner’s words; exclude assistant restatements from counts. Name inaccessible
   records, truncation, or ambiguous authorship and limit conclusions
   accordingly. Do not substitute keyword hits or summaries for the full read.
2. **Counting:** group entries by the same concrete request or correction,
   preserving differing scope and exceptions. Count each distinct owner message
   or answer once per theme; deduplicate the same source entry repeated through
   exports or inherited thread history. Report the counting unit, total
   inspected owner messages/answers and threads, theme counts, dates, and
   retrievable thread/message or answer locators. One entry may support multiple
   themes; theme counts therefore need not sum to the corpus total.
3. **Recurrence after a rule:** locate the dated owner rule or repository
   introduction/revision intended to prevent each theme. Compare only later,
   applicable occurrences with the rule in effect then; cite the rule and dated
   later evidence, with a count. Distinguish a renewed request from evidence of
   the same failure. Undated, unavailable, or ambiguous ordering is unresolved,
   not proof of recurrence or prevention.
4. **Repository comparison:** inspect the applicable project instructions,
   skill/reference owners, and existing generators or checks. Cite exact
   paths/lines and compare their actual scope with the owner evidence. Preserve
   required, optional, and future labels; current text alone does not prove that
   historical guidance existed or applied.
5. **Classification:** choose the smallest justified disposition: **new skill**
   only for a reusable capability without an existing owner; **refine skill**
   for a gap in an existing skill/reference; **project rule** for a
   project-specific decision; **structural fix** when an existing generator,
   command, or check should prevent recurrence; **covered** when applicable
   guidance already addresses it and no change is supported. Repetition alone
   does not justify another rule or skill; an unwired/broken existing check calls
   for repair. Record missing evidence before assigning an unsupported
   disposition.
6. **Report:** return a concise theme table with counts, dated source locators,
   rule and post-rule recurrence evidence, guidance owner, classification, and
   smallest proposed action. End with inspected scope and missing evidence.
   Report candidates only; apply no fixes without authority. No database,
   exporter, new audit script, scoring, or permanent audit record format.
