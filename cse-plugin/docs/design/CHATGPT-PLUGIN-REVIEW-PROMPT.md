# ChatGPT prompt for an external Scientific Codex review

Copy and paste the prompt below after granting ChatGPT's GitHub app access to
both private repositories.

~~~text
You are conducting an independent, review-only product and scientific-workflow
review of the private Codex plugin Scientific Codex. You have GitHub app access
for both repositories below:

1. First inspect the plugin source: https://github.com/tannerpolley/scientific-codex
2. Then inspect the behavioral example: https://github.com/tannerpolley/scientific-codex-example

Do not modify either repository. Do not create issues, branches, pull requests,
comments, commits, releases, labels, Projects, or generated files. Do not
install anything. If either repository is inaccessible, report that as the
first finding and do not infer its contents.

## Review method

Start with the plugin repository. Read its manifest, README, AGENTS.md, all ten
public skill files, all shared references, validation scripts, and tests. Then
read the design documents under docs/design/. After that, inspect the example's
PROFILE.md, README.md, docs/scientific/CONTEXT.md, formulation.tex, methods.tex,
evidence.tex, writing rules, setup validator, bibliography helper, and the
committed bibliography snapshot. Follow links when they are part of the
plugin's stated contract.

For every material finding:

- cite the exact repository, file path, line number or heading, and a direct
  GitHub URL when possible;
- label the statement as **Observed** when the file or live repository shows it
  directly, or **Inference** when you are reasoning beyond the text;
- explain the scientific or product consequence, not just the wording issue;
- distinguish a contradiction, a missing capability, an ambiguity, a
  duplication, and a merely optional improvement; and
- avoid quoting private task history or treating an undocumented assumption as
  a settled decision.

Do not use generic software-engineering boilerplate. Do not recommend coverage
targets, a test pyramid, helper-by-helper tests, or conventional architecture
work unless you can tie the recommendation to a concrete scientific risk,
source-integrity risk, numerical failure, privacy boundary, or Codex plugin
contract.

## Questions to answer

Assess the following dimensions against the repository evidence:

1. **Scientific usefulness.** Does Scientific Codex help an agent move from a
   scientific question and evidence to equations, methods, numerical behavior,
   uncertainty, interpretation, and defensible claims? What kinds of users and
   scientific work does it serve well or poorly?
2. **Science-first language.** Is the shared vocabulary precise and useful?
   Does it keep question, equation, method, reference case, tolerance,
   evidence, uncertainty, interpretation, limitation, and claim distinct from
   generic project-management language?
3. **Numerical and uncertainty doctrine.** Does the result-first testing advice
   select independent oracles and quantity-specific tolerances? Does it
   distinguish code verification, solution verification, model validation,
   numerical uncertainty, and physical uncertainty without overpromising?
4. **Skill routing and continuity.** Do setup, research, construct, build,
   analyze, summarize, write, review, zotero, and mathpix form a coherent route? Are the
   continuation rules useful, or do entrypoint overlap and repeated alignment
   questions create friction?
5. **Grilling quality.** Are the material questions strong enough to expose
   missing scientific context and weak claims without turning every task into a
   rigid questionnaire or blocking ordinary work?
6. **Sources and Zotero Companion.** Is the authority boundary between Zotero,
   Companion, repository snapshots, and remote search clear?
   Are paper acquisition, exact locators, private attachments, provenance, and
   correction permissions safe and practical?
7. **Writing and plotting support.** Do the notebook, manuscript, bibliography,
   figure, style, and claim-boundary rules support reproducible scientific
   communication? Are important scientific writing or plotting workflows
   missing?
8. **Self-containment and Codex quality.** Is the plugin genuinely independent
   of Project Truss, Superpowers, and Matt Pocock skills at runtime? Is the
   manifest, skill metadata, reference layout, validator, deployment path, and
   fresh-task installation guidance coherent for a Codex plugin?
9. **Missing workflows.** Which scientifically important workflows are absent,
   such as experiment design, dimensional analysis, symbolic derivation,
   Bayesian or statistical inference, uncertainty quantification, data
   assimilation, HPC execution, benchmarking, or domain-specific validation?
   Rank omissions by product value rather than listing every possible feature.
10. **Ambiguity and duplication.** Identify instructions that could lead to
    different behavior, repeated doctrine that could drift, unresolved product
    boundaries, or terminology that a new user would interpret differently.
11. **Example fidelity.** Does the scientific-codex-example repository genuinely
    demonstrate the plugin's promises, or does it only demonstrate setup and
    documentation? Separate what the example has completed from what it plans
    for future FTCS and Crank–Nicolson studies.

## Required output

Return a concise but substantive report with these sections:

### Executive verdict

Give a candid verdict on the plugin's current potential for serious scientific
work. State the strongest evidence for that verdict and the largest uncertainty.
Do not soften a material concern merely because the product idea is promising.

### Strengths worth preserving

List the decisions, language, workflows, or boundaries that are unusually good.
Each item needs a file-specific citation and an observed-versus-inference label.

### Prioritized findings

Use three priority levels:

- **P0: blocking or scientifically unsafe**
- **P1: important product or workflow revision**
- **P2: useful refinement**

For each finding provide: priority, observed or inference label, exact citation,
why it matters, and a concrete revision or experiment that would resolve it.
If a priority level has no findings, say so explicitly.

### Scientific workflow coverage

Map the ten skills and the example to the work they actually support. Identify
missing workflows and explain which should be added, clarified, delegated to the
user's repository, or deliberately left out.

### Self-containment, privacy, and installation review

Check the runtime boundary, private-repository assumptions, Zotero and Companion
permissions, capability gates, manifest, validation, deployment, and
fresh-task behavior. Cite the exact files. State any claim that is only an
inference from local scripts rather than a verified live behavior.

### Concrete revision plan

Give the smallest ordered set of revisions that would materially improve the
plugin. Favor changes to shared doctrine, skill routing, source boundaries,
scientific examples, or evaluation evidence over generic refactoring.

### Final verdict

Answer plainly:

- Would you keep using this plugin for a new numerical research repository?
- Would you keep using it for Tanner's intended private scientific work?
- What evidence is still needed before calling it genuinely useful and well built for that purpose?

Keep the review independent, specific, and scientifically grounded. Do not make
repository changes as part of this review.
~~~
