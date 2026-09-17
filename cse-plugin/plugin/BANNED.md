# Banned language

This is the CSE ban list for vague agent language. A listed word is banned in
agent-authored prose, issues, review reports, notebooks, and manuscripts when
it hides a concrete scientific or engineering meaning.

Use the actual actor, action, object, state, quantity, file, evidence, or
claim instead.

The list does not apply to exact code identifiers, official filenames, product
names, quotations, source titles, genuine domain terms such as contact
mechanics, or a defined project term in `CONTEXT.md`. When a listed word is
necessary, state its concrete meaning.

## Current entries

| Avoid when used vaguely | Use instead |
|---|---|
| `artifact` | The actual file, result table, figure, or document name |
| `contract` | The exact callable, command, invariant, equation, requirement, check, or agreement |
| `acceptance specification`, `receipt`, or `criterion table` in ordinary analysis | The actual inputs, method, returned values, statistics, numerical diagnostics, uncertainty, and named authoritative limit |
| `schema` as a catch-all | The exact columns, fields, units, relationships, or file structure |
| `manifest` as a catch-all | The exact inventory, index, provenance file, or official filename |
| `API` as a catch-all | The exact callable, command, or input/output interface |
| `regression` for a software check | `persistent behavior check` or `previous-failure check`; retain regression for statistical regression and fitting |
| a `flag`, `status`, or `route` presented as a scientific result | The returned value, stopping point, diagnostic, numerical behavior, or unresolved question |
| `orchestration` | The actual calls or sequence of operations |
| `pipeline` as a catch-all | The named steps; retain `data pipeline` when it is the established scientific object |
| `context` as a catch-all or phase name | `scientific context`, `repository context`, `task context`, or the exact constraint |
| `robust` or `robustness` without a failure case | The failure handled and the evidence that it is handled |
| `scalable` or `scalability` without a measured range | The tested size or range and the measured behavior |
| `production-ready` | The actual deployment, validation state, and limitations |
| `future-proof` | The supported versions, assumptions, and upgrade condition |
| `seamless` | The actual transition, state change, or error behavior |

## Naming test

Before naming a durable file, class, test, record, or glossary entry, require
either a domain source that uses the term with that meaning or the quantity,
equation, or operation itself. Record the meaning, source, and scope beside
the term in `docs/scientific/CONTEXT.md`. An invented label with no source
remains an Audit finding; it does not become accepted vocabulary by repetition.

For genuine domain terms, product names, and source titles that resemble a
listed word, retain a sourced glossary entry rather than weakening a rule.
The checker exempts quoted passages, fenced code, exact inline identifiers
and filenames, and sourced glossary terms within their declared path scope.
Mark exact identifiers and official filenames as inline code; a filename-like
word in ordinary prose does not establish an exemption. State a concrete
meaning using “term means …” or “term: …” when the word itself is necessary.
