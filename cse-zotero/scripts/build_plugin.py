"""Build the bootstrapped Zotero-Wiki plugin XPI."""

from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugin"
DIST = ROOT / "dist"
OUTPUT = DIST / "zotero-wiki-0.1.0.xpi"
FILES = ("manifest.json", "bootstrap.js", "cleanup-plan.js", "zotero-wiki.js")


def main() -> None:
    DIST.mkdir(exist_ok=True)
    with ZipFile(OUTPUT, "w", ZIP_DEFLATED) as archive:
        for name in FILES:
            archive.write(PLUGIN / name, name)
    print(OUTPUT)


if __name__ == "__main__":
    main()
