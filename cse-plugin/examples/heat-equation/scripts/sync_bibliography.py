"""Generate the project bibliography from cited Zotero-owned BBT records."""

from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
from pathlib import Path

import bibtexparser
from bibtexparser.bwriter import BibTexWriter

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path.home() / "Zotero/exports/references.bib"
TARGET = ROOT / "docs/latex/references.bib"
KEYS_FILE = ROOT / "docs/latex/cited_keys.txt"


def cited_keys() -> list[str]:
    keys = [line.strip() for line in KEYS_FILE.read_text(encoding="utf-8").splitlines()]
    return [key for key in keys if key and not key.startswith("#")]


def generated_bytes() -> bytes:
    if not SOURCE.is_file() or SOURCE.is_symlink() or SOURCE.stat().st_size == 0:
        raise SystemExit(f"canonical Better BibTeX export is unavailable: {SOURCE}")
    database = bibtexparser.loads(SOURCE.read_text(encoding="utf-8"))
    entries = {entry["ID"]: entry for entry in database.entries}
    wanted = cited_keys()
    missing = [key for key in wanted if key not in entries]
    if missing:
        raise SystemExit(f"cited keys missing from canonical export: {', '.join(missing)}")

    selected = []
    for key in wanted:
        entry = dict(entries[key])
        entry.pop("file", None)
        selected.append(entry)
    database.entries = selected

    writer = BibTexWriter()
    writer.order_entries_by = None
    writer.indent = "  "
    body = bibtexparser.dumps(database, writer=writer)
    if "file =" in body.casefold() or str(Path.home()) in body:
        raise SystemExit("generated bibliography contains a local attachment path")
    return body.encode("utf-8")


def target_is_dirty() -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "--", str(TARGET.relative_to(ROOT))],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = generated_bytes()
    current = TARGET.read_bytes() if TARGET.is_file() and not TARGET.is_symlink() else None

    if args.check:
        if current != expected:
            raise SystemExit(f"project bibliography is stale: {TARGET}")
        print(
            f"Project bibliography is current "
            f"({len(expected)} bytes, {len(cited_keys())} record)."
        )
        return

    if current == expected:
        print(
            f"Project bibliography is current "
            f"({len(expected)} bytes, {len(cited_keys())} record)."
        )
        return
    if target_is_dirty():
        raise SystemExit(f"refusing to replace bibliography with Git changes: {TARGET}")

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".references.bib.", dir=TARGET.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(expected)
        temporary.chmod(0o644)
        temporary.replace(TARGET)
    finally:
        temporary.unlink(missing_ok=True)
    if TARGET.read_bytes() != expected:
        raise SystemExit("bibliography synchronization verification failed")
    print(f"Generated project bibliography ({len(expected)} bytes, {len(cited_keys())} record).")


if __name__ == "__main__":
    main()
