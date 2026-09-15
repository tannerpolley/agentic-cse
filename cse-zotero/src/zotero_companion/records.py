"""Typed, provenance-first knowledge records and read-only lineage tools.

The generated Zotero source layer is intentionally kept in :mod:`wiki`.  This
module owns the small curated record surface that connects source evidence to
equations, data references, ideas, workflows, implementations, and validation
runs without making any of those things look like generic paper claims.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict, deque
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

RECORDS_DIRNAME = "records"
RELATIONS_FILENAME = "relations.json"
RECORD_SCHEMA_VERSION = 1
RELATION_SCHEMA_VERSION = 1

RECORD_TYPES = {
    "paper_brief",
    "claim",
    "equation",
    "dataset_reference",
    "parameter_reference",
    "correlation_reference",
    "idea",
    "insight",
    "workflow",
    "implementation_reference",
    "validation_run",
}
RECORD_ID_PREFIXES = {
    "paper_brief": "paper",
    "claim": "claim",
    "equation": "equation",
    "dataset_reference": "dataset",
    "parameter_reference": "parameter",
    "correlation_reference": "correlation",
    "idea": "idea",
    "insight": "insight",
    "workflow": "workflow",
    "implementation_reference": "implementation",
    "validation_run": "validation",
}
DERIVATION_KINDS = {
    "source-reported",
    "normalized",
    "inferred",
    "project-derived",
    "implementation-observed",
}
RECORD_STATUSES = {
    "proposed",
    "source-backed",
    "evidence-ready",
    "accepted",
    "open",
    "needs-review",
    "superseded",
    "rejected",
}
CONFIDENCES = {"high", "medium", "low", "not-assessed"}
RELATION_TYPES = {
    "extracted_from",
    "supports",
    "contradicts",
    "supersedes",
    "depends_on",
    "derived_from",
    "implemented_by",
    "uses",
    "validates",
    "contextualizes",
    "related_to",
}
RELATION_STATUSES = {"proposed", "accepted", "needs-review", "rejected"}
EXTERNAL_PREFIXES = {
    "claim",
    "code",
    "project",
    "registry",
    "source",
    "zotero",
}
_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*:[a-z0-9][a-z0-9._-]*$")


class RecordError(ValueError):
    """Raised when a record lookup or record contract cannot be satisfied."""


def _display(path: Path, *, base: Path | None = None) -> str:
    try:
        if base is not None:
            return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        pass
    return path.as_posix()


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RecordError(f"Could not read JSON {path}: {exc}") from exc


def _record_paths(root: Path) -> list[Path]:
    directory = Path(root) / RECORDS_DIRNAME
    if not directory.exists():
        return []
    return sorted(
        path
        for path in directory.rglob("*.json")
        if path.is_file() and path.name.casefold() != "readme.json"
    )


def load_records(root: Path = Path("wiki")) -> list[dict[str, Any]]:
    """Load all curated JSON records in deterministic path order."""

    loaded: list[dict[str, Any]] = []
    for path in _record_paths(Path(root)):
        value = _read_json(path)
        if isinstance(value, Mapping):
            record = dict(value)
            record["_path"] = _display(path)
            loaded.append(record)
    return loaded


def load_relations(root: Path = Path("wiki")) -> list[dict[str, Any]]:
    """Load the typed relation file, returning an empty list when absent."""

    path = Path(root) / RELATIONS_FILENAME
    if not path.exists():
        return []
    value = _read_json(path)
    if isinstance(value, Mapping):
        relations = value.get("relations", [])
    else:
        relations = value
    if not isinstance(relations, Sequence) or isinstance(relations, (str, bytes)):
        raise RecordError(f"Relations must be a JSON array in {path}")
    return [dict(item) for item in relations if isinstance(item, Mapping)]


def _prefix(value: str) -> str:
    return value.split(":", 1)[0] if ":" in value else ""


def _path_from_reference(root: Path, reference: str, *, base: Path | None = None) -> Path:
    """Resolve a repo/wiki-relative path without allowing an escape."""

    repo_root = Path(root).resolve().parent if Path(root).name == "wiki" else Path(root).resolve()
    raw = Path(str(reference))
    if raw.is_absolute():
        candidate = raw.resolve()
    else:
        candidates = []
        if base is not None:
            candidates.append((base / raw).resolve())
        candidates.extend(((repo_root / raw).resolve(), (Path(root) / raw).resolve()))
        candidate = next((item for item in candidates if item.exists()), candidates[0])
    allowed_roots = [repo_root]
    if base is not None:
        allowed_roots.append(Path(base).resolve())
    if not any(candidate == allowed or allowed in candidate.parents for allowed in allowed_roots):
        raise RecordError(f"Reference escapes repository boundary: {reference}")
    return candidate


def _source_record(root: Path, zotero_key: str) -> dict[str, Any] | None:
    path = Path(root) / "sources" / str(zotero_key) / "record.json"
    if not path.exists():
        return None
    value = _read_json(path)
    return dict(value) if isinstance(value, Mapping) else None


def _legacy_external_ids(root: Path) -> set[str]:
    identifiers = {f"source:{path.parent.name}" for path in (Path(root) / "sources").glob("*/record.json")}
    for path in sorted((Path(root) / "claims").glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        match = re.search(r"^-\s*claim_id:\s*`?([^`\s]+)", text, flags=re.MULTILINE)
        if match:
            identifiers.add(f"claim:{match.group(1)}")
    for path in sorted((Path(root) / "projects").glob("*.md")):
        identifiers.add(f"project:{path.stem}")
    return identifiers


def _required_string(record: Mapping[str, Any], field: str, errors: list[str], path: str) -> None:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{path}: missing required non-empty {field}")


def validate_record(record: Mapping[str, Any], path: str = "<record>") -> list[str]:
    """Return human-readable contract errors for one record."""

    errors: list[str] = []
    if record.get("schema_version") != RECORD_SCHEMA_VERSION:
        errors.append(f"{path}: schema_version must be {RECORD_SCHEMA_VERSION}")
    record_type = record.get("record_type")
    if record_type not in RECORD_TYPES:
        errors.append(f"{path}: unsupported record_type {record_type!r}")
    record_id = record.get("record_id")
    if not isinstance(record_id, str) or not _ID_PATTERN.fullmatch(record_id):
        errors.append(f"{path}: record_id must use a type-prefixed stable ID")
    elif record_type in RECORD_ID_PREFIXES and _prefix(record_id) != RECORD_ID_PREFIXES[record_type]:
        errors.append(
            f"{path}: record_id prefix {_prefix(record_id)!r} does not match record_type {record_type!r}"
        )
    for field in ("title", "summary"):
        _required_string(record, field, errors, path)
    if record.get("status") not in RECORD_STATUSES:
        errors.append(f"{path}: unsupported status {record.get('status')!r}")
    if record.get("confidence") not in CONFIDENCES:
        errors.append(f"{path}: unsupported confidence {record.get('confidence')!r}")

    provenance = record.get("provenance")
    if not isinstance(provenance, Mapping):
        errors.append(f"{path}: provenance must be an object")
        return errors
    if provenance.get("derivation_kind") not in DERIVATION_KINDS:
        errors.append(f"{path}: provenance.derivation_kind is invalid")
    sources = provenance.get("sources")
    derived_from = provenance.get("derived_from")
    if not isinstance(sources, Sequence) or isinstance(sources, (str, bytes)):
        errors.append(f"{path}: provenance.sources must be an array")
        sources = []
    if not isinstance(derived_from, Sequence) or isinstance(derived_from, (str, bytes)):
        errors.append(f"{path}: provenance.derived_from must be an array")
        derived_from = []
    if not sources and not derived_from:
        errors.append(f"{path}: provenance needs sources or derived_from")
    for index, source in enumerate(sources):
        if not isinstance(source, Mapping):
            errors.append(f"{path}: provenance.sources[{index}] must be an object")
            continue
        if not str(source.get("zotero_key", "")).strip() and not str(source.get("record_id", "")).strip():
            errors.append(f"{path}: provenance.sources[{index}] needs zotero_key or record_id")
        if source.get("zotero_key") and not isinstance(source.get("locator"), Mapping):
            errors.append(f"{path}: provenance.sources[{index}] needs a locator")
    for index, item in enumerate(derived_from):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{path}: provenance.derived_from[{index}] must be a non-empty ID")

    if record_type == "equation" and not str(record.get("expression", "")).strip():
        errors.append(f"{path}: equation records need expression")
    if record_type in {"dataset_reference", "parameter_reference", "correlation_reference"}:
        refs = record.get("registry_refs")
        if not isinstance(refs, Sequence) or isinstance(refs, (str, bytes)) or not refs:
            errors.append(f"{path}: {record_type} records need registry_refs (use status proposed when unresolved)")
    if record_type == "implementation_reference" and not str(record.get("repository", "")).strip():
        errors.append(f"{path}: implementation_reference records need repository")
    if record_type == "validation_run" and not isinstance(record.get("inputs"), Sequence):
        errors.append(f"{path}: validation_run records need inputs")
    return errors


def _registry_ids(registry_root: Path) -> set[str]:
    identifiers: set[str] = set()
    for path in sorted(registry_root.rglob("*.json")):
        try:
            value = _read_json(path)
        except RecordError:
            continue
        if isinstance(value, Mapping):
            for field in ("observation_id", "dataset_id", "parameter_set_id", "correlation_id", "validation_id"):
                candidate = value.get(field)
                if isinstance(candidate, str) and candidate:
                    identifiers.add(candidate)
    return identifiers


def _registry_root(root: Path, value: str | Path) -> Path:
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = (Path(root).resolve().parent / candidate).resolve()
    return candidate.resolve()


def _workspace_root(root: Path) -> Path:
    repo_root = Path(root).resolve().parent if Path(root).name == "wiki" else Path(root).resolve()
    return repo_root.parent


def _check_record_references(
    root: Path,
    record: Mapping[str, Any],
    *,
    registry_root: Path | None,
    warnings: list[str],
    errors: list[str],
) -> None:
    path = str(record.get("_path", "<record>"))
    provenance = record.get("provenance", {})
    sources = provenance.get("sources", []) if isinstance(provenance, Mapping) else []
    for index, source in enumerate(sources):
        if not isinstance(source, Mapping) or not source.get("zotero_key"):
            continue
        key = str(source["zotero_key"])
        source_record = _source_record(root, key)
        if source_record is None:
            errors.append(f"{path}: missing generated Zotero source {key}")
            continue
        attachment_key = str(source.get("attachment_key", ""))
        if attachment_key:
            attachment_keys = {
                str(item.get("key"))
                for item in source_record.get("attachments", [])
                if isinstance(item, Mapping)
            }
            if attachment_key not in attachment_keys:
                errors.append(f"{path}: source {key} does not declare attachment {attachment_key}")
        evidence_path = source.get("evidence_path")
        if evidence_path:
            try:
                evidence = _path_from_reference(root, str(evidence_path))
            except RecordError as exc:
                errors.append(f"{path}: source {key} evidence path invalid: {exc}")
            else:
                if not evidence.exists():
                    errors.append(f"{path}: missing evidence path {evidence_path}")

    for ref_index, reference in enumerate(record.get("registry_refs", []) or []):
        if not isinstance(reference, Mapping):
            errors.append(f"{path}: registry_refs[{ref_index}] must be an object")
            continue
        if registry_root is None:
            warnings.append(f"{path}: registry reference was not checked (pass --registry-root)")
            continue
        ref_path = reference.get("path")
        if ref_path:
            candidate = (registry_root / str(ref_path)).resolve()
            if registry_root != candidate and registry_root not in candidate.parents:
                errors.append(f"{path}: registry path escapes registry root: {ref_path}")
            elif not candidate.exists():
                errors.append(f"{path}: missing registry path {ref_path}")
        registry_id = str(reference.get("registry_id", ""))
        if registry_id and registry_id not in _registry_ids(registry_root):
            warnings.append(f"{path}: registry ID not found in scanned JSON records: {registry_id}")

    for index, reference in enumerate(record.get("implementation_refs", []) or []):
        if not isinstance(reference, Mapping):
            errors.append(f"{path}: implementation_refs[{index}] must be an object")
            continue
        repository = str(reference.get("repository", "")).strip()
        relative_path = str(reference.get("path", "")).strip()
        if not repository or not relative_path:
            warnings.append(f"{path}: incomplete implementation reference {index}")
            continue
        candidate = (_workspace_root(root) / repository / relative_path).resolve()
        if not candidate.exists():
            warnings.append(f"{path}: implementation path is unavailable: {repository}/{relative_path}")


def _endpoint_exists(endpoint: str, record_ids: set[str], external_ids: set[str], registry_ids: set[str] | None) -> bool:
    if endpoint in record_ids or endpoint in external_ids:
        return True
    prefix, _, identifier = endpoint.partition(":")
    if prefix == "registry":
        return registry_ids is None or identifier in registry_ids
    if prefix in EXTERNAL_PREFIXES and identifier:
        return True
    return False


def lint_records(
    root: Path = Path("wiki"),
    *,
    registry_root: str | Path | None = None,
) -> dict[str, Any]:
    """Validate records, relations, source references, and optional registry links."""

    root = Path(root)
    errors: list[str] = []
    warnings: list[str] = []
    records = load_records(root)
    record_ids: set[str] = set()
    for record in records:
        path = str(record.get("_path", "<record>"))
        record_id = str(record.get("record_id", ""))
        if record_id in record_ids:
            errors.append(f"{path}: duplicate record_id {record_id}")
        if record_id:
            record_ids.add(record_id)
        errors.extend(validate_record(record, path))

    resolved_registry = _registry_root(root, registry_root) if registry_root is not None else None
    registry_ids = _registry_ids(resolved_registry) if resolved_registry and resolved_registry.exists() else None
    if registry_root is not None and (resolved_registry is None or not resolved_registry.exists()):
        errors.append(f"Registry root does not exist: {resolved_registry}")
    for record in records:
        _check_record_references(
            root,
            record,
            registry_root=resolved_registry,
            warnings=warnings,
            errors=errors,
        )

    external_ids = _legacy_external_ids(root)
    try:
        relations = load_relations(root)
    except RecordError as exc:
        errors.append(str(exc))
        relations = []
    relation_ids: set[str] = set()
    for relation in relations:
        relation_id = str(relation.get("relation_id", ""))
        if relation_id in relation_ids:
            errors.append(f"{RELATIONS_FILENAME}: duplicate relation_id {relation_id}")
        if relation_id:
            relation_ids.add(relation_id)
        for field in ("relation_id", "source", "target", "rationale"):
            if not str(relation.get(field, "")).strip():
                errors.append(f"{RELATIONS_FILENAME}: relation missing {field}")
        if relation.get("relation_type") not in RELATION_TYPES:
            errors.append(f"{RELATIONS_FILENAME}: unsupported relation_type {relation.get('relation_type')!r}")
        if relation.get("status") not in RELATION_STATUSES:
            errors.append(f"{RELATIONS_FILENAME}: unsupported relation status {relation.get('status')!r}")
        for endpoint in (str(relation.get("source", "")), str(relation.get("target", ""))):
            if endpoint and not _endpoint_exists(endpoint, record_ids, external_ids, registry_ids):
                errors.append(f"{RELATIONS_FILENAME}: unresolved relation endpoint {endpoint}")
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "record_count": len(records),
        "relation_count": len(relations),
        "record_types": {
            record_type: sum(1 for record in records if record.get("record_type") == record_type)
            for record_type in sorted(RECORD_TYPES)
            if any(record.get("record_type") == record_type for record in records)
        },
        "registry_checked": resolved_registry is not None,
        "registry_root": str(resolved_registry) if resolved_registry else "",
    }


def _record_map(root: Path) -> dict[str, dict[str, Any]]:
    return {
        str(record["record_id"]): record
        for record in load_records(root)
        if isinstance(record.get("record_id"), str)
    }


def record_lookup(root: Path, record_id: str) -> dict[str, Any]:
    records = _record_map(Path(root))
    try:
        return records[str(record_id)]
    except KeyError as exc:
        raise RecordError(f"Unknown knowledge record: {record_id}") from exc


def search_records(root: Path, *, query: str = "", limit: int = 20) -> list[dict[str, Any]]:
    """Search the small curated record layer without opening source files."""

    if limit < 1:
        raise ValueError("limit must be positive")
    needle = str(query).strip().casefold()
    tokens = [token for token in re.findall(r"[a-z0-9][a-z0-9._+-]*", needle) if len(token) > 1]
    matches: list[tuple[int, dict[str, Any]]] = []
    for record in load_records(Path(root)):
        haystack = " ".join(
            str(record.get(field, ""))
            for field in ("record_id", "record_type", "title", "summary", "expression")
        ).casefold()
        score = sum(haystack.count(token) for token in tokens)
        if tokens and score == 0:
            continue
        result = dict(record)
        result.pop("_path", None)
        matches.append((score, result))
    matches.sort(key=lambda item: (-item[0], str(item[1].get("record_type", "")), str(item[1].get("record_id", ""))))
    return [record for _, record in matches[:limit]]


def _synthetic_edges(root: Path, records: Mapping[str, Mapping[str, Any]]) -> list[tuple[str, str, str]]:
    edges: list[tuple[str, str, str]] = []
    for record_id, record in records.items():
        provenance = record.get("provenance", {})
        if isinstance(provenance, Mapping):
            for upstream in provenance.get("derived_from", []) or []:
                if isinstance(upstream, str) and upstream:
                    edges.append((upstream, record_id, "derived_from"))
            for source in provenance.get("sources", []) or []:
                if isinstance(source, Mapping) and source.get("zotero_key"):
                    edges.append((f"source:{source['zotero_key']}", record_id, "extracted_from"))
        for reference in record.get("registry_refs", []) or []:
            if isinstance(reference, Mapping) and reference.get("registry_id"):
                edges.append((f"registry:{reference['registry_id']}", record_id, "uses"))
        for reference in record.get("implementation_refs", []) or []:
            if isinstance(reference, Mapping):
                repository = str(reference.get("repository", "")).strip()
                path = str(reference.get("path", "")).strip()
                if repository and path:
                    edges.append((record_id, f"code:{repository}/{path}", "implemented_by"))
        for related in record.get("related_records", []) or []:
            if isinstance(related, str) and related:
                edges.append((record_id, related, "related_to"))
    return edges


def lineage(
    root: Path,
    record_id: str,
    *,
    direction: str = "both",
    registry_root: str | Path | None = None,
) -> dict[str, Any]:
    """Trace typed and envelope-declared dependencies around one record."""

    if direction not in {"upstream", "downstream", "both"}:
        raise ValueError("direction must be upstream, downstream, or both")
    root = Path(root)
    records = _record_map(root)
    record = record_lookup(root, record_id)
    relations = load_relations(root)
    edges = _synthetic_edges(root, records)
    for relation in relations:
        if relation.get("source") and relation.get("target"):
            edges.append((str(relation["source"]), str(relation["target"]), str(relation.get("relation_type", "related_to"))))
    upstream_map: dict[str, list[tuple[str, str]]] = defaultdict(list)
    downstream_map: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for source, target, relation_type in edges:
        upstream_map[target].append((source, relation_type))
        downstream_map[source].append((target, relation_type))

    def trace(adjacency: Mapping[str, Sequence[tuple[str, str]]]) -> list[dict[str, str]]:
        visited: set[str] = {str(record_id)}
        queue: deque[str] = deque([str(record_id)])
        result: list[dict[str, str]] = []
        while queue:
            current = queue.popleft()
            for target, relation_type in sorted(adjacency.get(current, [])):
                if target in visited:
                    continue
                visited.add(target)
                queue.append(target)
                result.append({"record_id": target, "relation_type": relation_type})
        return result

    upstream = trace(upstream_map) if direction in {"upstream", "both"} else []
    downstream = trace(downstream_map) if direction in {"downstream", "both"} else []
    checked = lint_records(root, registry_root=registry_root)
    return {
        "record": {key: value for key, value in record.items() if key != "_path"},
        "record_path": record.get("_path", ""),
        "upstream": upstream,
        "downstream": downstream,
        "relation_count": len(relations),
        "lint": checked,
        "read_only": True,
    }


def global_context(
    root: Path,
    *,
    query: str = "",
    limit: int = 12,
    registry_root: str | Path | None = None,
    data_root: str | Path | None = None,
    api: Any | None = None,
) -> dict[str, Any]:
    """Return the documented low-friction starting context for any agent."""

    if limit < 1:
        raise ValueError("limit must be positive")
    root = Path(root)
    resolved_registry_root = (
        _registry_root(root, registry_root)
        if registry_root is not None
        else (
            Path(data_root)
            / "domains"
            / "thermophysical"
            / "source"
            / "registry"
            if data_root is not None
            else None
        )
    )
    warnings: list[str] = []
    triage: dict[str, Any] = {}
    source_matches: list[dict[str, Any]] = []
    try:
        from .wiki import search_wiki, triage_wiki

        triage = triage_wiki(root, limit=limit)
        if query:
            source_matches = search_wiki(root, query=query, limit=limit)
    except Exception as exc:  # pragma: no cover - defensive CLI boundary
        warnings.append(f"Triage unavailable: {exc}")
    try:
        from .wiki import freshness_status

        freshness = freshness_status(root, api=api)
    except Exception as exc:  # pragma: no cover - defensive CLI boundary
        freshness = {"stale": None, "warning": str(exc)}
        warnings.append(f"Freshness unavailable: {exc}")
    records = load_records(root)
    record_matches = search_records(root, query=query, limit=limit)
    relations = load_relations(root)
    from .manifests import load_manifests
    from .health import health_report
    from .coverage import coverage_report

    try:
        coverage = coverage_report(root)
    except Exception as exc:  # pragma: no cover - defensive CLI boundary
        coverage = {"ok": False, "error": str(exc), "read_only": True}
        warnings.append(f"Coverage unavailable: {exc}")
    generated_triage: dict[str, Any] = {}
    triage_path = root / "triage.json"
    if triage_path.exists():
        try:
            loaded = json.loads(triage_path.read_text(encoding="utf-8"))
            if isinstance(loaded, Mapping):
                generated_triage = dict(loaded)
        except (OSError, json.JSONDecodeError):
            warnings.append(f"Could not read generated triage: {triage_path}")
    source_keys: set[str] = {
        str(match.get("zotero_key", ""))
        for match in source_matches
        if str(match.get("zotero_key", "")).strip()
    }
    for record in record_matches:
        provenance = record.get("provenance", {})
        sources = provenance.get("sources", []) if isinstance(provenance, Mapping) else []
        for source in sources:
            if isinstance(source, Mapping) and str(source.get("zotero_key", "")).strip():
                source_keys.add(str(source["zotero_key"]))
    matched_source_keys = sorted(source_keys)
    evidence_hits: list[dict[str, Any]] = []
    try:
        from .wiki import search_evidence_chunks

        if query:
            # Search companions independently of metadata. A term may occur
            # only in evidence, so metadata hits must not gate retrieval.
            evidence_hits = search_evidence_chunks(
                root,
                source_keys=None,
                query=query,
                limit=limit,
            )
            source_keys.update(
                str(hit.get("zotero_key", ""))
                for hit in evidence_hits
                if str(hit.get("zotero_key", "")).strip()
            )
            matched_source_keys = sorted(source_keys)
    except Exception as exc:  # pragma: no cover - defensive CLI boundary
        warnings.append(f"Evidence hydration unavailable: {exc}")
    evidence_coverage: dict[str, Any] = {
        "matched_source_count": len(matched_source_keys),
        "sources_without_indexed_evidence": matched_source_keys,
        "coverage_ratio": None if not matched_source_keys else 0.0,
        "read_only": True,
    }
    if matched_source_keys:
        try:
            from .wiki import (
                evidence_coverage as build_evidence_coverage,
            )

            evidence_coverage = build_evidence_coverage(root, source_keys=matched_source_keys)
            evidence_coverage["read_only"] = True
        except Exception as exc:  # pragma: no cover - defensive CLI boundary
            warnings.append(f"Evidence hydration unavailable: {exc}")
    elif query:
        warnings.append("No Zotero source keys were available to hydrate evidence for this query")
    triage_entries = generated_triage.get("entries", [])
    triage_by_key = {
        str(entry.get("zotero_key")): entry
        for entry in triage_entries
        if isinstance(entry, Mapping) and str(entry.get("zotero_key", "")).strip()
    }
    briefs = []
    for key in matched_source_keys:
        entry = triage_by_key.get(key, {})
        brief_path = str(entry.get("brief_path", ""))
        if brief_path:
            briefs.append(
                {
                    "zotero_key": key,
                    "title": str(entry.get("title", "")),
                    "path": brief_path,
                    "status": str(entry.get("brief_status", "")),
                    "evidence": dict(entry.get("evidence", {}))
                    if isinstance(entry.get("evidence", {}), Mapping)
                    else {},
                }
            )
    stale_source_keys = [
        *freshness.get("live_check", {}).get("changed", []),
        *freshness.get("live_check", {}).get("removed", []),
    ]
    health = health_report(
        root,
        stale_source_keys=stale_source_keys,
        registry_root=resolved_registry_root,
    )
    lint = health["lint"]
    manifest_lint = health["manifest_lint"]
    warnings.extend(lint["warnings"])
    if not health["ok"]:
        warnings.append("Dependency health requires review before promoting this context")
    registry_context: dict[str, Any] = {
        "registry_root": "",
        "query": query,
        "count": 0,
        "total_matches": 0,
        "results": [],
        "warnings": ["No registry root was provided"],
        "read_only": True,
    }
    if resolved_registry_root is not None and query:
        try:
            from .scientific_data import search_registry

            registry_context = search_registry(
                resolved_registry_root,
                query=query,
                limit=limit,
            )
        except Exception as exc:  # pragma: no cover - defensive CLI boundary
            registry_context["warnings"] = [f"Registry discovery unavailable: {exc}"]
            warnings.append(registry_context["warnings"][0])
    elif resolved_registry_root is not None:
        registry_context["registry_root"] = str(
            Path(resolved_registry_root).expanduser().resolve()
        )
        registry_context["warnings"] = ["Registry discovery requires a query"]
    return {
        "scope": "global",
        "start_here": [
            "wiki/index.md",
            "wiki-context --global --query '<question>' --json",
            "wiki-evidence <ZOTERO_KEY> --query '<terms>' --json",
            "wiki-record-search '<terms>' --json",
            "wiki-lineage <RECORD_ID> --json",
            "data-search '<terms>' --json",
            "wiki-health --json",
        ],
        "query": query,
        "source_inventory": {
            "source_count": generated_triage.get("source_count", triage.get("total", 0)),
            "evidence_file_count": generated_triage.get("evidence_file_count", 0),
            "evidence_chunk_count": generated_triage.get("evidence_chunk_count", 0),
            "queue_counts": triage.get("queue_counts", {}),
        },
        "freshness": freshness,
        "records": {
            "count": len(records),
            "matches": record_matches,
            "types": {
                record_type: sum(1 for record in records if record.get("record_type") == record_type)
                for record_type in sorted(RECORD_TYPES)
                if any(record.get("record_type") == record_type for record in records)
            },
        },
        "source_matches": source_matches,
        "matched_source_keys": matched_source_keys,
        "briefs": briefs,
        "evidence_hits": evidence_hits,
        "evidence_coverage": evidence_coverage,
        "data": registry_context,
        "project_manifests": [
            {key: value for key, value in manifest.items() if key != "_path"}
            for manifest in load_manifests(root)
        ],
        "relations": {"count": len(relations)},
        "lint": lint,
        "manifest_lint": manifest_lint,
        "health": {
            "ok": health["ok"],
            "review_queue_total": health["review_queue_total"],
            "attention_queue_total": health["attention_queue_total"],
            "orphaned_total": health["orphaned_total"],
            "contradiction_count": len(health["contradictions"]),
            "read_only": health["read_only"],
        },
        "coverage": coverage,
        "warnings": warnings,
        "read_only": True,
    }


__all__ = [
    "CONFIDENCES",
    "RECORDS_DIRNAME",
    "RECORD_SCHEMA_VERSION",
    "RELATIONS_FILENAME",
    "RELATION_SCHEMA_VERSION",
    "RecordError",
    "global_context",
    "lineage",
    "lint_records",
    "load_records",
    "load_relations",
    "record_lookup",
    "search_records",
    "validate_record",
]
