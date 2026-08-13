"""Read-only project manifest and registry-link validation."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

MANIFESTS_DIRNAME = "manifests"
MANIFEST_SCHEMA_VERSION = 1
MANIFEST_STATUSES = {"scaffold", "proposed", "active", "released", "needs-review"}


class ManifestError(ValueError):
    """Raised when a project manifest cannot be read or selected."""


def _paths(root: Path) -> list[Path]:
    return sorted(
        path
        for path in (Path(root) / MANIFESTS_DIRNAME).glob("*.json")
        if path.is_file() and path.name.casefold() != "readme.json"
    )


def load_manifests(root: Path = Path("wiki")) -> list[dict[str, Any]]:
    manifests: list[dict[str, Any]] = []
    for path in _paths(Path(root)):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ManifestError(f"Could not read manifest {path}: {exc}") from exc
        if isinstance(value, Mapping):
            item = dict(value)
            item["_path"] = path.as_posix()
            manifests.append(item)
    return manifests


def manifest_lookup(root: Path, project_id: str) -> dict[str, Any]:
    for manifest in load_manifests(root):
        if manifest.get("project_id") == project_id:
            return manifest
    raise ManifestError(f"Unknown project manifest: {project_id}")


def _registry_candidate(root: Path, repository: str) -> Path:
    repo_root = Path(root).resolve().parent if Path(root).name == "wiki" else Path(root).resolve()
    candidate = Path(repository)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    return candidate.resolve()


def validate_manifest(
    root: Path,
    manifest: Mapping[str, Any],
    *,
    record_ids: set[str],
    registry_root: Path | None,
) -> list[str]:
    errors: list[str] = []
    path = str(manifest.get("_path", "<manifest>"))
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        errors.append(f"{path}: schema_version must be {MANIFEST_SCHEMA_VERSION}")
    project_id = manifest.get("project_id")
    if not isinstance(project_id, str) or not project_id.strip():
        errors.append(f"{path}: missing project_id")
    if not isinstance(manifest.get("title"), str) or not manifest.get("title", "").strip():
        errors.append(f"{path}: missing title")
    if manifest.get("status") not in MANIFEST_STATUSES:
        errors.append(f"{path}: unsupported status {manifest.get('status')!r}")
    record_values = manifest.get("record_ids", [])
    if not isinstance(record_values, Sequence) or isinstance(record_values, (str, bytes)):
        errors.append(f"{path}: record_ids must be an array")
        record_values = []
    for record_id in record_values:
        if not isinstance(record_id, str) or record_id not in record_ids:
            errors.append(f"{path}: unresolved record_id {record_id}")
    registry = manifest.get("registry")
    if not isinstance(registry, Mapping):
        errors.append(f"{path}: registry must be an object")
    else:
        for field in ("name", "repository", "revision"):
            if not str(registry.get(field, "")).strip():
                errors.append(f"{path}: registry missing {field}")
        repository = str(registry.get("repository", ""))
        if registry_root is not None and repository:
            expected = registry_root.resolve()
            actual = _registry_candidate(root, repository)
            if actual != expected:
                errors.append(f"{path}: registry repository resolves to {actual}, expected {expected}")

    if registry_root is not None:
        for index, reference in enumerate(manifest.get("registry_refs", []) or []):
            if not isinstance(reference, Mapping):
                errors.append(f"{path}: registry_refs[{index}] must be an object")
                continue
            ref_path = str(reference.get("path", ""))
            if ref_path and not (registry_root / ref_path).resolve().exists():
                errors.append(f"{path}: missing registry reference path {ref_path}")
    validation_runs = manifest.get("validation_runs", [])
    if not isinstance(validation_runs, Sequence) or isinstance(validation_runs, (str, bytes)):
        errors.append(f"{path}: validation_runs must be an array")
    else:
        for validation_id in validation_runs:
            if validation_id not in record_ids:
                errors.append(f"{path}: unresolved validation run {validation_id}")
    return errors


def lint_manifests(
    root: Path = Path("wiki"),
    *,
    registry_root: str | Path | None = None,
) -> dict[str, Any]:
    from .records import _registry_root, load_records

    root = Path(root)
    records = load_records(root)
    record_ids = {str(record.get("record_id")) for record in records if record.get("record_id")}
    resolved_registry = _registry_root(root, registry_root) if registry_root is not None else None
    errors: list[str] = []
    warnings: list[str] = []
    if registry_root is not None and (resolved_registry is None or not resolved_registry.exists()):
        errors.append(f"Registry root does not exist: {resolved_registry}")
    manifests = load_manifests(root)
    manifest_ids: set[str] = set()
    for manifest in manifests:
        project_id = str(manifest.get("project_id", ""))
        if project_id in manifest_ids:
            errors.append(f"{manifest.get('_path', '<manifest>')}: duplicate project_id {project_id}")
        if project_id:
            manifest_ids.add(project_id)
        errors.extend(
            validate_manifest(
                root,
                manifest,
                record_ids=record_ids,
                registry_root=resolved_registry,
            )
        )
        if manifest.get("status") == "scaffold":
            warnings.append(f"{manifest.get('_path', '<manifest>')}: scaffold manifest has no curated records yet")
        registry = manifest.get("registry", {})
        if isinstance(registry, Mapping) and registry.get("revision") == "working-tree":
            warnings.append(f"{manifest.get('_path', '<manifest>')}: registry revision is unpinned working-tree")
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "manifest_count": len(manifests),
        "projects": sorted(manifest_ids),
        "registry_checked": resolved_registry is not None,
        "registry_root": str(resolved_registry) if resolved_registry else "",
    }


__all__ = [
    "MANIFEST_SCHEMA_VERSION",
    "MANIFESTS_DIRNAME",
    "ManifestError",
    "lint_manifests",
    "load_manifests",
    "manifest_lookup",
    "validate_manifest",
]
