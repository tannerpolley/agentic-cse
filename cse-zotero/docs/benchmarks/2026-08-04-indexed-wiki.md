# Indexed wiki benchmark — 2026-08-12

The benchmark uses 20 bounded agent tasks covering paper sources, equations,
datasets, correlations, parameters, ideas, insights, workflows, and validation
across ePC-SAFT, electrolyte, MEA, and lithium-extraction work. The task
definitions are in [`benchmarks/agent_tasks.json`](../../benchmarks/agent_tasks.json),
and the indexed runner is [`scripts/benchmark_wiki.py`](../../scripts/benchmark_wiki.py).
The public command contract is exercised by
[`scripts/agent_smoke.py`](../../scripts/agent_smoke.py).

Observed local run:

| Metric | Result |
| --- | ---: |
| Tasks | 20 |
| Passed / recall | 20 / 1.0 |
| Fully auditable tasks | 20 |
| Full PDF reads | 0 |
| Mean latency | approximately 61.1 ms |
| Maximum returned context | 15,701 characters |
| Read-only tasks | 20 / 20 |

The benchmark searches typed records and the declared `.md`/`.mmd` evidence
index only. It does not convert PDFs, call Mathpix, mutate Zotero, or write to
the registry. The current indexed Markdown/SQLite path is sufficient for the
seed tasks; adding vector, graph-database, MCP, or service infrastructure is
not justified until a measured task failure appears.

Re-run it with:

```bash
uv run python scripts/benchmark_wiki.py --json
uv run python scripts/agent_smoke.py --json
```
