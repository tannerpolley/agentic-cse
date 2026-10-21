"""Read-only corpus coverage and curation-gap reporting.

The triage index answers *which* sources are discoverable.  This module answers
*how much* of the discoverable corpus has reached each deliberate curation
stage, without treating missing briefs or evidence as errors.  It is intended
to keep broad-corpus work bounded and reviewable rather than encouraging bulk
summarization.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .manifests import load_manifests
from .records import load_records

TRIAGE_FILENAME = "triage.json"


class CoverageError(ValueError):
    """Raised when the generated triage layer cannot support a coverage report."""


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 3)


def _load_triage(root: Path) -> dict[str, Any]:
    path = Path(root) / TRIAGE_FILENAME
    if not path.exists():
        raise CoverageError(f"Triage index is missing: {path}; run wiki-index --apply first")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CoverageError(f"Could not read triage index {path}: {exc}") from exc
    if not isinstance(value, Mapping):
        raise CoverageError(f"Triage index is not an object: {path}")
    return dict(value)


def _relevant(entry: Mapping[str, Any]) -> bool:
    classification = entry.get("classification", {})
    relevance = classification.get("relevance", "") if isinstance(classification, Mapping) else ""
    return bool(entry.get("projects")) or relevance in {"candidate", "relevant", "uncertain"}


def _examples(entries: Sequence[Mapping[str, Any]], *, limit: int) -> list[dict[str, str]]:
    return [
        {
            "zotero_key": str(entry.get("zotero_key", "")),
            "title": str(entry.get("title", "")),
        }
        for entry in entries[:limit]
    ]


def coverage_report(
    root: Path = Path("wiki"),
    *,
    limit: int = 20,
) -> dict[str, Any]:
    """Return deterministic, read-only coverage metrics for the full corpus."""

    if limit < 1:
        raise ValueError("limit must be positive")
    root = Path(root)
    triage = _load_triage(root)
    raw_entries = triage.get("entries", [])
    if not isinstance(raw_entries, Sequence) or isinstance(raw_entries, (str, bytes)):
        raise CoverageError(f"{root / TRIAGE_FILENAME}: entries must be an array")
    entries = [dict(entry) for entry in raw_entries if isinstance(entry, Mapping)]
    total = len(entries)
    source_count = int(triage.get("source_count", total) or 0)
    warnings: list[str] = []
    if source_count != total:
        warnings.append(
            f"Triage source count {source_count} does not match its entry count {total}"
        )

    classified = [
        entry
        for entry in entries
        if str((entry.get("classification") or {}).get("state", "")) != "unassigned"
    ]
    evidence_ready = [
        entry
        for entry in entries
        if int((entry.get("evidence") or {}).get("chunk_count", 0) or 0) > 0
    ]
    briefed = [entry for entry in entries if entry.get("status") == "briefed"]
    claims_curated = [
        entry
        for entry in entries
        if entry.get("status") == "claims-curated" or entry.get("claim_paths")
    ]
    relevant = [entry for entry in entries if _relevant(entry)]
    relevant_without_brief = [entry for entry in relevant if entry.get("status") != "briefed"]
    relevant_without_evidence = [
        entry
        for entry in relevant
        if int((entry.get("evidence") or {}).get("chunk_count", 0) or 0) == 0
    ]
    unclassified = [
        entry
        for entry in entries
        if str((entry.get("classification") or {}).get("state", "")) == "unassigned"
    ]

    records = load_records(root)
    source_keys_with_records: set[str] = set()
    for record in records:
        provenance = record.get("provenance", {})
        sources = provenance.get("sources", []) if isinstance(provenance, Mapping) else []
        if not isinstance(sources, Sequence) or isinstance(sources, (str, bytes)):
            continue
        source_keys_with_records.update(
            str(source.get("zotero_key", "")).strip()
            for source in sources
            if isinstance(source, Mapping) and str(source.get("zotero_key", "")).strip()
        )
    relevant_without_record = [
        entry for entry in relevant if str(entry.get("zotero_key", "")) not in source_keys_with_records
    ]
    validation_records = [
        record for record in records if record.get("record_type") == "validation_run"
    ]
    registry_linked_records = [record for record in records if record.get("registry_refs")]
    manifests = load_manifests(root)
    manifests_with_validation = [
        manifest for manifest in manifests if manifest.get("validation_runs")
    ]

    queues: dict[str, dict[str, Any]] = {}
    for name, queue in sorted((triage.get("queues") or {}).items()):
        if not isinstance(queue, Sequence) or isinstance(queue, (str, bytes)):
            continue
        keys = {str(key) for key in queue}
        selected = [entry for entry in entries if str(entry.get("zotero_key")) in keys]
        queues[str(name)] = {
            "count": len(selected),
            "examples": _examples(selected, limit=limit),
        }

    gaps = [
        {
            "kind": "unclassified",
            "count": len(unclassified),
            "examples": _examples(unclassified, limit=limit),
            "next_command": "wiki-triage --queue needs_classification --json",
        },
        {
            "kind": "relevant_without_brief",
            "count": len(relevant_without_brief),
            "examples": _examples(relevant_without_brief, limit=limit),
            "next_command": "wiki-triage --queue unbriefed_relevant --json",
        },
        {
            "kind": "relevant_without_evidence",
            "count": len(relevant_without_evidence),
            "examples": _examples(relevant_without_evidence, limit=limit),
            "next_command": "wiki-evidence <ZOTERO_KEY> --query '<terms>' --json",
        },
        {
            "kind": "relevant_without_typed_record",
            "count": len(relevant_without_record),
            "examples": _examples(relevant_without_record, limit=limit),
            "next_command": "wiki-record-template <record_type> --zotero-key <ZOTERO_KEY> --json",
        },
    ]

    return {
        "ok": not warnings,
        "wiki_root": str(root),
        "source_count": source_count,
        "coverage": {
            "classification": {
                "covered": len(classified),
                "total": total,
                "ratio": _ratio(len(classified), total),
            },
            "evidence": {
                "covered": len(evidence_ready),
                "total": total,
                "ratio": _ratio(len(evidence_ready), total),
            },
            "briefs": {
                "covered": len(briefed),
                "total": total,
                "ratio": _ratio(len(briefed), total),
                "relevant_covered": len([entry for entry in relevant if entry.get("status") == "briefed"]),
                "relevant_total": len(relevant),
                "relevant_ratio": _ratio(
                    len([entry for entry in relevant if entry.get("status") == "briefed"]),
                    len(relevant),
                ),
            },
            "claims": {
                "source_count": len(claims_curated),
                "total_records": len(records),
            },
            "typed_records": {
                "count": len(records),
                "source_keys_covered": len(source_keys_with_records),
                "record_types": {
                    str(record_type): sum(
                        1 for record in records if record.get("record_type") == record_type
                    )
                    for record_type in sorted(
                        {str(record.get("record_type")) for record in records}
                    )
                },
            },
            "registry": {
                "linked_record_count": len(registry_linked_records),
                "project_manifest_count": len(manifests),
                "manifests_with_validation": len(manifests_with_validation),
            },
            "validation": {
                "record_count": len(validation_records),
                "project_manifests_with_validation": len(manifests_with_validation),
            },
        },
        "queues": queues,
        "gaps": gaps,
        "warnings": warnings,
        "read_only": True,
        "zotero_mutation": False,
        "pdf_conversion": False,
    }


__all__ = ["CoverageError", "coverage_report"]
