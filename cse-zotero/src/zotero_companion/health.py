"""Read-only dependency health and on-demand review reporting.

The wiki has several deliberately separate layers: generated Zotero source
records, evidence companions, curated knowledge records, typed relations,
project manifests, and registry references.  This module connects those
layers for review purposes without changing any of them.  A changed source or
registry input conservatively propagates through the linked record component
so an agent does not miss a downstream paper interpretation, equation,
workflow, implementation pointer, or validation run.
"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from .manifests import lint_manifests
from .records import lint_records, load_records, load_relations

ATTENTION_STATUSES = {"needs-review", "proposed", "open"}


def _values(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _record_source_keys(record: Mapping[str, Any]) -> set[str]:
    provenance = record.get("provenance", {})
    sources = provenance.get("sources", []) if isinstance(provenance, Mapping) else []
    return {
        str(source.get("zotero_key")).strip()
        for source in sources
        if isinstance(source, Mapping) and str(source.get("zotero_key", "")).strip()
    }


def _record_registry_ids(record: Mapping[str, Any]) -> set[str]:
    return {
        str(reference.get("registry_id")).strip()
        for reference in record.get("registry_refs", []) or []
        if isinstance(reference, Mapping) and str(reference.get("registry_id", "")).strip()
    }


def _registry_tokens(value: str) -> set[str]:
    """Return equivalent forms for CLI and record registry identifiers."""

    token = str(value).strip()
    if not token:
        return set()
    if token.startswith("registry:"):
        token = token.split(":", 1)[1]
    return {token, f"registry:{token}"}


def _record_reference_ids(record: Mapping[str, Any]) -> set[str]:
    references: set[str] = set()
    provenance = record.get("provenance", {})
    if isinstance(provenance, Mapping):
        references.update(_values(provenance.get("derived_from")))
        for source in provenance.get("sources", []) or []:
            if isinstance(source, Mapping) and str(source.get("record_id", "")).strip():
                references.add(str(source["record_id"]).strip())
    references.update(_values(record.get("related_records")))
    references.update(_values(record.get("validation_refs")))
    references.update(
        value
        for value in _values(record.get("inputs"))
        if ":" in value
    )
    return references


def _dependency_graph(
    records: Mapping[str, Mapping[str, Any]],
    relations: Iterable[Mapping[str, Any]],
) -> dict[str, set[str]]:
    """Build a conservative undirected graph for review propagation.

    Relation vocabulary is intentionally still small and some relations are
    explanatory rather than strict data-flow edges.  Treating linked record
    endpoints as a review component avoids false negatives while the output
    labels the propagated entries as conservative downstream review.
    """

    graph: dict[str, set[str]] = defaultdict(set)

    def connect(left: str, right: str) -> None:
        if not left or not right or left == right:
            return
        graph[left].add(right)
        graph[right].add(left)

    for record_id, record in records.items():
        graph.setdefault(record_id, set())
        for source_key in _record_source_keys(record):
            connect(f"source:{source_key}", record_id)
        for registry_id in _record_registry_ids(record):
            connect(f"registry:{registry_id}", record_id)
        for reference_id in _record_reference_ids(record):
            if reference_id in records:
                connect(reference_id, record_id)

    for relation in relations:
        source = str(relation.get("source", "")).strip()
        target = str(relation.get("target", "")).strip()
        if source in records and target in records:
            connect(source, target)

    return dict(graph)


def _evidence_orphan_reasons(root: Path, record: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    provenance = record.get("provenance", {})
    sources = provenance.get("sources", []) if isinstance(provenance, Mapping) else []
    for source in sources or []:
        if not isinstance(source, Mapping):
            continue
        evidence_path = str(source.get("evidence_path", "")).strip()
        if not evidence_path:
            continue
        candidate = Path(evidence_path)
        candidates = [candidate] if candidate.is_absolute() else [root.parent / candidate, root / candidate]
        if not any(item.exists() for item in candidates):
            reasons.append(f"missing evidence path {evidence_path}")
    return reasons


def _orphan_reasons(
    root: Path,
    record: Mapping[str, Any],
    record_ids: set[str],
    registry_root: Path | None,
) -> list[str]:
    reasons = _evidence_orphan_reasons(root, record)
    for reference_id in _record_reference_ids(record):
        if reference_id.startswith(("source:", "registry:", "code:", "project:", "claim:")):
            continue
        if ":" in reference_id and reference_id not in record_ids:
            reasons.append(f"unresolved record dependency {reference_id}")
    if registry_root is not None:
        for reference in record.get("registry_refs", []) or []:
            if not isinstance(reference, Mapping):
                continue
            relative_path = str(reference.get("path", "")).strip()
            if relative_path and not (registry_root / relative_path).resolve().exists():
                reasons.append(f"missing registry path {relative_path}")
    return reasons


def health_report(
    root: Path = Path("wiki"),
    *,
    stale_source_keys: Iterable[str] = (),
    changed_registry_ids: Iterable[str] = (),
    record_ids: Iterable[str] = (),
    registry_root: str | Path | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Return dependency health and a bounded, read-only review queue."""

    if limit < 1:
        raise ValueError("limit must be positive")
    root = Path(root)
    records = load_records(root)
    record_map = {
        str(record["record_id"]): record
        for record in records
        if isinstance(record.get("record_id"), str)
    }
    relations = load_relations(root)
    graph = _dependency_graph(record_map, relations)
    source_keys = {
        str(value).strip() for value in stale_source_keys if str(value).strip()
    }
    registry_values = {str(value).strip() for value in changed_registry_ids if str(value).strip()}
    explicit_record_ids = {str(value).strip() for value in record_ids if str(value).strip()}

    direct_reasons: dict[str, set[str]] = defaultdict(set)
    seed_nodes: set[str] = set()
    for source_key in source_keys:
        node = f"source:{source_key}"
        seed_nodes.add(node)
        for record_id, record in record_map.items():
            if source_key in _record_source_keys(record):
                direct_reasons[record_id].add(f"stale Zotero source {source_key}")
    for value in registry_values:
        tokens = _registry_tokens(value)
        seed_nodes.update(tokens)
        for record_id, record in record_map.items():
            if _record_registry_ids(record) & tokens:
                direct_reasons[record_id].add(f"changed registry reference {value}")
    for record_id in explicit_record_ids:
        if record_id in record_map:
            seed_nodes.add(record_id)
            direct_reasons[record_id].add("explicitly requested review")

    affected: set[str] = set(direct_reasons)
    queue: deque[str] = deque(seed_nodes)
    visited = set(seed_nodes)
    while queue:
        node = queue.popleft()
        for neighbor in sorted(graph.get(node, set())):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
            if neighbor in record_map:
                affected.add(neighbor)

    orphaned: list[dict[str, Any]] = []
    resolved_registry = None
    if registry_root is not None:
        candidate = Path(registry_root)
        resolved_registry = (root.parent / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    for record_id, record in sorted(record_map.items()):
        reasons = _orphan_reasons(root, record, set(record_map), resolved_registry)
        if reasons:
            orphaned.append({"record_id": record_id, "reasons": reasons})
            affected.add(record_id)

    review_queue: list[dict[str, Any]] = []
    for record_id in sorted(affected):
        record = record_map[record_id]
        reasons = sorted(direct_reasons.get(record_id, set()))
        if not reasons:
            reasons = ["conservative dependency propagation from a changed input"]
        review_queue.append(
            {
                "record_id": record_id,
                "record_type": record.get("record_type", ""),
                "title": record.get("title", ""),
                "status": record.get("status", ""),
                "confidence": record.get("confidence", ""),
                "impact": "direct" if record_id in direct_reasons else "propagated",
                "reasons": reasons,
                "source_keys": sorted(_record_source_keys(record)),
                "registry_ids": sorted(_record_registry_ids(record)),
            }
        )
    review_queue.sort(key=lambda item: (item["impact"] != "direct", item["record_id"]))

    attention_queue = [
        {
            "record_id": str(record["record_id"]),
            "record_type": record.get("record_type", ""),
            "title": record.get("title", ""),
            "status": record.get("status", ""),
            "confidence": record.get("confidence", ""),
            "reasons": ["status requires deliberate review"],
        }
        for record in sorted(records, key=lambda item: str(item.get("record_id", "")))
        if record.get("status") in ATTENTION_STATUSES
    ]
    contradictions = [
        {
            key: relation.get(key)
            for key in ("relation_id", "relation_type", "source", "target", "rationale", "status")
            if key in relation
        }
        for relation in relations
        if relation.get("relation_type") == "contradicts"
    ]
    superseded = [
        {
            "record_id": str(record["record_id"]),
            "title": record.get("title", ""),
            "status": record.get("status", ""),
        }
        for record in sorted(records, key=lambda item: str(item.get("record_id", "")))
        if record.get("status") == "superseded"
    ]
    record_lint = lint_records(root, registry_root=registry_root)
    manifest_lint = lint_manifests(root, registry_root=registry_root)
    structural_ok = bool(record_lint.get("ok") and manifest_lint.get("ok"))
    review_required = bool(
        review_queue
        or attention_queue
        or orphaned
        or contradictions
    )
    return {
        "ok": bool(structural_ok and not contradictions),
        "structural_ok": structural_ok,
        "review_required": review_required,
        "inputs": {
            "stale_source_keys": sorted(source_keys),
            "changed_registry_ids": sorted(registry_values),
            "record_ids": sorted(explicit_record_ids),
        },
        "errors": [],
        "review_queue": review_queue[:limit],
        "review_queue_total": len(review_queue),
        "attention_queue": attention_queue[:limit],
        "attention_queue_total": len(attention_queue),
        "contradictions": contradictions,
        "superseded": superseded,
        "orphaned": orphaned[:limit],
        "orphaned_total": len(orphaned),
        "lint": record_lint,
        "manifest_lint": manifest_lint,
        "graph": {
            "record_count": len(record_map),
            "relation_count": len(relations),
            "conservative_review_edges": sum(len(neighbors) for neighbors in graph.values()) // 2,
        },
        "read_only": True,
    }


__all__ = ["ATTENTION_STATUSES", "health_report"]
