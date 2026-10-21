"""Read-only release and reproducibility manifest generation."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .health import health_report
from .manifests import lint_manifests, load_manifests
from .records import lint_records, load_records

RELEASE_FILENAME = "release-manifest.json"
RELEASE_SCHEMA_VERSION = 1


class ReleaseError(ValueError):
    """Raised when a release manifest cannot be generated or written."""


def _repo_root(root: Path) -> Path:
    resolved = Path(root).resolve()
    return resolved.parent if resolved.name == "wiki" else resolved


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_state(repo_root: Path) -> dict[str, Any]:
    try:
        revision = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return {"revision": "uncommitted-working-tree", "available": False, "dirty": True}
    try:
        dirty = bool(
            subprocess.run(
                ["git", "-C", str(repo_root), "status", "--short"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
    except (OSError, subprocess.CalledProcessError):
        dirty = True
    return {"revision": revision or "uncommitted-working-tree", "available": True, "dirty": dirty}


def _artifact_paths(root: Path) -> list[Path]:
    candidates = [
        root / "manifest.json",
        root / "catalog.json",
        root / "triage.json",
        root / "relations.json",
    ]
    for pattern in (
        "records/**/*.json",
        "manifests/*.json",
        "evidence/**/manifest.json",
        "evidence/**/*.md",
        "evidence/**/*.mmd",
        "claims/*.md",
        "graphs/*.nodegraph.json",
        "synthesis/*.md",
    ):
        candidates.extend(root.glob(pattern))
    return sorted(
        {
            path.resolve()
            for path in candidates
            if path.is_file() and path.name != RELEASE_FILENAME
        }
    )


def build_release_manifest(
    root: Path = Path("wiki"),
    *,
    registry_root: str | Path | None = None,
) -> dict[str, Any]:
    """Build a deterministic-enough release description without writing it."""

    root = Path(root).resolve()
    repo_root = _repo_root(root)
    if not root.exists():
        raise ReleaseError(f"Wiki root does not exist: {root}")
    record_lint = lint_records(root, registry_root=registry_root)
    manifest_lint = lint_manifests(root, registry_root=registry_root)
    health = health_report(root, registry_root=registry_root)
    artifacts = {
        path.relative_to(repo_root).as_posix(): _sha256(path)
        for path in _artifact_paths(root)
    }
    source_manifest = root / "manifest.json"
    triage_path = root / "triage.json"
    source_count = 0
    materialized_item_count = 0
    evidence_file_count = 0
    evidence_chunk_count = 0
    if source_manifest.exists():
        try:
            loaded = json.loads(source_manifest.read_text(encoding="utf-8"))
            if isinstance(loaded, Mapping):
                source_count = len(loaded.get("records", []))
                materialized_item_count = int(loaded.get("item_count", 0) or 0)
        except (OSError, json.JSONDecodeError):
            pass
    if triage_path.exists():
        try:
            loaded = json.loads(triage_path.read_text(encoding="utf-8"))
            if isinstance(loaded, Mapping):
                evidence_file_count = int(loaded.get("evidence_file_count", 0) or 0)
                evidence_chunk_count = int(loaded.get("evidence_chunk_count", 0) or 0)
        except (OSError, json.JSONDecodeError):
            pass
    registry_revisions = {
        str(manifest.get("project_id")): str(manifest.get("registry", {}).get("revision", ""))
        for manifest in load_manifests(root)
        if manifest.get("project_id") and isinstance(manifest.get("registry"), Mapping)
    }
    return {
        "schema_version": RELEASE_SCHEMA_VERSION,
        "scope": "zotero-companion",
        "repository": {
            "root": ".",
            "git": _git_state(repo_root),
        },
        "source_inventory": {
            "source_count": source_count,
            "materialized_item_count": materialized_item_count,
            "evidence_file_count": evidence_file_count,
            "evidence_chunk_count": evidence_chunk_count,
            "typed_record_count": len(load_records(root)),
            "relation_count": record_lint.get("relation_count", 0),
        },
        "registry_revisions": registry_revisions,
        "artifacts": artifacts,
        "record_lint": record_lint,
        "manifest_lint": manifest_lint,
        "dependency_health": {
            "ok": health.get("ok", False),
            "attention_queue_total": health.get("attention_queue_total", 0),
            "orphaned_total": health.get("orphaned_total", 0),
            "contradiction_count": len(health.get("contradictions", [])),
        },
        "reproducibility": {
            "zotero_mutation": False,
            "pdf_conversion": False,
            "secret_material_included": False,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }


def release_plan(
    root: Path = Path("wiki"),
    *,
    registry_root: str | Path | None = None,
    apply: bool = False,
) -> dict[str, Any]:
    """Plan or write the release manifest; writing is explicit and local-only."""

    root = Path(root)
    payload = build_release_manifest(root, registry_root=registry_root)
    if not apply:
        return {
            "mode": "dry-run",
            "would_write": (root / RELEASE_FILENAME).name,
            "release": payload,
            "read_only": True,
        }
    if (
        not payload["record_lint"]["ok"]
        or not payload["manifest_lint"]["ok"]
        or not payload["dependency_health"]["ok"]
    ):
        raise ReleaseError(
            "Cannot write a release manifest while record, project-manifest, or dependency health checks fail"
        )
    output = root / RELEASE_FILENAME
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "mode": "apply",
        "path": output.name,
        "release": payload,
        "written": True,
        "read_only": False,
        "zotero_mutation": False,
    }


__all__ = [
    "RELEASE_FILENAME",
    "RELEASE_SCHEMA_VERSION",
    "ReleaseError",
    "build_release_manifest",
    "release_plan",
]
