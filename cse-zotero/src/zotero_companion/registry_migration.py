"""Preserve and index the thermophysical registry as a CSE Zotero domain pack."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any


class RegistryMigrationError(ValueError):
    """Raised when a registry migration cannot be performed safely."""


ID_FIELDS = {
    "species.json": "species_id",
    "mixture.json": "mixture_id",
    "dataset.json": "dataset_id",
    "observation.json": "observation_id",
    "reaction-constant.json": "reaction_constant_id",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _files(root: Path):
    try:
        output = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            check=True,
            capture_output=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RegistryMigrationError("Registry source must be a Git checkout") from exc
    paths = [root / item.decode() for item in output.split(b"\0") if item]
    if not paths or any(not path.is_file() for path in paths):
        raise RegistryMigrationError("Registry checkout has missing or no tracked files")
    yield from paths


def _canonical_records(root: Path):
    for path in sorted((root / "data").rglob("*.json")):
        if path.name in ID_FIELDS and "raw" not in path.parts and "staging" not in path.parts:
            yield path


def _row_count(path: Path) -> int | None:
    if path.suffix.casefold() != ".csv":
        return None
    try:
        with path.open(newline="", encoding="utf-8-sig") as stream:
            return sum(1 for _ in csv.reader(stream)) - 1
    except (OSError, UnicodeDecodeError):
        return None


def _csv_count(path: Path) -> int:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return sum(1 for _ in csv.DictReader(stream))


def build_registry_pack(registry_root: Path, companion_root: Path, *, apply: bool) -> dict[str, Any]:
    """Plan or create a source-preserving thermophysical domain pack."""

    registry_root = Path(registry_root).resolve()
    companion_root = Path(companion_root).resolve()
    if not (registry_root / "data").is_dir() or not (registry_root / "docs/migration").is_dir():
        raise RegistryMigrationError(f"Not a thermophysical registry checkout: {registry_root}")
    destination = companion_root / "data/domains/thermophysical"
    if apply and destination.exists():
        raise RegistryMigrationError(f"Destination already exists: {destination}")

    source_files = list(_files(registry_root))
    canonical = list(_canonical_records(registry_root))
    ready = registry_root / "docs/migration/source-ready-candidates.csv"
    blocked = registry_root / "docs/migration/source-blocked-candidates.csv"
    summary = {
        "source_repository": registry_root.name,
        "destination": destination.relative_to(companion_root).as_posix(),
        "source_files": len(source_files),
        "canonical_records": len(canonical),
        "source_ready": _csv_count(ready),
        "quarantined": _csv_count(blocked),
        "apply": apply,
    }
    if not apply:
        return summary

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".thermophysical.next.", dir=destination.parent))
    try:
        source_root = temporary / "source/registry"
        for source in source_files:
            target = source_root / source.relative_to(registry_root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

        normalized = temporary / "normalized"
        quarantine = temporary / "quarantine"
        normalized.mkdir(parents=True)
        quarantine.mkdir(parents=True)

        with (normalized / "source-files.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=("source_path", "bytes", "rows", "sha256"),
                lineterminator="\n",
            )
            writer.writeheader()
            for path in source_files:
                writer.writerow(
                    {
                        "source_path": path.relative_to(registry_root).as_posix(),
                        "bytes": path.stat().st_size,
                        "rows": _row_count(path),
                        "sha256": _sha256(path),
                    }
                )

        with (normalized / "registry-records.csv").open("w", newline="", encoding="utf-8") as stream:
            fields = (
                "record_type",
                "record_id",
                "title",
                "quality_state",
                "source_path",
                "sha256",
                "source",
            )
            writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            for path in canonical:
                record = json.loads(path.read_text(encoding="utf-8"))
                writer.writerow(
                    {
                        "record_type": record.get("record_type", path.stem),
                        "record_id": record.get(ID_FIELDS[path.name], ""),
                        "title": record.get("title") or record.get("preferred_name") or record.get("display_name", ""),
                        "quality_state": record.get("quality_state", "identity"),
                        "source_path": path.relative_to(registry_root).as_posix(),
                        "sha256": _sha256(path),
                        "source": json.dumps(record.get("source", {}), sort_keys=True),
                    }
                )

        shutil.copy2(ready, normalized / ready.name)
        shutil.copy2(blocked, quarantine / blocked.name)
        summary["source_tree_sha256"] = hashlib.sha256(
            "".join(f"{_sha256(path)}  {path.relative_to(registry_root).as_posix()}\n" for path in source_files).encode()
        ).hexdigest()
        (temporary / "migration-report.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        temporary.rename(destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return summary
