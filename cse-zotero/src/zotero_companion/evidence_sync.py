"""Materialize existing Zotero Markdown companions into the agent wiki.

This module deliberately handles only ``.md`` and ``.mmd`` child attachments.
It resolves their local file paths through Zotero's read-only API, copies the
bytes into repository evidence bundles, and records the Zotero attachment key
and hash.  It never reads or copies PDFs, invokes Mathpix, or writes to
Zotero.  The default is a dry run; ``apply=True`` writes repository files only.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.parse
import urllib.request
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .local_api import LocalAPIError, ZoteroLocalAPI
from .wiki import EVIDENCE_DIRNAME, SOURCE_DIRNAME, index_wiki


class EvidenceSyncError(RuntimeError):
    """Raised when the repository evidence plan cannot be interpreted safely."""


_COMPANION_FORMATS = {
    ".md": "markdown",
    ".mmd": "mathpix-markdown",
}


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _write_atomic(path: Path, content: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    if isinstance(content, str):
        temporary.write_text(content, encoding="utf-8")
    else:
        temporary.write_bytes(content)
    os.replace(temporary, path)


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _display_path(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve().parent))
    except ValueError:
        return str(path)


def _root_relative_path(root: Path, path: Path) -> str:
    return str(path.resolve().relative_to(root.resolve()))


def _load_source_records(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    source_root = root / SOURCE_DIRNAME
    for path in sorted(source_root.glob("*/record.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise EvidenceSyncError(f"Could not read source record {path}: {exc}") from exc
        if not isinstance(value, Mapping):
            raise EvidenceSyncError(f"Source record is not a JSON object: {path}")
        records.append(dict(value))
    return records


def _local_attachment_path(api: Any, attachment_key: str) -> Path:
    """Resolve one attachment through Zotero's local file URL endpoint."""

    path = f"/api/users/0/items/{urllib.parse.quote(attachment_key, safe='')}/file/view/url"
    raw_url = api.get_text(path) if hasattr(api, "get_text") else api.get(path)
    if not isinstance(raw_url, str):
        raise LocalAPIError("Zotero did not return a local attachment file URL")
    parsed = urllib.parse.urlparse(raw_url)
    if parsed.scheme != "file" or parsed.netloc not in ("", "localhost"):
        # Do not echo a URL that could contain local or user-specific details.
        raise LocalAPIError("Zotero attachment did not resolve to a local file URL")
    candidate = Path(
        urllib.request.url2pathname(urllib.parse.unquote(parsed.path))
    ).resolve()
    if not candidate.is_file():
        raise LocalAPIError("Zotero attachment file is unavailable")
    return candidate


def _safe_filename(filename: str, attachment_key: str, suffix: str) -> str:
    name = Path(filename).name.strip()
    if not name or name in {".", ".."}:
        name = f"attachment-{attachment_key}{suffix}"
    if Path(name).suffix.casefold() not in _COMPANION_FORMATS:
        name = f"{name}{suffix}"
    return name


def _role(filename: str) -> str:
    lowered = filename.casefold()
    if any(term in lowered for term in ("support", "supplement", "appendix")):
        return "supporting_information"
    return "main_article"


def _relative_manifest_path(bundle: Path, relative_path: str) -> Path | None:
    candidate = Path(relative_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    resolved = (bundle / candidate).resolve()
    if resolved != bundle.resolve() and bundle.resolve() not in resolved.parents:
        return None
    return resolved


def _read_manifest(bundle: Path) -> tuple[dict[str, Any] | None, str | None]:
    path = bundle / "manifest.json"
    if not path.exists():
        return None, None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, "existing evidence manifest is unreadable"
    if not isinstance(value, Mapping) or not isinstance(value.get("files", []), Sequence):
        return None, "existing evidence manifest has an invalid files list"
    return dict(value), None


def _base_manifest(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "parent_zotero_key": str(record.get("zotero_key", "")),
        "citation_key": str(record.get("citation_key", "")),
        "doi": str(record.get("doi", "")),
        "conversion": {
            "mode": "existing-zotero-companions",
            "converter": "none",
            "pdf_conversion": "forbidden-when-companion-exists",
        },
        "files": [],
    }


def _readme(record: Mapping[str, Any], manifest: Mapping[str, Any]) -> str:
    title = str(record.get("title") or "Untitled source").strip()
    key = str(record.get("zotero_key", ""))
    citation = str(record.get("citation_key") or "not-set")
    doi = str(record.get("doi") or "not-set")
    lines = [
        f"# {title} evidence bundle",
        "",
        "This bundle contains exact Markdown companions already present in Zotero.",
        "No PDF was copied or converted; no Mathpix conversion was run.",
        "",
        f"- Zotero parent: `{key}`",
        f"- Citation key: `{citation}`",
        f"- DOI: {doi}",
        "- Conversion: `none` (existing Zotero companion)",
        "",
        "## Files",
        "",
    ]
    for entry in manifest.get("files", []):
        if not isinstance(entry, Mapping):
            continue
        lines.append(
            f"- `{entry.get('path', '')}` — Zotero attachment "
            f"`{entry.get('zotero_attachment_key', '')}`; "
            f"SHA-256 `{entry.get('sha256', '')}`"
        )
    lines.extend(
        [
            "",
            "The companions are source evidence. Interpretations, claims, and",
            "implementation conclusions belong in the curated wiki layer.",
            "",
        ]
    )
    return "\n".join(lines)


def _candidate(
    root: Path,
    record: Mapping[str, Any],
    attachment: Mapping[str, Any],
    api: Any,
) -> dict[str, Any]:
    parent_key = str(record.get("zotero_key", ""))
    attachment_key = str(attachment.get("key", ""))
    filename = str(attachment.get("filename", ""))
    suffix = Path(filename).suffix.casefold()
    candidate: dict[str, Any] = {
        "zotero_key": parent_key,
        "title": str(record.get("title", "")),
        "citation_key": str(record.get("citation_key", "")),
        "doi": str(record.get("doi", "")),
        "zotero_attachment_key": attachment_key,
        "source_filename": filename,
        "format": _COMPANION_FORMATS[suffix],
        "role": _role(filename),
        "available": False,
        "source_sha256": None,
        "destination": None,
        "action": "unavailable",
        "reason": "",
    }
    try:
        source_path = _local_attachment_path(api, attachment_key)
        content = source_path.read_bytes()
    except (LocalAPIError, OSError, ValueError) as exc:
        candidate["reason"] = "local companion file is unavailable"
        candidate["error_type"] = type(exc).__name__
        return candidate
    candidate["available"] = True
    candidate["source_sha256"] = _sha256(content)
    candidate["_source_path"] = source_path
    return candidate


def _plan_candidate(root: Path, candidate: dict[str, Any], record: Mapping[str, Any]) -> None:
    if not candidate["available"]:
        return
    parent_key = str(candidate["zotero_key"])
    bundle = root / EVIDENCE_DIRNAME / parent_key
    manifest, manifest_error = _read_manifest(bundle)
    if manifest_error:
        candidate["action"] = "conflict"
        candidate["reason"] = manifest_error
        return
    manifest = manifest or _base_manifest(record)
    entries = [entry for entry in manifest.get("files", []) if isinstance(entry, Mapping)]
    attachment_key = str(candidate["zotero_attachment_key"])
    matching = next(
        (dict(entry) for entry in entries if str(entry.get("zotero_attachment_key", "")) == attachment_key),
        None,
    )
    if matching is not None:
        relative = str(matching.get("path", ""))
        destination = _relative_manifest_path(bundle, relative)
        if destination is None:
            candidate["action"] = "conflict"
            candidate["reason"] = "existing evidence path escapes its bundle"
            return
        candidate["destination"] = _root_relative_path(root, destination)
        candidate["manifest_path"] = relative
        declared = str(matching.get("sha256", ""))
        if declared and declared != candidate["source_sha256"]:
            candidate["action"] = "conflict"
            candidate["reason"] = "existing manifest hash differs from Zotero companion"
            return
        if destination.is_file():
            try:
                existing_hash = _sha256(destination.read_bytes())
            except OSError:
                existing_hash = ""
            if existing_hash != candidate["source_sha256"]:
                candidate["action"] = "conflict"
                candidate["reason"] = "existing evidence file differs from Zotero companion"
                return
            candidate["action"] = "unchanged"
            candidate["reason"] = "companion already materialized with matching hash"
            return
        candidate["action"] = "copy"
        candidate["reason"] = "manifest exists but companion file is missing"
        return

    filename = _safe_filename(
        str(candidate["source_filename"]),
        attachment_key,
        Path(str(candidate["source_filename"])).suffix.casefold(),
    )
    destination = (bundle / filename).resolve()
    candidate["destination"] = _root_relative_path(root, destination)
    candidate["manifest_path"] = filename
    if any(str(entry.get("path", "")) == filename for entry in entries):
        candidate["action"] = "conflict"
        candidate["reason"] = "destination filename is already used by another attachment"
        return
    if destination.exists():
        candidate["action"] = "conflict"
        candidate["reason"] = "destination file exists outside the evidence manifest"
        return
    candidate["action"] = "copy"
    candidate["reason"] = "existing Zotero companion is ready to materialize"


def _updated_manifest(
    record: Mapping[str, Any],
    bundle: Path,
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    manifest, manifest_error = _read_manifest(bundle)
    if manifest_error:
        raise EvidenceSyncError(str(manifest_error))
    updated = manifest or _base_manifest(record)
    files = [dict(entry) for entry in updated.get("files", []) if isinstance(entry, Mapping)]
    new_entry = {
        "role": candidate["role"],
        "zotero_attachment_key": candidate["zotero_attachment_key"],
        "source_filename": candidate["source_filename"],
        "path": str(candidate["manifest_path"]),
        "format": candidate["format"],
        "sha256": candidate["source_sha256"],
    }
    replaced = False
    for index, entry in enumerate(files):
        if str(entry.get("zotero_attachment_key", "")) == str(candidate["zotero_attachment_key"]):
            files[index] = new_entry
            replaced = True
            break
    if not replaced:
        files.append(new_entry)
    updated["files"] = sorted(files, key=lambda entry: str(entry.get("path", "")))
    return updated


def sync_evidence(
    root: Path = Path("wiki"),
    *,
    api: Any | None = None,
    keys: Sequence[str] | None = None,
    records: Sequence[Mapping[str, Any]] | None = None,
    apply: bool = False,
) -> dict[str, Any]:
    """Plan or materialize all existing Markdown companions in Zotero.

    ``records`` lets a caller pass a just-read snapshot so attachment lists are
    resolved from the live library rather than from an older source file.
    """

    root = Path(root)
    api = api or ZoteroLocalAPI()
    records = (
        [dict(record) for record in records]
        if records is not None
        else _load_source_records(root)
    )
    requested = {str(key) for key in (keys or []) if str(key)}
    record_by_key = {str(record.get("zotero_key", "")): record for record in records}
    selected = [
        record
        for record in records
        if not requested or str(record.get("zotero_key", "")) in requested
    ]
    candidates: list[dict[str, Any]] = []
    for record in selected:
        attachments = record.get("attachments", [])
        if not isinstance(attachments, Sequence) or isinstance(attachments, (str, bytes)):
            continue
        for attachment in attachments:
            if not isinstance(attachment, Mapping):
                continue
            suffix = Path(str(attachment.get("filename", ""))).suffix.casefold()
            if suffix not in _COMPANION_FORMATS:
                continue
            candidate = _candidate(root, record, attachment, api)
            _plan_candidate(root, candidate, record)
            candidate.pop("_source_path", None)
            candidates.append(candidate)

    action_counts = Counter(str(candidate["action"]) for candidate in candidates)
    unknown_keys = sorted(requested - set(record_by_key))
    result: dict[str, Any] = {
        "mode": "apply" if apply else "dry-run",
        "wiki_root": str(root),
        "source_count": len(selected),
        "candidate_count": len(candidates),
        "available_count": sum(1 for candidate in candidates if candidate["available"]),
        "actions": dict(sorted(action_counts.items())),
        "unknown_keys": unknown_keys,
        "repository_only": True,
        "zotero_mutation": False,
        "pdf_conversion": False,
        "candidates": candidates,
    }
    if not apply:
        return result

    applied: list[str] = []
    for candidate in candidates:
        if candidate["action"] != "copy":
            continue
        record = record_by_key[str(candidate["zotero_key"])]
        source_path = _local_attachment_path(api, str(candidate["zotero_attachment_key"]))
        content = source_path.read_bytes()
        if _sha256(content) != candidate["source_sha256"]:
            raise EvidenceSyncError(
                f"Companion changed during sync for {candidate['zotero_attachment_key']}; rerun the dry run"
            )
        destination = root / str(candidate["destination"])
        bundle = root / EVIDENCE_DIRNAME / str(candidate["zotero_key"])
        _write_atomic(destination, content)
        manifest = _updated_manifest(record, bundle, candidate)
        _write_atomic(bundle / "manifest.json", _stable_json(manifest))
        readme = bundle / "README.md"
        if not readme.exists():
            _write_atomic(readme, _readme(record, manifest))
        applied.append(str(candidate["zotero_attachment_key"]))

    result["applied_attachment_keys"] = applied
    result["applied_count"] = len(applied)
    if applied:
        result["index"] = index_wiki(root)
    return result


__all__ = ["EvidenceSyncError", "sync_evidence"]
