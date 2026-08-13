"""Low-friction, read-only templates for new typed knowledge records."""

from __future__ import annotations

import re
import json
from pathlib import Path
from typing import Any

from .records import RECORD_ID_PREFIXES, RECORD_SCHEMA_VERSION, RECORD_TYPES

_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*:[a-z0-9][a-z0-9._-]*$")

_FILL_FIELDS = {
    "paper_brief": ["summary", "provenance.sources[0].locator", "related_records"],
    "claim": ["summary", "provenance.sources[0].locator"],
    "equation": ["expression", "symbols", "assumptions", "validity"],
    "dataset_reference": ["registry_refs", "basis", "conditions", "quality_state"],
    "parameter_reference": ["registry_refs", "model", "dependencies", "validity"],
    "correlation_reference": ["registry_refs", "equation", "validity"],
    "idea": ["summary", "provenance.sources", "related_records"],
    "insight": ["summary", "provenance.sources", "derived_from", "limitations"],
    "workflow": ["inputs", "outputs", "assumptions", "failure_modes"],
    "implementation_reference": ["repository", "path", "version", "behavior"],
    "validation_run": ["inputs", "acceptance", "result", "code_version"],
}


def _placeholder_id(record_type: str) -> str:
    return f"{RECORD_ID_PREFIXES[record_type]}:replace-me"


def _source_reference(zotero_key: str) -> dict[str, Any]:
    if zotero_key:
        return {
            "zotero_key": zotero_key,
            "locator": {"kind": "section-or-page", "value": "TODO: locate exact evidence"},
        }
    return {
        "record_id": "source:replace-with-zotero-key",
        "locator": {"kind": "section-or-page", "value": "TODO: locate exact evidence"},
    }


def record_template(
    record_type: str,
    *,
    record_id: str = "",
    title: str = "",
    zotero_key: str = "",
) -> dict[str, Any]:
    """Return a clearly marked record template without writing repository files."""

    if record_type not in RECORD_TYPES:
        allowed = ", ".join(sorted(RECORD_TYPES))
        raise ValueError(f"record_type must be one of: {allowed}")
    normalized_id = str(record_id).strip() or _placeholder_id(record_type)
    if not _ID_PATTERN.fullmatch(normalized_id):
        raise ValueError("record_id must use a type-prefixed stable ID")
    expected_prefix = RECORD_ID_PREFIXES[record_type]
    if not normalized_id.startswith(f"{expected_prefix}:"):
        raise ValueError(f"record_id must start with {expected_prefix}:")
    normalized_key = str(zotero_key).strip()
    if normalized_key and not re.fullmatch(r"[A-Za-z0-9]+", normalized_key):
        raise ValueError("zotero_key must be a single Zotero key")
    source = _source_reference(normalized_key)
    record: dict[str, Any] = {
        "schema_version": RECORD_SCHEMA_VERSION,
        "record_type": record_type,
        "record_id": normalized_id,
        "title": str(title).strip() or "TODO: replace with a human title",
        "status": "proposed",
        "confidence": "not-assessed",
        "summary": "TODO: replace with a source-backed, bounded summary.",
        "provenance": {
            "derivation_kind": "source-reported",
            "sources": [source],
            "derived_from": [],
            "review": {
                "reviewer": "",
                "reviewed_at": "",
                "notes": "Template only; do not promote until evidence and limits are reviewed.",
            },
        },
    }
    if record_type == "equation":
        record.update(
            {
                "expression": "TODO: transcribe the equation exactly",
                "symbols": [],
                "assumptions": [],
                "validity": {},
            }
        )
    elif record_type in {"dataset_reference", "parameter_reference", "correlation_reference"}:
        record["registry_refs"] = [
            {
                "registry": "thermophysical-data-registry",
                "registry_id": "TODO: stable registry ID",
                "version": "TODO: version or revision",
                "path": "TODO: registry-relative path",
            }
        ]
    elif record_type == "implementation_reference":
        record.update({"repository": "TODO: Engineering repository", "path": "TODO: relative path"})
    elif record_type == "validation_run":
        record.update({"inputs": [], "acceptance": [], "result": "TODO: result", "code_version": "TODO: commit"})
    elif record_type in {"idea", "insight", "workflow"}:
        record["related_records"] = []
    return {
        "record": record,
        "template": {
            "record_type": record_type,
            "fill_before_review": list(_FILL_FIELDS[record_type]),
            "warning": "This is a draft template. It was not written, promoted, or treated as scientific truth.",
        },
        "read_only": True,
        "zotero_mutation": False,
        "pdf_conversion": False,
    }


def paper_brief_template(root: Path, zotero_key: str) -> dict[str, Any]:
    """Return a metadata-only Markdown brief scaffold without writing it."""

    root = Path(root)
    key = str(zotero_key).strip()
    if not re.fullmatch(r"[A-Za-z0-9]+", key):
        raise ValueError("zotero_key must be a single Zotero key")
    source_path = root / "sources" / key / "record.json"
    if not source_path.exists():
        raise ValueError(f"Source record not found: {source_path}")
    try:
        source = json.loads(source_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read source record {source_path}: {exc}") from exc
    if not isinstance(source, dict):
        raise ValueError(f"Source record is not an object: {source_path}")
    title = str(source.get("title") or f"Zotero source {key}").strip()
    citation_key = str(source.get("citation_key") or key).strip()
    doi = str(source.get("doi") or "").strip()
    authors = ", ".join(str(author) for author in source.get("creators", []) if author)
    projects = ", ".join(str(project) for project in source.get("projects", []) if project)
    evidence_bundle = root / "evidence" / key
    evidence_readme = evidence_bundle / "README.md"
    evidence_available = evidence_readme.exists()
    doi_line = f"https://doi.org/{doi}" if doi else ""
    markdown = "\n".join(
        [
            f"# {title}",
            "",
            "- brief_status: scaffold",
            "- Zotero key: " + key,
            "- citation key: " + citation_key,
            "- DOI: " + doi_line,
            "- source record: ../sources/" + key + "/record.json",
            "- evidence bundle: ../evidence/" + key + "/README.md",
            "- domains: TODO: classify",
            "- projects: " + (projects or "TODO: classify"),
            "- research threads: TODO: classify",
            "",
            "## Research question and context",
            "",
            "TODO: state the source's question only after reviewing its evidence.",
            "",
            "## Contribution",
            "",
            "TODO: separate source-reported contribution from wiki interpretation.",
            "",
            "## Model, equations, and assumptions",
            "",
            "TODO: add exact equations, symbols, units, assumptions, and locators.",
            "",
            "## Data and validation",
            "",
            "TODO: record data, conditions, bases, uncertainties, and validation targets.",
            "",
            "## Workflow and methods",
            "",
            "TODO: describe the repeatable source workflow and distinguish proposals.",
            "",
            "## Results and limitations",
            "",
            "TODO: record bounded results, caveats, contradictions, and open questions.",
            "",
            "## Related sources and synthesis",
            "",
            "TODO: link typed relations and explicitly derived cross-paper insights.",
            "",
            "## Registry, implementation, and validation links",
            "",
            "TODO: add only reviewed registry, code, manifest, and validation records.",
            "",
            "## Review record",
            "",
            "- checked_at:",
            "- reviewer:",
            "- unresolved: scaffold; no full-paper audit has been claimed",
            "",
        ]
    )
    return {
        "zotero_key": key,
        "suggested_path": f"wiki/papers/{citation_key}.md",
        "source": {
            "title": title,
            "citation_key": citation_key,
            "doi": doi,
            "authors": authors,
            "year": str(source.get("year", "")),
        },
        "evidence_available": evidence_available,
        "evidence_bundle": str(evidence_bundle),
        "markdown": markdown,
        "read_only": True,
        "zotero_mutation": False,
        "pdf_conversion": False,
    }


__all__ = ["paper_brief_template", "record_template"]
