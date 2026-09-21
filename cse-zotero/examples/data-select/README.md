# Data selection

Register the controlled package first, then select one verified resource into
an analysis-local snapshot. The command is dry-run by default:

```bash
mkdir -p /tmp/cse-normalized/source/registry

uv run cse-zotero data-register examples/data-register/package \
  --registry-root /tmp/cse-normalized/source/registry --apply --json

uv run cse-zotero data-select ds:registered-mea-density \
  --resource observations.csv \
  --analysis analyses/mea-density \
  --registry-root /tmp/cse-normalized/source/registry \
  --apply --json
```

Apply writes `analyses/mea-density/inputs/observations.csv` and
`observations.csv.lineage.json`. The resource is copied, not linked; the
lineage records its registered hash and metadata so a later registry update
cannot change an existing analysis input.
