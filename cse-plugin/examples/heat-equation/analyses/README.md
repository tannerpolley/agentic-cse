# Analysis layout

Each durable study owns a locally understandable folder under `analyses/` with
a `README.md`, retained `inputs/` with provenance, separate data-generation
and rendering scripts, exact plotted-data tables, and retained final figures. Review checks this retained evidence.

The current study is [heat_verification](heat_verification/README.md). Its
figure-owned directories contain source scripts, editable plotting metadata,
CSV outputs, and same-stem SVG, PNG, and PDF figures. Generation computes the
scientific values. Rendering reads those retained values and never reruns the
solvers.

Small CSV tables and curated figures are tracked because they carry the
repository's scientific claims. Disposable runs belong in ignored `runs/` or
`scratch/` directories. Future large data requires an explicit project policy
for authority, format, lineage, retention, versioning, and recovery.
