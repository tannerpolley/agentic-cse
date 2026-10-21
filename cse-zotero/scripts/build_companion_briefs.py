#!/usr/bin/env python3
"""Build conservative paper briefs from existing Zotero companions.

This is deliberately a repository-only curation tool.  It reads the generated
triage metadata and the Markdown/Mathpix companions already copied by
``wiki-evidence-sync``.  It never reads or converts PDFs, never calls Zotero,
and never overwrites an existing paper brief or typed record.

The generated pages are orientation maps, not substitutes for source review.
The source text remains authoritative for equations, data, units, limitations,
and any later registry or implementation promotion.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
WIKI = ROOT / "wiki"
TRIAGE_PATH = WIKI / "triage.json"
PAPERS_DIR = WIKI / "papers"
RECORDS_DIR = WIKI / "records" / "papers"
INDEX_PATH = PAPERS_DIR / "index.md"
CURATION_DATE = "2026-08-06"


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _clean_text(value: str) -> str:
    """Make extracted Markdown/LaTeX readable without interpreting it."""

    value = re.sub(r"<!--.*?-->", " ", value, flags=re.DOTALL)
    value = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", value)
    value = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", value)
    value = re.sub(
        r"\\(?:text|textrm|mathrm|mathbf|mathit|operatorname|mbox)\s*\{([^{}]*)\}",
        r"\1",
        value,
    )
    value = re.sub(r"\\(?:cite|citep|citet|ref|eqref|label)\s*\{[^{}]*\}", " ", value)
    value = re.sub(r"\\(?:begin|end)\s*\{[^{}]*\}", " ", value)
    value = re.sub(r"\\[A-Za-z]+\*?(?:\s*\[[^\]]*\])?\s*", " ", value)
    value = value.replace("$$", " ").replace("$", " ")
    value = value.replace("{", " ").replace("}", " ")
    value = value.replace("`", "")
    value = re.sub(r"\s+", " ", value)
    return value.strip(" -:;\t")


def _sentences(value: str, limit: int = 3, max_chars: int = 1100) -> str:
    value = _clean_text(value)
    if not value:
        return ""
    pieces = [piece.strip() for piece in re.split(r"(?<=[.!?])\s+", value) if piece.strip()]
    selected: list[str] = []
    for piece in pieces[:limit]:
        candidate = " ".join(selected + [piece])
        if len(candidate) > max_chars and selected:
            break
        selected.append(piece)
    result = " ".join(selected) or value[:max_chars].rstrip()
    if len(result) > max_chars:
        result = result[: max_chars - 1].rstrip() + "…"
    return result


def _headings(lines: list[str]) -> list[tuple[int, str, int]]:
    found: list[tuple[int, str]] = []
    for number, line in enumerate(lines, start=1):
        match = re.match(r"^\s*#{1,6}\s+(.+?)\s*$", line)
        if match:
            found.append((number, _clean_text(match.group(1))))
            continue
        match = re.match(r"^\s*\\(?:section|subsection|subsubsection)\*?\s*\{(.+?)\}", line)
        if match:
            found.append((number, _clean_text(match.group(1))))
    return [
        (number, title, found[index + 1][0] - 1 if index + 1 < len(found) else len(lines))
        for index, (number, title) in enumerate(found)
        if title
    ]


def _block_from_heading(lines: list[str], heading: tuple[int, str, int]) -> tuple[str, str]:
    start, title, end = heading
    raw = "\n".join(lines[start:end])
    cleaned = _sentences(raw)
    return cleaned, f"{title}, lines {start + 1}-{end}"


def _abstract(lines: list[str]) -> tuple[str, str]:
    for heading in _headings(lines):
        if heading[1].casefold().startswith(("abstract", "summary")):
            text, locator = _block_from_heading(lines, heading)
            if text:
                return text, locator

    joined = "\n".join(lines)
    match = re.search(r"\\begin\s*\{abstract\}(.*?)\\end\s*\{abstract\}", joined, flags=re.I | re.S)
    if match:
        text = _sentences(match.group(1))
        start = joined[: match.start(1)].count("\n") + 1
        end = joined[: match.end(1)].count("\n") + 1
        if text:
            return text, f"LaTeX abstract, lines {start}-{end}"

    return _first_paragraph(lines)


def _section_excerpt(lines: list[str], terms: tuple[str, ...]) -> tuple[str, str]:
    headings = _headings(lines)
    # Prefer an explicit conclusion/limitations section.  A long
    # ``Results and Discussion`` section often begins with a methods or
    # parameter subsection, which is useful evidence but a poor result label.
    priority_groups = (
        tuple(term for term in terms if term in {"conclusion", "summary", "limitation", "outlook"}),
        tuple(term for term in terms if term in {"results", "discussion"}),
    )
    for group in priority_groups:
        for heading in headings:
            title = heading[1].casefold()
            if not any(term in title for term in group):
                continue
            text, locator = _block_from_heading(lines, heading)
            if text:
                return text, locator
    return "", ""


def _first_paragraph(lines: list[str]) -> tuple[str, str]:
    joined = "\n".join(lines)
    paragraphs = re.split(r"\n\s*\n", joined)
    offset = 1
    for paragraph in paragraphs:
        raw = paragraph.strip()
        if (
            not raw
            or raw.startswith(("#", "\\title", "\\author", "\\section", "Keywords:"))
            or "<br>" in raw
        ):
            offset += paragraph.count("\n") + 2
            continue
        cleaned = _sentences(paragraph)
        if len(cleaned) >= 80 and not cleaned.startswith("|"):
            end = offset + paragraph.count("\n")
            return cleaned, f"available body text, lines {offset}-{end}"
        offset += paragraph.count("\n") + 2
    return "", ""


def _section_names(lines: list[str], terms: tuple[str, ...] = ()) -> list[str]:
    names: list[str] = []
    for _, title, _ in _headings(lines):
        if not terms or any(term in title.casefold() for term in terms):
            if title not in names:
                names.append(title)
    return names[:10]


def _slug(value: str, fallback: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._")
    return value[:100] or fallback


def _doi_url(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        return ""
    return value if value.startswith("http") else f"https://doi.org/{value.removeprefix('doi:').strip()}"


def _companion_files(key: str, fallback_keys: list[str]) -> list[dict[str, Any]]:
    directory = WIKI / "evidence" / key
    readme = directory / "README.md"
    mapping: dict[str, str] = {}
    if readme.exists():
        for line in readme.read_text(encoding="utf-8").splitlines():
            match = re.search(r"- `([^`]+)`.*?attachment `([^`]+)`", line)
            if match:
                mapping[match.group(1)] = match.group(2)

    files = sorted(
        path for path in directory.iterdir() if path.suffix.casefold() in {".md", ".mmd"} and path.name != "README.md"
    ) if directory.exists() else []
    companions: list[dict[str, Any]] = []
    for index, path in enumerate(files):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="replace")
        attachment_key = mapping.get(path.name)
        if not attachment_key and index < len(fallback_keys):
            attachment_key = fallback_keys[index]
        companions.append({"path": path, "text": text, "attachment_key": attachment_key or ""})
    return companions


def _main_companion(companions: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not companions:
        return None
    secondary_words = ("support", "supplement", "appendix", "data", "graphical")
    primary = [
        companion
        for companion in companions
        if not any(word in companion["path"].name.casefold() for word in secondary_words)
    ]
    return max(primary or companions, key=lambda companion: len(companion["text"]))


def _source_metadata(entry: dict[str, Any]) -> dict[str, Any]:
    key = str(entry["zotero_key"])
    path = WIKI / "sources" / key / "record.json"
    return _json(path) if path.exists() else {}


def _metadata_list(values: Any, fallback: str = "unassigned") -> list[str]:
    if isinstance(values, list):
        cleaned = [str(value).strip() for value in values if str(value).strip()]
        if cleaned:
            return cleaned
    return [fallback]


def _brief_name(entry: dict[str, Any]) -> str:
    return _slug(str(entry.get("citation_key") or ""), str(entry["zotero_key"]))


def _brief_paths(entry: dict[str, Any], refresh_existing: bool = False) -> tuple[Path, Path]:
    stem = _brief_name(entry)
    page = PAPERS_DIR / f"{stem}.md"
    record = RECORDS_DIR / f"{stem.casefold()}.json"
    if refresh_existing and page.exists():
        if "curation_level: companion-backed batch brief" not in page.read_text(encoding="utf-8"):
            raise SystemExit(f"refusing to refresh non-batch brief: {page.relative_to(ROOT)}")
        return page, record
    if page.exists() or record.exists():
        suffix = str(entry["zotero_key"]).casefold()
        page = PAPERS_DIR / f"{stem}-{suffix}.md"
        record = RECORDS_DIR / f"{stem.casefold()}-{suffix}.json"
    return page, record


def _evidence_lines(companion: dict[str, Any], locator: str) -> str:
    path = companion["path"].relative_to(WIKI).as_posix()
    return f"`wiki/{path}` ({locator})"


def _render_brief(entry: dict[str, Any], source: dict[str, Any], companions: list[dict[str, Any]]) -> str:
    key = str(entry["zotero_key"])
    title = str(entry.get("title") or source.get("title") or key)
    citation_key = str(entry.get("citation_key") or source.get("citation_key") or key)
    doi = _doi_url(source.get("doi") or entry.get("doi"))
    projects = _metadata_list(entry.get("projects"), "unassigned (provisional)")
    domains = _metadata_list(entry.get("suggested_domains"), "not assigned (provisional)")
    threads = _metadata_list(entry.get("suggested_research_threads"), "not assigned (provisional)")
    main = _main_companion(companions)
    lines = main["text"].splitlines() if main else []
    lead, lead_locator = _abstract(lines) if lines else ("", "")
    if not lead and lines:
        lead, lead_locator = _first_paragraph(lines)
    conclusion, conclusion_locator = _section_excerpt(
        lines, ("conclusion", "results", "discussion", "summary", "limitation", "outlook")
    ) if lines else ("", "")
    model_sections = _section_names(
        lines, ("model", "equation", "thermodynamic", "theory", "parameter", "equilibrium", "born", "saft")
    ) if lines else []
    data_sections = _section_names(
        lines, ("data", "experiment", "validation", "measurement", "result", "property", "table", "figure")
    ) if lines else []
    method_sections = _section_names(
        lines, ("method", "workflow", "calculation", "simulation", "regression", "optimization", "procedure")
    ) if lines else []
    evidence_chars = sum(len(str(companion["text"])) for companion in companions)
    low_confidence = evidence_chars < 5000 or "corrigendum" in title.casefold() or not lead
    confidence = "low" if low_confidence else "medium"
    evidence_list = [
        f"- `{companion['path'].relative_to(WIKI).as_posix()}` — attachment `{companion['attachment_key'] or 'not recorded'}`"
        for companion in companions
    ]

    if lead:
        research = (
            f"The available Zotero companion describes the source as follows: {lead}\n\n"
            f"Evidence locator: {_evidence_lines(main, lead_locator)}."
        )
        contribution = (
            "This batch brief preserves the source-reported orientation from the companion. "
            "It does not promote a new project interpretation or implementation conclusion."
        )
    else:
        research = (
            "The available companion contains too little continuous article text for a substantive "
            "research-question summary. This page is an evidence map pending deliberate review."
        )
        contribution = "No substantive contribution claim is made because the available companion text is limited."

    if model_sections:
        model = (
            "Available companion headings relevant to models or equations: "
            + ", ".join(f"{name}" for name in model_sections)
            + ". Exact equations, symbols, units, assumptions, and validity limits remain in the companion. "
            "No typed equation or parameter record was promoted by this batch."
        )
    else:
        model = (
            "No model/equation heading was confidently extracted from the available companion. "
            "Do not infer model scope from the title or metadata alone; use `wiki-evidence " + key + "`."
        )

    if data_sections:
        data = (
            "Available companion headings relevant to data or validation: "
            + ", ".join(data_sections)
            + ". Exact observations, composition bases, conditions, uncertainties, tables, and figures "
            "remain source evidence; no thermophysical-data-registry dataset was asserted."
        )
    else:
        data = (
            "No data/validation heading was confidently extracted. This batch does not assert an observed "
            "dataset, uncertainty basis, or registry mapping."
        )

    workflow = (
        "Available methods/workflow headings: " + ", ".join(method_sections) + "."
        if method_sections
        else "No repeatable workflow was promoted by this batch; inspect the exact companion before reuse."
    )
    if conclusion:
        results = (
            f"Available result/limitation text: {conclusion}\n\n"
            f"Evidence locator: {_evidence_lines(main, conclusion_locator)}."
        )
    else:
        results = "No conclusion or limitation excerpt was confidently extracted from the available companion."
    limits = (
        "This is a companion-backed batch brief, not a full-paper audit. The source PDF was not converted or "
        "read by this workflow. Do not treat metadata suggestions, section names, or this summary as validated "
        "model/data/implementation truth."
    )
    if low_confidence:
        limits += " The available companion is short or evidence-limited; deliberate follow-up review is required."

    doi_line = f"- DOI: [{doi.removeprefix('https://doi.org/')}](<{doi}>)" if doi else "- DOI: not recorded in the generated source record"
    return "\n".join(
        [
            f"# {title}",
            "",
            "- brief_status: briefed",
            "- curation_level: companion-backed batch brief",
            f"- confidence: {confidence}",
            f"- Zotero key: `{key}`",
            f"- citation key: `{citation_key}`",
            doi_line,
            f"- source record: [`wiki/sources/{key}/record.json`](../sources/{key}/record.json)",
            f"- evidence bundle: [`wiki/evidence/{key}/README.md`](../evidence/{key}/README.md)",
            f"- domains (provisional metadata): {', '.join(domains)}",
            f"- projects: {', '.join(projects)}",
            f"- research threads (provisional metadata): {', '.join(threads)}",
            "",
            "## Research question and context",
            "",
            research,
            "",
            "## Contribution",
            "",
            contribution,
            "",
            "## Model, equations, and assumptions",
            "",
            model,
            "",
            "## Data and validation",
            "",
            data,
            "",
            "## Workflow and methods",
            "",
            workflow,
            "",
            "## Results and limitations",
            "",
            results,
            "",
            limits,
            "",
            "## Related sources and synthesis",
            "",
            "The domains, projects, and research threads above are provisional navigation signals from the "
            "generated triage layer. No cross-paper support, contradiction, supersession, or derived insight was "
            "promoted automatically; add those only with exact evidence and a typed relation.",
            "",
            "## Registry, implementation, and validation links",
            "",
            "No registry dataset, parameter set, implementation reference, or validation run was promoted by this "
            "batch. Those links require exact compatibility and provenance review.",
            "",
            "## Review record",
            "",
            f"- checked_at: {CURATION_DATE}",
            "- reviewer: Codex companion-backed batch curation",
            "- curation method: deterministic extraction of existing Zotero Markdown/Mathpix companions plus generated source metadata",
            "- evidence reviewed:",
            *evidence_list,
            "- unresolved: exact equations, data bases, units, uncertainty, validity limits, cross-paper relations, registry mapping, and implementation compatibility",
            "- boundary: the companion files are authoritative evidence; this brief is an orientation layer and does not replace them",
            "",
        ]
    )


def _render_record(
    entry: dict[str, Any],
    source: dict[str, Any],
    companions: list[dict[str, Any]],
    page_path: Path,
) -> dict[str, Any]:
    key = str(entry["zotero_key"])
    title = str(entry.get("title") or source.get("title") or key)
    lead = ""
    if companions:
        lines = _main_companion(companions)["text"].splitlines()
        lead, _ = _abstract(lines)
        lead = lead or _first_paragraph(lines)[0]
    confidence = "low" if sum(len(str(item["text"])) for item in companions) < 5000 or "corrigendum" in title.casefold() or not lead else "medium"
    provenance_sources = []
    for companion in companions:
        evidence_path = f"wiki/evidence/{key}/{companion['path'].name}"
        provenance_sources.append(
            {
                "zotero_key": key,
                "attachment_key": companion["attachment_key"],
                "evidence_path": evidence_path,
                "locator": {"kind": "companion", "value": "existing Markdown/Mathpix companion; see the paper brief for extracted section locators"},
            }
        )
    stem = page_path.stem.casefold()
    summary = lead or "Companion-backed orientation map; no substantive summary was promoted from the available evidence."
    return {
        "schema_version": 1,
        "record_type": "paper_brief",
        "record_id": f"paper:{stem}",
        "title": title,
        "status": "evidence-ready",
        "confidence": confidence,
        "summary": summary,
        "provenance": {
            "derivation_kind": "source-reported",
            "sources": provenance_sources,
            "derived_from": [],
            "review": {
                "reviewer": "Codex companion-backed batch curation",
                "reviewed_at": CURATION_DATE,
                "notes": "Existing Zotero Markdown/Mathpix companions were used directly; no PDF was converted, no Zotero data was mutated, and no registry or implementation claim was promoted.",
            },
        },
        "related_records": [],
    }


def _parse_page_metadata(path: Path) -> tuple[str, str, list[str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    title = next((line[2:].strip() for line in lines if line.startswith("# ")), path.stem)
    key = ""
    projects: list[str] = []
    for line in lines[:25]:
        if line.startswith("- Zotero key:"):
            key = line.split("`", 2)[1] if "`" in line else line.split(":", 1)[1].strip()
        if line.startswith("- projects:") or line.startswith("- project:"):
            projects = [part.strip().strip("`") for part in line.split(":", 1)[1].split(",") if part.strip().strip("`")]
    return title, key, projects or ["unassigned"]


def _render_collection_index() -> str:
    groups: dict[str, list[tuple[str, str, str]]] = {}
    for path in sorted(PAPERS_DIR.glob("*.md")):
        if path.name in {"README.md", "index.md"}:
            continue
        title, key, projects = _parse_page_metadata(path)
        for project in projects:
            groups.setdefault(project, []).append((title, key, path.name))
    output = [
        "# Paper brief collection",
        "",
        f"Updated: {CURATION_DATE}",
        "",
        "This navigation page is generated from the paper briefs. Each brief is a concise orientation layer; the linked Zotero evidence companion remains authoritative for exact equations, data, units, and limitations.",
        "",
    ]
    for project in sorted(groups, key=str.casefold):
        output.extend([f"## {project}", ""])
        seen: set[tuple[str, str]] = set()
        for title, key, filename in sorted(groups[project], key=lambda item: item[0].casefold()):
            identity = (filename, key)
            if identity in seen:
                continue
            seen.add(identity)
            safe_title = title.replace("]", "\\]")
            output.append(f"- [{safe_title}]({filename}) — `{key or 'key unavailable'}`")
        output.append("")
    return "\n".join(output)


def _candidates(refresh_existing: bool = False) -> list[dict[str, Any]]:
    triage = _json(TRIAGE_PATH)
    entries = triage.get("entries", [])
    return [
        entry
        for entry in entries
        if (
            (
                entry.get("status") == "evidence-ready"
                and not entry.get("brief_path")
            )
            or (
                refresh_existing
                and entry.get("brief_status") == "briefed"
                and (PAPERS_DIR / f"{_brief_name(entry)}.md").exists()
                and "curation_level: companion-backed batch brief"
                in (PAPERS_DIR / f"{_brief_name(entry)}.md").read_text(encoding="utf-8")
            )
        )
        and int(entry.get("evidence", {}).get("searchable_file_count", 0)) > 0
    ]


def _build_payload(entry: dict[str, Any], refresh_existing: bool = False) -> tuple[Path, Path, str, dict[str, Any]]:
    key = str(entry["zotero_key"])
    companions = _companion_files(key, list(entry.get("evidence", {}).get("attachment_keys", [])))
    source = _source_metadata(entry)
    page_path, record_path = _brief_paths(entry, refresh_existing=refresh_existing)
    brief = _render_brief(entry, source, companions)
    record = _render_record(entry, source, companions, page_path)
    return page_path, record_path, brief, record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write only missing briefs and records")
    parser.add_argument("--limit", type=int, default=0, help="limit candidates for a staged run (default: all)")
    parser.add_argument("--rebuild-index", action="store_true", help="rebuild wiki/papers/index.md from existing briefs")
    parser.add_argument(
        "--refresh-existing",
        action="store_true",
        help="explicitly refresh only pages marked as companion-backed batch briefs",
    )
    args = parser.parse_args()

    if args.rebuild_index:
        result = {
            "mode": "apply" if args.apply else "dry-run",
            "index_path": str(INDEX_PATH.relative_to(ROOT)),
            "paper_page_count": sum(
                1 for path in PAPERS_DIR.glob("*.md") if path.name not in {"README.md", "index.md"}
            ),
        }
        if args.apply:
            INDEX_PATH.write_text(_render_collection_index(), encoding="utf-8")
            result["rebuilt"] = True
        else:
            result["rebuilt"] = False
        print(json.dumps(result, indent=2))
        return 0

    candidates = _candidates(refresh_existing=args.refresh_existing)
    if args.limit:
        candidates = candidates[: args.limit]
    payloads = [_build_payload(entry, refresh_existing=args.refresh_existing) for entry in candidates]
    existing = [
        str(path.relative_to(ROOT))
        for page_path, record_path, _, _ in payloads
        for path in (page_path, record_path)
        if path.exists()
    ]
    missing_companions = [
        str(entry["zotero_key"])
        for entry in candidates
        if not _companion_files(str(entry["zotero_key"]), list(entry.get("evidence", {}).get("attachment_keys", [])))
    ]
    if missing_companions:
        raise SystemExit(f"evidence-ready entries have no local companion files: {', '.join(missing_companions)}")
    if existing and not args.refresh_existing:
        raise SystemExit("refusing to overwrite existing generated targets: " + ", ".join(existing))

    result = {
        "mode": "apply" if args.apply else "dry-run",
        "candidate_count": len(candidates),
        "brief_count": len(payloads),
        "record_count": len(payloads),
        "refresh_existing": args.refresh_existing,
        "pdf_conversion": False,
        "zotero_mutation": False,
        "index_path": str(INDEX_PATH.relative_to(ROOT)),
        "sample": [
            {"zotero_key": str(entry["zotero_key"]), "citation_key": entry.get("citation_key", ""), "page": str(page.relative_to(ROOT))}
            for entry, (page, _, _, _) in list(zip(candidates, payloads))[:5]
        ],
    }
    if not args.apply:
        print(json.dumps(result, indent=2))
        return 0

    PAPERS_DIR.mkdir(parents=True, exist_ok=True)
    RECORDS_DIR.mkdir(parents=True, exist_ok=True)
    for page_path, record_path, brief, record in payloads:
        page_path.write_text(brief, encoding="utf-8")
        record_path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    INDEX_PATH.write_text(_render_collection_index(), encoding="utf-8")
    result["created_pages"] = len(payloads)
    result["created_records"] = len(payloads)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
