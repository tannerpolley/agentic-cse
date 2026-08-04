# Indexed wiki benchmark — 2026-08-04

The seed benchmark uses five bounded agent tasks covering a source-backed
equation, an activity-coefficient dataset, a registry parameter trace, a
cross-paper insight, and a validation acceptance gate. The task definitions are
in [`benchmarks/agent_tasks.json`](../../benchmarks/agent_tasks.json), and the
read-only runner is [`scripts/benchmark_wiki.py`](../../scripts/benchmark_wiki.py).

Observed local run:

| Metric | Result |
| --- | ---: |
| Tasks | 5 |
| Passed / recall | 5 / 1.0 |
| Fully auditable tasks | 5 |
| Full PDF reads | 0 |
| Mean latency | approximately 11.4 ms |
| Maximum returned context | 9,978 characters |
| Read-only tasks | 5 / 5 |

The benchmark searches typed records and the declared `.md`/`.mmd` evidence
index only. It does not convert PDFs, call Mathpix, mutate Zotero, or write to
the registry. The current indexed Markdown/SQLite path is sufficient for the
seed tasks; adding vector, graph-database, MCP, or service infrastructure is
not justified until a measured task failure appears.

Re-run it with:

```bash
uv run python scripts/benchmark_wiki.py --json
```
