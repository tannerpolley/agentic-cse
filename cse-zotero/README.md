# Zotero-Wiki

Staged automation for the local Zotero library used by the Engineering
workspaces.

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
local API key from `/home/user/.config/zotero-wiki/local-api-key`,
keeps the key out of output, and uses server-ID and version preconditions for
writes.

## Read-only audit

From this directory:

```bash
python -m zotero_wiki audit --json
```

The audit reports Zotero item/collection/tag counts and Markdown attachment
counts. It does not modify Zotero, files, or preferences.

## Agent wiki

The canonical broad-corpus architecture and delivery roadmap is
[docs/zotero-llm-wiki-plan.md](docs/zotero-llm-wiki-plan.md). The shared
domain vocabulary is [CONTEXT.md](CONTEXT.md). All Zotero sources remain
discoverable; the current project pages are only initial views, while relevant
papers can be connected to multiple projects, domains, and research threads.

The retrieval and curation slices now build indexed Markdown evidence chunks,
an all-source triage queue, reviewable domain/thread classification, and
first-class records connecting evidence to equations, data, ideas, workflows,
implementations, and validation. Metadata suggestions remain visibly
different from scientific conclusions.
Inspect the bounded queues with:

~~~bash
uv run zotero-wiki wiki-triage --queue unbriefed_relevant --limit 20 --json
uv run zotero-wiki wiki-triage --queue needs_classification --limit 20 --json
uv run zotero-wiki wiki-triage --domain electrolyte-thermodynamics --json
~~~

The `wiki/` directory is the durable agent-facing layer. Zotero remains the
bibliographic source of truth; `wiki/sources/`, `wiki/catalog.json`, and
`wiki/manifest.json` are generated from Zotero and can be rebuilt. Human or
agent interpretation belongs in `wiki/projects/` and `wiki/claims/`, where it
must cite a Zotero key or another explicitly identified source.

Reviewable corpus classification belongs in
[`wiki/curation/source-assignments.json`](wiki/curation/source-assignments.json).
Use `wiki-classify` to prepare one classification at a time; it is dry-run by
default and `--apply` changes only the repository assignment file and generated
triage/index artifacts. `suggested_domains` and `suggested_research_threads`
remain metadata-based discovery aids until an assignment is recorded.

The first sync is intentionally a dry run:

```bash
uv run zotero-wiki wiki-sync --json
uv run zotero-wiki wiki-sync --apply --json
```

The apply flag writes only repository files and never writes to Zotero. The
generated SQLite index is ignored and can be rebuilt at any time:

```bash
uv run zotero-wiki wiki-search "phase equilibrium" --json
uv run zotero-wiki wiki-search "activity coefficient" --project epcsaft-equilibrium --json
uv run zotero-wiki wiki-source ABCD2345 --json
uv run zotero-wiki wiki-evidence ABCD2345 --query "Born diameter" --json
uv run zotero-wiki wiki-context epcsaft-equilibrium --json
uv run zotero-wiki wiki-context --global --query "Born activity coefficient" --json
uv run zotero-wiki wiki-record equation:figiel-born-solvation-shell --json
uv run zotero-wiki wiki-lineage dataset:hamer-1972-aqueous-coefficients --json
uv run zotero-wiki wiki-health --stale-source 28NPJ5H6 --json
uv run zotero-wiki wiki-lint --registry-root ../thermophysical-data-registry --json
uv run zotero-wiki wiki-release --registry-root ../thermophysical-data-registry --json
uv run zotero-wiki wiki-refresh --json
uv run zotero-wiki wiki-verify --json
uv run zotero-wiki wiki-stale --json
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
`lithium-extraction`, and `mea-thermodynamics`. See [wiki/README.md](wiki/README.md)
for the artifact contract.

The first full-text evidence candidate is [Figiel 2025](wiki/papers/Figiel2025.md).
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

```bash
uv run zotero-wiki wiki-context epcsaft-equilibrium \
  --query "Born term mixed solvent" --json
```

The Figiel 2025 graph is at
[`wiki/graphs/Figiel2025.nodegraph.json`](wiki/graphs/Figiel2025.nodegraph.json),
and its atomic claims are under [`wiki/claims/`](wiki/claims/README.md).

The second vertical-slice evidence candidate is [Hamer 1972](wiki/papers/Hamer1972.md),
using the existing Zotero Markdown companion under `wiki/evidence/28NPJ5H6/`.
Its registry data remains a staging candidate until basis and row membership
are reviewed.

Before a review or handoff, run the local-only checks:

```bash
uv run zotero-wiki wiki-verify --json
uv run zotero-wiki wiki-manifest-lint --registry-root ../thermophysical-data-registry --json
uv run zotero-wiki wiki-release --registry-root ../thermophysical-data-registry --json
uv run python scripts/benchmark_wiki.py --json
```

`wiki-release` is dry-run by default. `wiki-release --apply` writes only the
repository-local `wiki/release-manifest.json`; it does not write to Zotero or
the thermophysical-data registry.

`wiki-evidence` searches only the declared Markdown/Mathpix Markdown companions
in an evidence manifest. It returns short line-located passages, attachment
keys, and companion hash status; it never converts a PDF or writes to Zotero.
The CLI `wiki-context` command performs a read-only live freshness check when
the local Zotero API is available and includes the result under `freshness`.
It never refreshes the repository implicitly. Use the explicit refresh gate
only after reviewing its dry-run output:

```bash
uv run zotero-wiki wiki-refresh --json
uv run zotero-wiki wiki-refresh --apply --json
```

`wiki-refresh --apply` updates only generated source records, the catalog,
manifest, and search index. Curated claims, graphs, and evidence companions
remain untouched.

## Stage 2 background plugin

Build the bootstrapped plugin package with:

```bash
uv run python scripts/build_plugin.py
```

Install `dist/zotero-wiki-0.1.0.xpi` from Zotero's Add-ons manager, then
restart Zotero once. The plugin runs in the background and adds these
loopback-only endpoints to Zotero's existing local server:

- `GET /zotero-wiki/status`
- `POST /zotero-wiki/tag-cleanup` (dry-run unless an exact confirmation token is supplied)
- `POST /zotero-wiki/saved-searches` (dry-run unless an exact confirmation token is supplied)

The CLI never controls the desktop pointer or keyboard:

```bash
uv run zotero-wiki plugin-status --json
uv run zotero-wiki plugin-tag-cleanup --json
uv run zotero-wiki plugin-searches --json
```

Mutating commands are deliberately separate and explicit (`--apply`). They
are not run as part of installation or startup.

## Stage 3 authenticated local REST writer

Check the key file and local API without changing Zotero:

```bash
uv run zotero-wiki local-status --json
```

The REST organization commands are dry-run by default:

```bash
uv run zotero-wiki local-tag-cleanup --json
uv run zotero-wiki local-searches --json
```

Only run an apply command after reviewing its dry-run output and confirming
the intended scope:

```bash
uv run zotero-wiki local-tag-cleanup --apply --json
uv run zotero-wiki local-searches --apply --json
```

Item tag updates preserve unrelated tags and use the item's version when the
local API provides one. For local records with an empty item version, the
writer uses the library `Last-Modified-Version` returned by the same read as
the request-level precondition. Saved-search creation uses the same library
precondition. A stale precondition stops the operation.
