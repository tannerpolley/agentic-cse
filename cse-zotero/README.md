# Zotero Companion

Zotero Companion adds source-linked synthesis and scientific data to a local
Zotero library. Zotero remains the authority for citations, collections, and
attachments. Companion preserves exact source locators, typed scientific
records, transformations, uncertainty, lineage, and domain data.

The installable package contains the domain-neutral LinkML model in
[`schema/companion.yaml`](schema/companion.yaml) and optional domain packs such
as [`schema/thermophysical.yaml`](schema/thermophysical.yaml). The active corpus
is user-owned local state under the configured XDG data directory, not package
content. LinkML validates retained record shape and DuckDB builds rebuildable
indexes over declared CSV, Parquet, or JSON sources without becoming a second
scientific authority.

Each scientific project declares its own data authority, formats, lineage,
retention, versioning, and recovery strategy. Companion does not prescribe a
dataset versioning system.

```bash
uv run zotero-companion init --json
uv run zotero-companion doctor --json
uv run zotero-companion schema-validate data/examples/core-records.yaml --json
uv run zotero-companion data-query \
  "$HOME/.local/share/zotero-companion/corpus/data/domains/thermophysical/normalized/registry-records.csv" \
  --sql "SELECT record_type, count(*) AS count FROM records GROUP BY record_type" --json
```

`init` is dry-run by default. `init --apply` creates the private configuration
and empty corpus directories. For the one-time migration from an older source
checkout, review `corpus-migrate --json`, then use `corpus-migrate --apply
--json`; it copies and verifies files without deleting the source checkout.

## Canonical bibliography

The configured bibliography target defaults to
`~/Zotero/exports/references.bib`. `bibliography-export` is dry-run by default;
`bibliography-export --apply --json` requests a whole-personal-library Better
BibTeX export and atomically refreshes that file. The request enforces
`skipFields=file`, and Companion refuses to replace the target if a local
attachment path is still present. Refresh is task-triggered, not a background
daemon, and the command never rewrites project bibliography consumers.

## Scientific source front doors

The installed CLI exposes live, read-only `zotero-search`, `zotero-children`,
and `zotero-attachment-path` commands so callers do not need a second Zotero
helper. `mathpix-convert` is dry-run first, requires recorded library consent,
honors configured denied tags and collections, refuses a PDF with an existing
Markdown child, and never mutates Zotero. `zotero-attach-companion` is a
separate dry-run-first authenticated write for making an approved generated
Markdown file visible as a linked Zotero child.

## Stages

- **Stage 1:** read-only local API inventory and dry-run reports.
- **Stage 2:** an optional background Zotero plugin for local-only writes. It
  will be installed separately and will never control the desktop pointer or
  keyboard.
- **Stage 3:** an authenticated Zotero 10 local REST writer. It plans tag and
  saved-search changes by default and requires `--apply` for writes.
- **Stage 4:** a deterministic, agent-readable wiki materialized from a
  read-only Zotero snapshot. Generated source records are kept separate from
  curated project context and claims.

The Stage 1 client intentionally exposes only read requests. Zotero 10 beta
supports authenticated local write requests, but those are kept out of the
read-only audit layer. The API runs at `http://127.0.0.1:23119` and requires
Zotero's local API preference to be enabled. The writer reads the remembered
local API key from `~/.config/zotero-companion/local-api-key`,
keeps the key out of output, and uses server-ID and version preconditions for
writes.

## Read-only audit

From this directory:

```bash
python -m zotero_companion audit --json
```

The audit reports Zotero item/collection/tag counts and Markdown attachment
counts. It does not modify Zotero, files, or preferences.

## Agent wiki

The canonical broad-corpus architecture and delivery roadmap is
[docs/zotero-companion-design.md](docs/zotero-companion-design.md). The shared
domain vocabulary is [CONTEXT.md](CONTEXT.md). All Zotero sources remain
discoverable; the current project pages are only initial views, while relevant
papers can be connected to multiple projects, domains, and research threads.
The reusable agent operating protocol is
[.agent/skills/zotero-companion/SKILL.md](.agent/skills/zotero-companion/SKILL.md), with
the answer-grounding rubric in [docs/agent-answer-rubric.md](docs/agent-answer-rubric.md).

The retrieval and curation slices now build indexed Markdown evidence chunks,
an all-source triage queue, reviewable domain/thread classification, and
first-class records connecting evidence to equations, data, ideas, workflows,
implementations, and validation. Metadata suggestions remain visibly
different from scientific conclusions.
Inspect the bounded queues with:

~~~bash
uv run zotero-companion wiki-triage --queue unbriefed_relevant --limit 20 --json
uv run zotero-companion wiki-triage --queue needs_classification --limit 20 --json
uv run zotero-companion wiki-triage --domain electrolyte-thermodynamics --json
~~~

The configured `corpus/wiki/` directory is the durable agent-facing layer. Zotero remains the
bibliographic source of truth; `wiki/sources/`, `wiki/catalog.json`, and
`wiki/manifest.json` are generated from Zotero and can be rebuilt. Human or
agent interpretation belongs in `wiki/projects/` and `wiki/claims/`, where it
must cite a Zotero key or another explicitly identified source.

Reviewable corpus classification belongs in the active corpus at
`wiki/curation/source-assignments.json`.
Use `wiki-classify` to prepare one classification at a time; it is dry-run by
default and `--apply` changes only the repository assignment file and generated
triage/index artifacts. `suggested_domains` and `suggested_research_threads`
remain metadata-based discovery aids until an assignment is recorded.

The first sync is intentionally a dry run:

```bash
uv run zotero-companion wiki-sync --json
uv run zotero-companion wiki-sync --apply --json
```

The apply flag writes only repository files and never writes to Zotero. The
generated SQLite index is ignored and can be rebuilt at any time:

```bash
uv run zotero-companion wiki-search "phase equilibrium" --json
uv run zotero-companion wiki-search "activity coefficient" --project epcsaft-equilibrium --json
uv run zotero-companion wiki-source ABCD2345 --json
uv run zotero-companion wiki-evidence ABCD2345 --query "Born diameter" --json
uv run zotero-companion wiki-context epcsaft-equilibrium --json
uv run zotero-companion wiki-context --global --query "Born activity coefficient" --json
uv run zotero-companion wiki-record equation:figiel-born-solvation-shell --json
uv run zotero-companion wiki-record-template equation --zotero-key YEENX35P --json
uv run zotero-companion wiki-paper-template YEENX35P --json
uv run zotero-companion wiki-lineage dataset:hamer-1972-aqueous-coefficients --json
uv run zotero-companion wiki-health --stale-source 28NPJ5H6 --json
uv run zotero-companion wiki-coverage --json
uv run zotero-companion wiki-lint --registry-root data/domains/thermophysical/source/registry --json
uv run zotero-companion wiki-release --registry-root data/domains/thermophysical/source/registry --json
uv run zotero-companion wiki-refresh --json
uv run zotero-companion wiki-verify --json
uv run zotero-companion wiki-stale --json
```

Agent authority rules are deliberately explicit:

- Treat a generated source record as a bibliographic/source observation, not
  as a validated scientific conclusion.
- Treat a project file as orientation and scope, not as evidence by itself.
- Treat a claim as provisional unless it names `zotero_key` or
  `derived_from` provenance and records its confidence/status.
- Prefer fresh Zotero metadata when `wiki-stale` reports a changed source;
  do not silently overwrite curated claims during a sync.

The project slugs currently scaffolded are `epcsaft-equilibrium`,
`lithium-extraction`, and `mea-thermodynamics`. See the active corpus's
`wiki/README.md`
for the retained-file contract.

The first full-text evidence candidate is the active corpus's
`wiki/papers/Figiel2025.md`.
Its main article and supporting information already had companion Markdown
attachments in Zotero, which are used directly by the repo evidence bundle.
For future PDFs without companions, use the repository-local Mathpix workflow:

```bash
python .agent/skills/mathpix/scripts/convert_with_mpx.py \
  "/absolute/path/to/paper.pdf" \
  --out "wiki/evidence/YEENX35P/paper.md" \
  --format md \
  --confirmed-no-companion
```

Read [.agent/skills/mathpix/SKILL.md](.agent/skills/mathpix/SKILL.md) before
converting another scientific PDF. First inspect the Zotero parent's children
and reuse any existing `.md`/`.mmd` attachment; an existing companion is
authoritative and is copied exactly. Routine PDF conversion is forbidden. The
wrapper requires the explicit no-companion confirmation and refuses OCR
API-key billing.

For agents, `wiki-context` is the main retrieval seam. It returns project
orientation, ranked source records, atomic claims, linked evidence files,
NodeGraph structures, implementation references, and open questions in one
JSON response. This keeps the common workflow low-friction while preserving
the distinction between Zotero evidence, curated reasoning, and engineering
implementation state:

When a query is supplied, wiki-context also returns evidence_hits from the
rebuildable index and an evidence_coverage report. The hits are limited to
declared Markdown/Mathpix Markdown companions, retain attachment keys,
locators, hashes, and sections, and never read or convert PDFs.
The global route additionally returns `matched_source_keys`, matching brief
paths, and source-to-evidence coverage so an agent can choose its next read
without scanning the folder layout. `wiki-source KEY` exposes the same
brief/evidence routes under `wiki` without embedding PDF text.

```bash
uv run zotero-companion wiki-context epcsaft-equilibrium \
  --query "Born term mixed solvent" --json
```

The Figiel 2025 graph is at
`wiki/graphs/Figiel2025.nodegraph.json` in the active corpus, and its atomic
claims are under that corpus's `wiki/claims/` directory.

The second vertical-slice evidence candidate is the active corpus's
`wiki/papers/Hamer1972.md`,
using the existing Zotero Markdown companion under `wiki/evidence/28NPJ5H6/`.
Its registry data remains a staging candidate until basis and row membership
are reviewed.

Before a review or handoff, run the local-only checks:

```bash
uv run zotero-companion wiki-verify --json
uv run zotero-companion wiki-manifest-lint --registry-root data/domains/thermophysical/source/registry --json
uv run zotero-companion wiki-release --registry-root data/domains/thermophysical/source/registry --json
uv run python scripts/benchmark_wiki.py --json
uv run python scripts/agent_smoke.py --json
```

`wiki-release` is dry-run by default. `wiki-release --apply` writes only the
repository-local `wiki/release-manifest.json`; it does not write to Zotero or
the thermophysical-data registry.

`wiki-coverage` is the broad-corpus progress view. It reports classification,
evidence, brief, typed-record, registry, and validation coverage plus bounded
examples for each gap. Missing coverage is expected and reviewable; it is not
permission to invent summaries or convert PDFs in bulk.

`wiki-evidence` searches only the declared Markdown/Mathpix Markdown companions
in an evidence manifest. It returns short line-located passages, attachment
keys, and companion hash status; it never converts a PDF or writes to Zotero.
The CLI `wiki-context` command performs a read-only live freshness check when
the local Zotero API is available and includes the result under `freshness`.
It never refreshes the repository implicitly. Use the explicit refresh gate
only after reviewing its dry-run output:

```bash
uv run zotero-companion wiki-refresh --json
uv run zotero-companion wiki-refresh --apply --json
```

`wiki-refresh --apply` updates only generated source records, the catalog,
manifest, and search index. Curated claims, graphs, and evidence companions
remain untouched.

## Stage 2 background plugin

Build the bootstrapped plugin package with:

```bash
uv run python scripts/build_plugin.py
```

Install `dist/zotero-companion-1.0.0.xpi` from Zotero's Add-ons manager, then
restart Zotero once. The plugin runs in the background and adds these
loopback-only endpoints to Zotero's existing local server:

- `GET /zotero-companion/status`
- `POST /zotero-companion/tag-cleanup` (dry-run unless an exact confirmation token is supplied)
- `POST /zotero-companion/saved-searches` (dry-run unless an exact confirmation token is supplied)

The CLI never controls the desktop pointer or keyboard:

```bash
uv run zotero-companion plugin-status --json
uv run zotero-companion plugin-tag-cleanup --json
uv run zotero-companion plugin-searches --json
```

Mutating commands are deliberately separate and explicit (`--apply`). They
are not run as part of installation or startup.

## Stage 3 authenticated local REST writer

Check the key file and local API without changing Zotero:

```bash
uv run zotero-companion local-status --json
```

The REST organization commands are dry-run by default:

```bash
uv run zotero-companion local-tag-cleanup --json
uv run zotero-companion local-searches --json
```

Only run an apply command after reviewing its dry-run output and confirming
the intended scope:

```bash
uv run zotero-companion local-tag-cleanup --apply --json
uv run zotero-companion local-searches --apply --json
```

Item tag updates preserve unrelated tags and use the item's version when the
local API provides one. For local records with an empty item version, the
writer uses the library `Last-Modified-Version` returned by the same read as
the request-level precondition. Saved-search creation uses the same library
precondition. A stale precondition stops the operation.
