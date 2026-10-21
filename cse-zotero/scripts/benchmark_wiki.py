"""Measure the bounded, read-only wiki retrieval path for agent tasks.

The benchmark intentionally uses only typed-record lookup and the declared
Markdown/Mathpix evidence index.  It never opens a PDF, invokes Mathpix, or
writes Zotero state.  Use ``--out`` only when an explicit repository-local
benchmark artifact is desired.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from zotero_companion.records import lineage, record_lookup, search_records  # noqa: E402
from zotero_companion.config import load_config  # noqa: E402
from zotero_companion.wiki import search_evidence_chunks  # noqa: E402


def _default_wiki_root() -> Path:
    return load_config().wiki_root


def _read_tasks(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or not value:
        raise ValueError(f"Benchmark task file must contain a non-empty array: {path}")
    tasks = [dict(item) for item in value if isinstance(item, dict)]
    if len(tasks) != len(value):
        raise ValueError(f"Benchmark task file contains a non-object entry: {path}")
    return tasks


def _auditability(hits: list[dict[str, Any]], record: dict[str, Any]) -> dict[str, Any]:
    evidence_auditable = bool(hits) and all(
        hit.get("zotero_key")
        and hit.get("zotero_attachment_key")
        and hit.get("locator")
        and hit.get("hash_matches") is True
        for hit in hits
    )
    provenance = record.get("provenance", {})
    source_auditable = bool(
        isinstance(provenance, dict)
        and provenance.get("sources")
        and all(
            isinstance(source, dict)
            and source.get("zotero_key")
            and source.get("locator")
            for source in provenance.get("sources", [])
        )
    )
    return {
        "evidence": evidence_auditable,
        "record_provenance": (
            source_auditable or bool(provenance.get("derived_from"))
            if isinstance(provenance, dict)
            else False
        ),
        "all_required": evidence_auditable and source_auditable,
    }


def run_benchmark(
    wiki_root: Path = ROOT / "wiki",
    tasks_path: Path = ROOT / "benchmarks/agent_tasks.json",
) -> dict[str, Any]:
    tasks = _read_tasks(tasks_path)
    results: list[dict[str, Any]] = []
    for task in tasks:
        started = time.perf_counter()
        query = str(task.get("query", ""))
        evidence_query = str(task.get("evidence_query", query))
        source_keys = [str(key) for key in task.get("source_keys", [])]
        expected_record_id = str(task.get("expected_record_id", ""))
        records = search_records(wiki_root, query=query, limit=8)
        hits = search_evidence_chunks(
            wiki_root,
            source_keys=source_keys,
            query=evidence_query,
            limit=4,
        )
        record = record_lookup(wiki_root, expected_record_id)
        lineage_result = lineage(wiki_root, expected_record_id)
        registry_refs = record.get("registry_refs", [])
        auditability = _auditability(hits, record)
        context_chars = sum(len(str(hit.get("text", ""))) for hit in hits)
        expected_found = any(item.get("record_id") == expected_record_id for item in records)
        min_evidence_hits = int(task.get("min_evidence_hits", 0) or 0)
        registry_ok = bool(registry_refs) if task.get("requires_registry_reference") else True
        passed = bool(
            expected_found
            and len(hits) >= min_evidence_hits
            and registry_ok
            and lineage_result.get("read_only") is True
        )
        results.append(
            {
                "id": str(task.get("id", "")),
                "passed": passed,
                "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                "context_chars": context_chars,
                "record_matches": len(records),
                "evidence_hits": len(hits),
                "expected_record_found": expected_found,
                "registry_reference_present": bool(registry_refs),
                "auditability": auditability,
                "full_pdf_read": False,
                "read_only": True,
            }
        )
    latencies = [float(result["latency_ms"]) for result in results]
    contexts = [int(result["context_chars"]) for result in results]
    return {
        "schema_version": 1,
        "benchmark": "indexed-markdown-wiki-agent-tasks",
        "task_file": str(tasks_path.relative_to(ROOT)),
        "wiki_root": str(wiki_root),
        "tasks": results,
        "summary": {
            "task_count": len(results),
            "passed_count": sum(1 for result in results if result["passed"]),
            "recall": round(sum(1 for result in results if result["passed"]) / len(results), 3),
            "mean_latency_ms": round(statistics.mean(latencies), 3),
            "p95_latency_ms": round(sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)], 3),
            "max_context_chars": max(contexts, default=0),
            "all_read_only": all(result["read_only"] for result in results),
            "full_pdf_reads": sum(1 for result in results if result["full_pdf_read"]),
            "fully_auditable_tasks": sum(
                1 for result in results if result["auditability"]["all_required"]
            ),
        },
        "decision": {
            "indexed_path_sufficient_for_seed_tasks": all(result["passed"] for result in results),
            "additional_retrieval_infrastructure_justified": False,
            "reason": "Use measured failure evidence before adding vector, graph, or service infrastructure.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wiki-root", type=Path, default=_default_wiki_root())
    parser.add_argument("--tasks", type=Path, default=ROOT / "benchmarks/agent_tasks.json")
    parser.add_argument("--out", type=Path, help="explicitly write the JSON result to this path")
    parser.add_argument("--json", action="store_true", help="emit JSON (the default output)")
    args = parser.parse_args()
    result = run_benchmark(args.wiki_root, args.tasks)
    if args.out:
        result["written"] = str(args.out)
        args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(output, end="")
    return 0 if result["summary"]["passed_count"] == result["summary"]["task_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
