"""Verified migration of the user corpus out of the installable package checkout."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Iterator

from .config import CompanionConfig


class CorpusMigrationError(RuntimeError):
    """Raised when a corpus migration would lose or overwrite information."""


def _files(root: Path) -> Iterator[Path]:
    if not root.is_dir():
        return
    yield from sorted(path for path in root.rglob("*") if path.is_file() and not path.is_symlink())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _entries(source_root: Path, config: CompanionConfig) -> list[tuple[Path, Path, str]]:
    mappings = (
        (source_root / "wiki", config.wiki_root, "wiki"),
        (source_root / "data" / "domains", config.data_root / "domains", "data/domains"),
    )
    entries: list[tuple[Path, Path, str]] = []
    for source, destination, prefix in mappings:
        if not source.is_dir():
            raise CorpusMigrationError(f"Corpus source directory is missing: {source}")
        for path in _files(source):
            relative = path.relative_to(source)
            entries.append((path, destination / relative, f"{prefix}/{relative.as_posix()}"))
    return entries


def migrate_corpus(
    source_root: Path,
    config: CompanionConfig,
    *,
    apply: bool = False,
) -> dict[str, object]:
    """Plan or copy corpus files, refusing to overwrite different destination content."""
    source_root = Path(source_root).expanduser().resolve()
    entries = _entries(source_root, config)
    conflicts: list[str] = []
    unchanged = 0
    pending = 0
    source_bytes = 0
    for source, destination, relative in entries:
        source_bytes += source.stat().st_size
        if destination.exists():
            if not destination.is_file() or _sha256(source) != _sha256(destination):
                conflicts.append(relative)
            else:
                unchanged += 1
        else:
            pending += 1
    if conflicts:
        examples = ", ".join(conflicts[:5])
        raise CorpusMigrationError(
            f"Refusing corpus migration because {len(conflicts)} destination files differ: {examples}"
        )
    copied = 0
    if apply:
        for source, destination, _relative in entries:
            if destination.exists():
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            if _sha256(source) != _sha256(destination):
                raise CorpusMigrationError(f"Copied file failed verification: {destination}")
            copied += 1
    verified = unchanged + copied
    return {
        "ok": True,
        "mode": "apply" if apply else "dry-run",
        "source_root": str(source_root),
        "corpus_root": str(config.corpus_root),
        "source_files": len(entries),
        "source_bytes": source_bytes,
        "pending_files": 0 if apply else pending,
        "copied_files": copied,
        "verified_files": verified,
        "conflicts": [],
        "source_removed": False,
    }
