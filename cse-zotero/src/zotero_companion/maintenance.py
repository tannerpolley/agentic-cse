"""One-shot, repository-only maintenance for the materialized Zotero wiki."""

from __future__ import annotations

import fcntl
from collections.abc import Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .evidence_sync import sync_evidence
from .local_api import LocalAPIError, ZoteroLocalAPI
from .wiki import (
    MANIFEST_FILENAME,
    WikiSnapshot,
    build_source_records,
    index_wiki,
    materialize_snapshot,
    verify_wiki,
)

MAINTENANCE_LOCK_FILENAME = ".zotero-companion-maintenance.lock"


def _lock_path(root: Path) -> Path:
    root = Path(root).expanduser().resolve()
    return root.parent / f".{root.name}{MAINTENANCE_LOCK_FILENAME}"


@contextmanager
def _overlap_lock(root: Path) -> Iterator[bool]:
    """Hold a nonblocking lock for manual calls that can overlap."""

    root = Path(root).expanduser().resolve()
    lock_path = _lock_path(root)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


def _run_locked(
    root: Path, *, api: Any, apply: bool, projects: Mapping[str, str] | None
) -> dict[str, Any]:
    snapshot = WikiSnapshot.from_api(api, projects)
    records = build_source_records(snapshot)
    refresh = materialize_snapshot(
        snapshot,
        root,
        apply=apply,
        records=records,
        rebuild_index=False,
    )
    evidence = sync_evidence(root, api=api, records=records, apply=apply)
    issues = [
        {
            "action": str(candidate.get("action", "")),
            "zotero_key": str(candidate.get("zotero_key", "")),
            "zotero_attachment_key": str(candidate.get("zotero_attachment_key", "")),
            "source_filename": str(candidate.get("source_filename", "")),
            "destination": str(candidate.get("destination", "")),
            "reason": str(candidate.get("reason", "")),
        }
        for candidate in evidence.get("candidates", [])
        if isinstance(candidate, Mapping)
        and candidate.get("action") in {"conflict", "unavailable"}
    ]

    if apply:
        if not isinstance(evidence.get("index"), Mapping):
            index_wiki(root)
        verification = verify_wiki(root)
    else:
        verification = (
            verify_wiki(root)
            if (root / MANIFEST_FILENAME).exists()
            else {"ok": True, "errors": []}
        )

    errors = [
        (
            f"Evidence {issue['action']} for "
            f"{issue['zotero_attachment_key'] or issue['source_filename']}: {issue['reason']}"
        )
        for issue in issues
    ]
    errors.extend(str(error) for error in verification.get("errors", []))
    return {
        "ok": not errors,
        "status": "error" if errors else "ok",
        "mode": "apply" if apply else "dry-run",
        "refresh": {
            "items": refresh.get("items_considered", 0),
            "sources": refresh.get("sources", 0),
            "changed": refresh.get("changed", 0),
            "unchanged": refresh.get("unchanged", 0),
            "orphaned": len(refresh.get("orphaned_records", [])),
        },
        "evidence": {
            "candidate_count": evidence.get("candidate_count", 0),
            "available_count": evidence.get("available_count", 0),
            "actions": evidence.get("actions", {}),
            "applied_count": evidence.get("applied_count", 0),
            "issues": issues,
        },
        "verify": {"ok": bool(verification.get("ok", False))},
        "errors": errors,
    }


def maintain_wiki(
    root: Path = Path("wiki"),
    *,
    api: Any | None = None,
    apply: bool = False,
    projects: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Refresh sources, sync existing companions, and verify the repository.

    ``projects`` maps registered slugs to collection keys for source membership.
    """

    root = Path(root).expanduser().resolve()
    api = api if api is not None else ZoteroLocalAPI()
    try:
        with _overlap_lock(root) as acquired:
            if not acquired:
                return {
                    "ok": True,
                    "status": "skipped_overlap",
                    "mode": "apply" if apply else "dry-run",
                }
            return _run_locked(root, api=api, apply=apply, projects=projects)
    except LocalAPIError as exc:
        return {
            "ok": False,
            "status": "unavailable",
            "mode": "apply" if apply else "dry-run",
            "reason": "zotero_unavailable",
            "errors": [str(exc)],
        }
    except Exception as exc:  # pragma: no cover - defensive scheduler boundary
        return {
            "ok": False,
            "status": "error",
            "mode": "apply" if apply else "dry-run",
            "errors": [str(exc)],
        }


__all__ = [
    "MAINTENANCE_LOCK_FILENAME",
    "maintain_wiki",
]
