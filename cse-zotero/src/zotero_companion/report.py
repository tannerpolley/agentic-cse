"""Pure inventory/report functions for CSE Zotero dry runs."""

from __future__ import annotations

import csv
from collections import Counter
from collections.abc import Iterable
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sqlite3
import subprocess
from typing import Any

from .config import CAPABILITIES, CompanionConfig, PROTOCOL_VERSION, config_payload
from .wiki import _collect_evidence_chunks, verify_wiki


_DATA_SUFFIXES = {".csv", ".json", ".jsonl", ".parquet", ".tsv"}
_INVENTORY_NAMES = {
    "catalog.json",
    "inventory.csv",
    "inventory.json",
    "inventory.tsv",
    "inventory.yaml",
    "inventory.yml",
    "manifest.json",
    "registry-records.csv",
    "source-files.csv",
}


def summarize_items(items: Iterable[dict[str, Any]]) -> dict[str, Any]:
    items = list(items)
    attachments = [item for item in items if item.get("data", {}).get("itemType") == "attachment"]
    conversions = [
        item
        for item in attachments
        if Path(item.get("data", {}).get("filename", "")).suffix.lower() in {".md", ".mmd"}
    ]
    tag_counts: Counter[str] = Counter()
    automatic_tag_assignments = 0
    manual_tag_assignments = 0
    for item in items:
        for tag in item.get("data", {}).get("tags", []):
            name = tag.get("tag")
            if not name:
                continue
            tag_counts[name] += 1
            if tag.get("type") == 1:
                automatic_tag_assignments += 1
            else:
                manual_tag_assignments += 1
    return {
        "items": len(items),
        "attachments": len(attachments),
        "markdown_attachments": len(conversions),
        "markdown_extensions": dict(
            Counter(Path(item["data"]["filename"]).suffix.lower() for item in conversions)
        ),
        "distinct_tags": len(tag_counts),
        "tag_assignments": sum(tag_counts.values()),
        "automatic_tag_assignments": automatic_tag_assignments,
        "manual_tag_assignments": manual_tag_assignments,
    }


def audit_payload(api: Any) -> dict[str, Any]:
    """Build a JSON-serializable read-only audit payload from an API client."""
    items = api.items()
    return {
        "top_level_items": len(api.items(top_level=True)),
        "collections": len(api.collections()),
        "tags_endpoint_count": len(api.tags()),
        "saved_searches": len(api.searches()),
        **summarize_items(items),
    }


def _status(
    reason: str,
    *,
    configured: bool,
    readable: bool | None,
    ready: bool,
    live_available: bool | None = None,
    supported: bool = True,
    **details: Any,
) -> dict[str, Any]:
    return {
        "supported": supported,
        "configured": configured,
        "readable": readable,
        "live_available": live_available,
        "ready": ready,
        "reason": reason,
        **details,
    }


def _source_commit() -> dict[str, Any]:
    try:
        revision = subprocess.run(
            ["git", "-C", str(Path(__file__).resolve().parents[2]), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        revision = ""
    return {
        "value": revision or None,
        "available": bool(revision),
        "reason": "read from the package checkout"
        if revision
        else "unavailable from the installed package",
    }


def _identity() -> dict[str, Any]:
    try:
        version = importlib.metadata.version("cse-zotero")
    except importlib.metadata.PackageNotFoundError:
        version = "unknown"
    payload = {
        "package": "cse-zotero",
        "version": version,
        "protocol_version": PROTOCOL_VERSION,
        "capabilities": list(CAPABILITIES),
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "package": {"name": payload["package"], "version": version},
        "source_commit": _source_commit(),
        "payload": {**payload, "sha256": digest},
    }


def _configured_paths(config_path: Path, config: CompanionConfig | None) -> dict[str, str]:
    paths = {"config": str(config_path.expanduser().resolve())}
    if config is not None:
        paths.update(
            {
                "corpus_root": str(config.corpus_root),
                "wiki_root": str(config.wiki_root),
                "data_root": str(config.data_root),
                "zotero_data_dir": str(config.zotero_data_dir),
                "bibliography_export": str(config.bibliography_export),
            }
        )
    return paths


def _offline_corpus(config: CompanionConfig | None) -> dict[str, Any]:
    if config is None:
        return _status(
            "configuration is not valid, so no retained corpus path is configured",
            configured=False,
            readable=False,
            ready=False,
        )
    root = config.wiki_root
    index = root / "index.sqlite"
    details = {"wiki_root": str(root), "index": str(index)}
    if not root.is_dir():
        return _status(f"retained wiki root is missing: {root}", configured=True, readable=False, ready=False, **details)
    if not index.is_file():
        return _status(f"retained corpus search index is missing: {index}", configured=True, readable=True, ready=False, **details)
    try:
        connection = sqlite3.connect(f"file:{index.resolve().as_posix()}?mode=ro", uri=True)
        try:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
            if not integrity or integrity[0] != "ok":
                return _status(f"SQLite index integrity check failed: {integrity}", configured=True, readable=False, ready=False, **details)
            if not connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='documents'"
            ).fetchone():
                return _status("SQLite index has no documents table", configured=True, readable=False, ready=False, **details)
        finally:
            connection.close()
    except (OSError, sqlite3.Error) as exc:
        return _status(f"SQLite index is unreadable: {exc}", configured=True, readable=False, ready=False, **details)

    errors: list[str] = []
    warnings: list[str] = []
    try:
        verification = verify_wiki(root)
        errors.extend(str(error) for error in verification.get("errors", []))
        warnings.extend(str(warning) for warning in verification.get("warnings", []))
    except Exception as exc:  # pragma: no cover - user-owned corpus boundary
        errors.append(f"offline wiki verification failed: {exc}")
    try:
        _, evidence_files, evidence_warnings = _collect_evidence_chunks(root)
        details["evidence_files"] = len(evidence_files)
        errors.extend(str(warning) for warning in evidence_warnings)
    except Exception as exc:  # pragma: no cover - user-owned corpus boundary
        errors.append(f"offline evidence verification failed: {exc}")
    details["warnings"] = warnings
    details["errors"] = errors
    if errors:
        return _status(
            f"retained corpus failed offline verification: {errors[0]}",
            configured=True,
            readable=False,
            ready=False,
            **details,
        )
    return _status(
        "retained wiki root and SQLite index are present and readable offline",
        configured=True,
        readable=True,
        ready=True,
        **details,
    )


def _project_views(config: CompanionConfig | None) -> dict[str, Any]:
    if config is None:
        return _status(
            "configuration is not valid, so project views are not configured",
            configured=False,
            readable=False,
            ready=False,
            projects=[],
        )
    root = config.wiki_root / "projects"
    if not root.exists():
        return _status("project view list is available and empty", configured=True, readable=True, ready=True, projects=[], path=str(root))
    if not root.is_dir():
        return _status(f"project view path is not a directory: {root}", configured=True, readable=False, ready=False, projects=[], path=str(root))
    try:
        projects = []
        for path in sorted(root.iterdir()):
            if path.is_file() and path.name.casefold() != "readme.md":
                path.read_text(encoding="utf-8")
                projects.append(path.stem)
    except (OSError, UnicodeDecodeError) as exc:
        return _status(f"project views are not readable: {exc}", configured=True, readable=False, ready=False, projects=[], path=str(root))
    return _status(
        f"project view list is readable ({len(projects)} view{'' if len(projects) == 1 else 's'})",
        configured=True,
        readable=True,
        ready=True,
        projects=projects,
        path=str(root),
    )


def _hash_inventory_path(root: Path, inventory: Path, relative: str, expected: str) -> str | None:
    if not relative or not expected:
        return None
    bases = [root, inventory.parent]
    if inventory.name in {"registry-records.csv", "source-files.csv"}:
        bases.append(inventory.parent.parent / "source" / "registry")
    candidates = []
    for base in bases:
        candidate = (base / relative).resolve()
        if candidate == root or root in candidate.parents:
            candidates.append(candidate)
    candidate = next((path for path in candidates if path.is_file()), candidates[0] if candidates else None)
    if candidate is None:
        return f"inventory path escapes data root: {relative}"
    if not candidate.is_file():
        return f"inventory file is missing: {relative}"
    if hashlib.sha256(candidate.read_bytes()).hexdigest() != expected:
        return f"data hash mismatch for {relative}"
    return None


def _inventory_errors(path: Path, root: Path) -> list[str]:
    if path.suffix.casefold() not in {".json", ".csv", ".tsv"}:
        return [] if path.stat().st_size else [f"data file is empty: {path}"]
    try:
        if path.suffix.casefold() == ".json":
            value = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(value, list):
                entries = value
            elif isinstance(value, dict):
                entries = []
                for key in ("files", "resources", "datasets", "records"):
                    if isinstance(value.get(key), list):
                        entries.extend(value[key])
            else:
                entries = []
            rows = [entry for entry in entries if isinstance(entry, dict)]
        else:
            with path.open(newline="", encoding="utf-8") as stream:
                reader = csv.DictReader(stream, delimiter="\t" if path.suffix.casefold() == ".tsv" else ",")
                if not reader.fieldnames:
                    return [f"data inventory has no header: {path}"]
                rows = list(reader)
    except (OSError, UnicodeError, csv.Error, json.JSONDecodeError) as exc:
        return [f"data inventory is unreadable ({path}): {exc}"]
    errors = []
    for row in rows:
        relative = str(row.get("path") or row.get("source_path") or row.get("relative_path") or "").strip()
        expected = str(row.get("sha256") or row.get("checksum") or "").strip()
        if error := _hash_inventory_path(root, path, relative, expected):
            errors.append(error)
    return errors


def _inventory_paths(root: Path) -> list[Path]:
    paths = {path for name in _INVENTORY_NAMES for path in root.rglob(name) if path.is_file()}
    return sorted(paths or [path for path in root.iterdir() if path.is_file() and path.suffix.casefold() in _DATA_SUFFIXES])


def _data_readiness(config: CompanionConfig | None) -> dict[str, Any]:
    if config is None:
        return _status("configuration is not valid, so no data root is configured", configured=False, readable=False, ready=False, inventories=[])
    root = config.data_root
    if not root.is_dir():
        return _status(f"configured data root is missing: {root}", configured=True, readable=False, ready=False, inventories=[], data_root=str(root))
    try:
        inventories = _inventory_paths(root)
        errors = [error for path in inventories for error in _inventory_errors(path, root)]
    except OSError as exc:
        return _status(f"configured data root is not readable: {exc}", configured=True, readable=False, ready=False, inventories=[], data_root=str(root))
    details = {"data_root": str(root), "inventories": [str(path) for path in inventories], "errors": errors}
    if not inventories:
        return _status(f"data root is present but no inventory or retained data file was found: {root}", configured=True, readable=True, ready=False, **details)
    if errors:
        return _status(f"data inventory is damaged: {errors[0]}", configured=True, readable=False, ready=False, **details)
    return _status(f"data root and inventory are readable ({len(inventories)} file{'' if len(inventories) == 1 else 's'})", configured=True, readable=True, ready=True, **details)


def _bibliography_readiness(config: CompanionConfig | None) -> dict[str, Any]:
    if config is None:
        return _status("configuration is not valid, so no bibliography export is configured", configured=False, readable=False, ready=False)
    path = config.bibliography_export
    if not path.is_file():
        return _status(f"bibliography export is missing: {path}", configured=True, readable=False, ready=False, path=str(path))
    try:
        empty = not path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError) as exc:
        return _status(f"bibliography export is not readable: {exc}", configured=True, readable=False, ready=False, path=str(path))
    return _status(f"bibliography export is {'empty' if empty else 'present and readable'}: {path}", configured=True, readable=True, ready=not empty, path=str(path))


def _live_status(result: dict[str, Any], name: str, capability: str) -> dict[str, Any]:
    available = bool(result.get("ok"))
    return _status(
        f"{name} responded to a read-only probe" if available else f"{name} is unavailable: {result.get('error') or 'read-only probe failed'}",
        configured=True,
        readable=available,
        live_available=available,
        ready=available,
        capability=capability,
        supported=capability in CAPABILITIES,
    )


def doctor_payload(
    config_path: Path,
    *,
    config: CompanionConfig | None,
    configuration_error: str = "",
    zotero: dict[str, Any],
    better_bibtex: dict[str, Any],
    mathpix: dict[str, Any],
) -> dict[str, Any]:
    """Build the read-only doctor payload without contacting external services."""
    config_file = Path(config_path)
    config_ready = config is not None and config_file.is_file() and not configuration_error
    configuration = _status(
        "configuration is present and valid"
        if config_ready
        else configuration_error or f"configuration file is missing: {config_file}",
        configured=config_file.is_file(),
        readable=config_ready,
        ready=config_ready,
        path=str(config_file),
    )
    zotero_status = _live_status(zotero, "Zotero local API", "zotero-local-api-v1")
    better_bibtex_status = _live_status(better_bibtex, "Better BibTeX", "better-bibtex-library-export-v1")
    consent = None if config is None else config.mathpix_library_consent
    mpx_on_path = bool(mathpix.get("mpx_on_path"))
    mathpix_status = _status(
        "Mathpix capability is supported but configuration and consent are unverified"
        if config is None
        else "Mathpix capability is not configured: mpx is not on PATH"
        if not mpx_on_path
        else "Mathpix capability is configured but explicit library consent is not granted"
        if consent is not True
        else "Mathpix capability is configured and explicit library consent is granted",
        configured=mpx_on_path,
        readable=config is not None,
        ready=bool(mpx_on_path and consent is True),
        capability="mathpix-on-demand-v1",
        mpx_on_path=mpx_on_path,
        consent={"recorded": config is not None, "granted": consent},
    )
    readiness = {
        "configuration": configuration,
        "zotero_local_api": zotero_status,
        "better_bibtex": better_bibtex_status,
        "retained_corpus": _offline_corpus(config),
        "project_views": _project_views(config),
        "data": _data_readiness(config),
        "bibliography_export": _bibliography_readiness(config),
        "mathpix": mathpix_status,
    }
    payload = config_payload(config, config_file, mode="read-only") if config is not None else {
        "ok": False,
        "mode": "read-only",
        "protocol_version": PROTOCOL_VERSION,
        "config_path": str(config_file),
    }
    payload.update(
        {
            "protocol_version": PROTOCOL_VERSION,
            "capabilities": list(CAPABILITIES),
            "zotero": zotero,
            "better_bibtex": better_bibtex,
            "mathpix": {**mathpix, "consent": mathpix_status["consent"]},
            "configuration_exists": config_file.is_file(),
            "configuration_valid": config_ready,
            "configuration_error": configuration_error,
            "configured_paths": _configured_paths(config_file, config),
            "observed_live_checks": {
                "zotero_local_api": {
                    "checked": True,
                    "available": zotero_status["live_available"],
                    "probe": "GET /api/users/0/items?limit=1",
                    "reason": zotero_status["reason"],
                },
                "better_bibtex": {
                    "checked": True,
                    "available": better_bibtex_status["live_available"],
                    "probe": "POST api.ready",
                    "reason": better_bibtex_status["reason"],
                },
            },
            "unverified_active_host": {
                "state": "unverified",
                "reason": "A local response does not prove the active profile or service matches the retained corpus.",
                "zotero_profile": "not inspected",
                "corpus_freshness": "not compared with the live library",
            },
            "identity": _identity(),
            "readiness": readiness,
        }
    )
    # Keep the historical aggregate contract; operation readiness is separate.
    payload["ok"] = bool(zotero.get("ok") and better_bibtex.get("ok") and config_ready)
    return payload


__all__ = ["audit_payload", "doctor_payload", "summarize_items"]
