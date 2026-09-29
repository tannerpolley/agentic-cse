"""Build the bootstrapped Zotero add-on XPI."""

from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "zotero-plugin"
DIST = ROOT / "dist"
OUTPUT = DIST / "cse-zotero-1.0.0.xpi"
FILES = ("manifest.json", "bootstrap.js", "cleanup-plan.js", "organize-plan.js", "zotero-companion.js")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    output = parser.parse_args().output
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for name in FILES:
            archive.write(PLUGIN / name, name)
    print(output)


if __name__ == "__main__":
    main()
