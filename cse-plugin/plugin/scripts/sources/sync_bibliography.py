#!/usr/bin/env python3
"""Synchronize a Better BibTeX export into a repository."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import tempfile


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    source = args.source.expanduser().resolve()
    destination = args.destination.expanduser().resolve()
    if not source.is_file():
        parser.error(f"Better BibTeX export does not exist: {source}")
    if source.suffix.casefold() != ".bib" or destination.suffix.casefold() != ".bib":
        parser.error("source and destination must be .bib files")
    if source == destination:
        parser.error("source and destination must differ")

    content = source.read_bytes()
    current = destination.read_bytes() if destination.is_file() else None
    if current == content:
        print(f"Bibliography is current: {destination}")
        return 0
    if args.check:
        print(f"Bibliography differs: {destination}")
        return 1

    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".references-", dir=destination.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    print(f"Synchronized bibliography: {source} -> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
