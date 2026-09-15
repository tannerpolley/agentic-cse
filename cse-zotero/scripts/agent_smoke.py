"""Exercise the public CSE Zotero CLI as a read-only agent workflow.

This is intentionally deterministic and local.  It checks that an agent can
discover a typed record, retrieve a source and its companion evidence, and
trace lineage without opening a PDF or mutating Zotero.  It does not call an
LLM; the task file is the executable retrieval contract used by the benchmark.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from zotero_companion.config import load_config

ROOT = Path(__file__).resolve().parents[1]


def _default_wiki_root() -> Path:
    return load_config().wiki_root


def _read_tasks(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or not value:
        raise ValueError(f"Smoke task file must contain a non-empty array: {path}")
    if any(not isinstance(item, dict) for item in value):
        raise ValueError(f"Smoke task file contains a non-object entry: {path}")
    return [dict(item) for item in value]


def _cli(wiki_root: Path, arguments: list[str]) -> dict[str, Any]:
    environment = os.environ.copy()
    source_path = str(ROOT / "src")
    environment["PYTHONPATH"] = (
        source_path + os.pathsep + environment.get("PYTHONPATH", "")
    )
    completed = subprocess.run(
        [sys.executable, "-m", "zotero_companion.cli", *arguments],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(
            f"CLI command failed ({completed.returncode}): {' '.join(arguments)}; {detail}"
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"CLI command did not return JSON: {' '.join(arguments)}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"CLI command returned a non-object: {' '.join(arguments)}")
    return payload


def _assert_public_global_context(wiki_root: Path, query: str) -> dict[str, Any]:
    context = _cli(
        wiki_root,
        [
            "wiki-context",
            "--global",
            "--query",
            query,
            "--limit",
            "8",
            "--wiki-root",
            str(wiki_root),
            "--json",
        ],
    )
    if context.get("read_only") is not True:
        raise RuntimeError("global context did not declare read_only=true")
    if not context.get("matched_source_keys"):
        raise RuntimeError("global context did not hydrate matched Zotero keys")
    if not context.get("evidence_hits"):
        raise RuntimeError("global context did not hydrate companion evidence hits")
    if not context.get("briefs"):
        raise RuntimeError("global context did not expose matched brief paths")
    if any(hit.get("hash_matches") is not True for hit in context["evidence_hits"]):
        raise RuntimeError("global context returned an evidence hash mismatch")
    return {
        "matched_source_keys": len(context["matched_source_keys"]),
        "briefs": len(context["briefs"]),
        "evidence_hits": len(context["evidence_hits"]),
        "coverage_ratio": context.get("evidence_coverage", {}).get("coverage_ratio"),
    }


def run_smoke(
    wiki_root: Path = ROOT / "wiki",
    tasks_path: Path = ROOT / "benchmarks/agent_tasks.json",
    *,
    task_limit: int | None = None,
) -> dict[str, Any]:
    """Run the public command contract and return a compact report."""

    tasks = _read_tasks(tasks_path)
    if task_limit is not None:
        if task_limit < 1:
            raise ValueError("task_limit must be positive")
        tasks = tasks[:task_limit]
    global_result = _assert_public_global_context(wiki_root, "Born solvation shell")
    results: list[dict[str, Any]] = []
    for task in tasks:
        task_id = str(task.get("id", ""))
        source_keys = [str(key) for key in task.get("source_keys", []) if str(key)]
        if not source_keys:
            raise ValueError(f"Smoke task has no source_keys: {task_id}")
        source_key = source_keys[0]
        evidence_query = str(task.get("evidence_query", task.get("query", "")))
        expected_record_id = str(task.get("expected_record_id", ""))

        search = _cli(
            wiki_root,
            [
                "wiki-record-search",
                str(task.get("query", "")),
                "--limit",
                "8",
                "--wiki-root",
                str(wiki_root),
                "--json",
            ],
        )
        expected_found = any(
            item.get("record_id") == expected_record_id
            for item in search.get("records", [])
        )

        evidence = _cli(
            wiki_root,
            [
                "wiki-evidence",
                source_key,
                "--query",
                evidence_query,
                "--limit",
                "4",
                "--wiki-root",
                str(wiki_root),
                "--json",
            ],
        )
        passages = evidence.get("passages", [])
        evidence_ok = len(passages) >= int(task.get("min_evidence_hits", 0) or 0)
        evidence_ok = evidence_ok and all(
            passage.get("zotero_attachment_key")
            and passage.get("locator")
            for passage in passages
        )
        evidence_files = evidence.get("files", [])
        evidence_ok = evidence_ok and all(
            file.get("hash_matches") is True
            for file in evidence_files
            if file.get("searchable") is True
        )
        pdf_passages = [passage for passage in passages if passage.get("format") == "pdf"]

        source = _cli(
            wiki_root,
            [
                "wiki-source",
                source_key,
                "--wiki-root",
                str(wiki_root),
                "--json",
            ],
        )
        source_wiki = source.get("wiki", {})
        source_ok = source.get("zotero_key") == source_key and isinstance(source_wiki, dict)
        source_ok = source_ok and isinstance(source_wiki.get("brief"), dict)
        source_ok = source_ok and isinstance(source_wiki.get("evidence"), dict)

        record = _cli(
            wiki_root,
            [
                "wiki-record",
                expected_record_id,
                "--wiki-root",
                str(wiki_root),
                "--json",
            ],
        )
        lineage = _cli(
            wiki_root,
            [
                "wiki-lineage",
                expected_record_id,
                "--wiki-root",
                str(wiki_root),
                "--json",
            ],
        )
        passed = bool(
            expected_found
            and evidence_ok
            and not pdf_passages
            and source_ok
            and record.get("record_id") == expected_record_id
            and lineage.get("read_only") is True
            and search.get("read_only") is True
        )
        results.append(
            {
                "id": task_id,
                "passed": passed,
                "record_found": expected_found,
                "evidence_hits": len(passages),
                "evidence_auditable": evidence_ok,
                "source_routes_present": source_ok,
                "lineage_read_only": lineage.get("read_only") is True,
                "full_pdf_reads": bool(pdf_passages),
                "read_only": True,
            }
        )

    return {
        "schema_version": 1,
        "workflow": "public-cli-agent-smoke",
        "task_file": str(tasks_path.relative_to(ROOT)),
        "wiki_root": str(wiki_root),
        "global_context": global_result,
        "tasks": results,
        "summary": {
            "task_count": len(results),
            "passed_count": sum(1 for result in results if result["passed"]),
            "all_read_only": all(result["read_only"] for result in results),
            "full_pdf_reads": sum(1 for result in results if result["full_pdf_reads"]),
            "zotero_mutation": False,
            "repository_writes": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wiki-root", type=Path, default=_default_wiki_root())
    parser.add_argument("--tasks", type=Path, default=ROOT / "benchmarks/agent_tasks.json")
    parser.add_argument("--task-limit", type=int)
    parser.add_argument("--out", type=Path, help="explicitly write the report to this path")
    parser.add_argument("--json", action="store_true", help="emit JSON (the default output)")
    args = parser.parse_args()
    result = run_smoke(args.wiki_root, args.tasks, task_limit=args.task_limit)
    if args.out:
        args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["summary"]["passed_count"] == result["summary"]["task_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
