"""Check durable repository structure and scientific provenance."""

from __future__ import annotations

from pathlib import Path

import bibtexparser
import yaml

ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


manifest = yaml.safe_load((ROOT / ".mplgallery/manifest.yaml").read_text(encoding="utf-8"))
records = manifest.get("records", [])
require(len(records) == 3, "MPLGallery manifest must register the three retained figures")
for record in records:
    for key in ("svg_path", "sidecar_path", "data_path"):
        require((ROOT / record[key]).is_file(), f"missing registered plot resource: {record[key]}")
    pdf = ROOT / Path(record["svg_path"]).with_suffix(".pdf")
    png = ROOT / Path(record["svg_path"]).with_suffix(".png")
    require(
        pdf.is_file() and png.is_file(),
        f"retained figure formats are incomplete: {record['plot_id']}",
    )

bibliography_text = (
    ROOT / "docs/scientific/latex/references.bib"
).read_text(encoding="utf-8")
bibliography = bibtexparser.loads(bibliography_text)
require(
    len(bibliography.entries) == 1,
    "project bibliography must contain exactly one cited record",
)
entry = bibliography.entries[0]
require(entry["ID"] == "crankPracticalMethodNumerical1947", "unexpected bibliography record")
require(entry.get("doi") == "10.1017/S0305004100023197", "Crank DOI is missing or incorrect")
require(
    "file" not in entry and str(Path.home()) not in bibliography_text,
    "bibliography contains a local path",
)

cases = yaml.safe_load((ROOT / "evaluation/cases.yaml").read_text(encoding="utf-8"))
entrypoints = {case["entrypoint"] for case in cases["direct_entry_cases"]}
expected_entrypoints = {
    f"cse:{name}"
    for name in (
        "setup",
        "research",
        "construct",
        "build",
        "analyze",
        "summarize",
        "write",
        "review",
        "zotero",
        "mathpix",
    )
}
require(entrypoints == expected_entrypoints, "evaluation suite must cover all ten public skills")

prose_paths = [
    ROOT / "AGENTS.md",
    ROOT / "README.md",
    ROOT / "analyses/README.md",
    ROOT / "analyses/heat_verification/inputs/case.json",
    ROOT / "analyses/heat_verification/notebook.qmd",
    ROOT / "docs/scientific/CONTEXT.md",
    ROOT / "docs/scientific/writing/STYLE.md",
    ROOT / "docs/scientific/writing/RULES.md",
]
prose = "\n".join(path.read_text(encoding="utf-8") for path in prose_paths)
for forbidden in ("datalad", "git-annex", "Documents/Papers/references.bib", "\N{EM DASH}"):
    require(
        forbidden.casefold() not in prose.casefold(),
        f"obsolete or forbidden prose remains: {forbidden}",
    )

ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
for stale in ("docs/" + "latex", "analysis" + ".yaml"):
    require(stale not in ignore and stale not in prose, f"stale migrated path remains: {stale}")

print("Repository scientific structure and provenance checks passed.")
