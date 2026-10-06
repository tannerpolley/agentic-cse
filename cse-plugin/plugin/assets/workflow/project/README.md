# Scientific project records

This directory maps the repository's scientific question and retained records.
Source code, canonical reusable data, and model files remain in their
repository owners. Each bounded calculation keeps its retained inputs, scripts,
results, figures, and notebook under root `analyses/<short-id>/`. Summarize
prepares the notebook and selected render before delivered Review; Prose
separately inspects writing and final manuscript cohesion. The investigator
alone promotes reviewed notebooks for manuscript use.

This is a CSE project. For scientific or engineering work, use the installed
CSE skills and read this file plus `CONTEXT.md` before selecting the smallest
evidence-justified route:

- use Research before Design or Build when equations, sources, assumptions, or
  methods are not yet supported;
- use Diagnose first for an unexplained failed calculation, then Research when
  the scientific or mathematical basis remains unsettled; and
- continue through the applicable CSE handoffs until the requested scientific
  endpoint is complete.

Normal CSE work may ask every material question needed. A task-specific request
not to ask questions does not change the general project doctrine.

- `CONTEXT.md` owns the question, intended use, owners, source/data adoption
  choice, one confirmed repository role (`analysis` or `tool`), and the
  confirmed agent role with its responsibilities; it links to project vocabulary.
  Scoped or exception-bearing writing rules live under `## Prose avoid rules`.
- Root `GLOSSARY.md` owns vocabulary in Matt Pocock's format, with CSE's
  required `Source:` and optional `Scope:` lines. Read every glossary linked by
  an existing `GLOSSARY-MAP.md`; CSE never creates a map or requires Matt's skills.
- Optional `formulation.md`, `methods.md`, `evidence.md`, `decisions/`, and
  `writing/` records are Markdown and are created only when selected.
- LaTeX is reserved for manuscript sources under `latex/`; it is never a
  scientific record file.
