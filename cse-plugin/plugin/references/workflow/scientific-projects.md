# Scientific project records

Use `docs/scientific/CONTEXT.md` as the short scientific map. It owns one
investigator-confirmed `repository role: analysis` or `repository role: tool`;
Setup recommends a role from purpose and owners and confirms it on every run.
Project vocabulary belongs in root `GLOSSARY.md`, using this format:

```markdown
# Heat transfer

## Language

**Heat flux**:
Heat transfer rate per unit area.
_Avoid_: heat flow density
Source: project-approved paper, equation 2
Scope: `analyses/*`; `src/heat/*`
```

CSE requires `Source:`; mark a missing source `sourceless` and report it for
review. `Scope:` is optional. A root glossary without scope applies throughout
the repository; a map-listed glossary defaults to its own directory. Explicit
scopes are repository-relative POSIX globs in code spans, separated by semicolons.
The avoid list uses commas; omit an empty list. A sourced term is allowed only
within its scope. If root `GLOSSARY-MAP.md` exists, read every present glossary
it links, as well as any root glossary. A missing mapped file is absent because
glossaries are created lazily. CSE never creates a map.

A synonym with its own scope, exceptions, or other writing information is not
vocabulary. Keep it in `docs/scientific/CONTEXT.md` under `## Prose avoid rules`,
with Avoid, Prefer, Meaning, Scope, Exceptions, and Evidence columns. Separate
scopes and exception phrases with semicolons; preserve extra columns during
migration. This table owns project writing rules, not definitions.

Record confirmed personal preferences in `~/.config/cse/config.toml` only after
preview and approval. When personal and repository rules overlap for the same
avoided phrase, ask the user which owner to retain or how to split the scopes;
never choose precedence silently.

The personal file uses TOML array-of-tables entries:

```toml
[[terminology]]
Avoid = "contact"
Prefer = "stages"
Meaning = "Use equilibrium stages for the modeled extraction sequence."
Scope = ["analyses/**/*.qmd"]
Exceptions = ["MSContactor", "contact mechanics"]
Evidence = "confirmed user correction and task locator"
```

The personal entries require all six fields; Exceptions may be empty.
Matching is case-insensitive and phrase-bounded. An exception suppresses only
the matching occurrence inside that exact exception phrase. Identical behavioral
rules are not conflicts. Different rules for the same avoided phrase are a
configuration error only where their scopes overlap; report both locators.

Run `scripts/workflow/check_prose.py` from the project root, or supply `--root`;
add `--config` for personal rules. The checker and Stop hook read glossary
entries, scopes, synonym-avoids, and the `## Prose avoid rules` table.
The checker reports Avoid → Prefer with the rule locator; semantic review still decides
whether wording is scientifically correct.

The shared CSE-created record owner is `docs/scientific/`. Setup always creates
only `README.md` and `CONTEXT.md`. Optional formulation, methods, evidence,
decisions, and writing records are Markdown. Manuscript sources and their
bibliography stay below `docs/scientific/latex/` when writing is enabled;
LaTeX is never used for a scientific record. Temporary source synthesis may
use the ignored `docs/scientific/.research/` path.

For an analysis role, emphasize data and source authority, retained analyses,
results, figures or notebooks, uncertainty, and validation. For a tool role,
emphasize equation and implementation owners, interfaces, failure behavior,
reference cases, tolerances, and numerical verification. Fill the core with the repository's real scientific question, owners, and
paths; do not copy generic ADR starters or write blank headings or placeholder
files. Source code, canonical
reusable data, and main model files remain in their natural repository owners.
Do not turn an analysis-only repository into a package or require package and
environment policy as part of CSE setup.
