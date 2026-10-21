"""Materialize Zotero metadata into an agent-readable research wiki.

Zotero remains the bibliographic source of truth.  This module creates a
deterministic, reviewable repository snapshot containing source records,
project context, and a local SQLite search index.  It never writes to Zotero.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .manifests import ManifestError, lint_manifests, manifest_lookup
from .records import _registry_root, lint_records, search_records
from .projects import collection_table, memberships

WIKI_SCHEMA_VERSION = 1
INDEX_SCHEMA_VERSION = 2
INDEX_FILENAME = "index.sqlite"
TRIAGE_FILENAME = "triage.json"
TRIAGE_SCHEMA_VERSION = 2
MANIFEST_FILENAME = "manifest.json"
CATALOG_FILENAME = "catalog.json"
SOURCE_DIRNAME = "sources"
PROJECT_DIRNAME = "projects"
CLAIMS_DIRNAME = "claims"
GRAPH_DIRNAME = "graphs"
EVIDENCE_DIRNAME = "evidence"
CURATION_DIRNAME = "curation"
ASSIGNMENTS_FILENAME = "source-assignments.json"
CLASSIFICATION_SCHEMA_VERSION = 1

ASSIGNMENT_STATES = ("proposed", "accepted", "rejected")
ASSIGNMENT_RELEVANCES = ("candidate", "relevant", "uncertain", "not_relevant")

DEFAULT_CLASSIFICATION_DOMAINS = (
    {
        "id": "epcsaft",
        "label": "ePC-SAFT and SAFT models",
        "description": "SAFT-family equations of state and their parameterizations.",
    },
    {
        "id": "mea-co2-capture",
        "label": "MEA and CO2 capture",
        "description": "Reactive amine systems, absorption, desorption, and capture processes.",
    },
    {
        "id": "lithium-extraction",
        "label": "Lithium extraction",
        "description": "Lithium recovery, brines, solvent extraction, membranes, and selectivity.",
    },
    {
        "id": "electrolyte-thermodynamics",
        "label": "Electrolyte thermodynamics",
        "description": "Ions, salts, activity models, solvation, dielectric effects, and electrolyte data.",
    },
    {
        "id": "phase-equilibria",
        "label": "Phase equilibria",
        "description": "VLE, LLE, flash, phase stability, and coupled chemical-phase equilibrium.",
    },
    {
        "id": "thermophysical-data",
        "label": "Thermophysical data",
        "description": "Measured or correlated properties, data resources, and property definitions.",
    },
    {
        "id": "transport",
        "label": "Transport and kinetics",
        "description": "Mass transfer, viscosity, diffusivity, heat transfer, and kinetic behavior.",
    },
    {
        "id": "numerical-modeling",
        "label": "Numerical and computational methods",
        "description": "Algorithms, optimization, simulation, uncertainty quantification, and solvers.",
    },
    {
        "id": "process-systems",
        "label": "Process systems",
        "description": "Flowsheets, columns, process design, scale-up, and systems integration.",
    },
)

DEFAULT_RESEARCH_THREADS = (
    {
        "id": "parameterization-and-regression",
        "label": "Parameterization and regression",
        "description": "Fitting, parameter estimation, combining rules, and parameter transferability.",
    },
    {
        "id": "electrolyte-solvation",
        "label": "Electrolyte solvation",
        "description": "Born terms, ion interactions, dielectric effects, and electrolyte activity behavior.",
    },
    {
        "id": "phase-and-chemical-equilibrium",
        "label": "Phase and chemical equilibrium",
        "description": "Equilibrium formulations, phase stability, speciation, and multiphase calculations.",
    },
    {
        "id": "reaction-and-speciation",
        "label": "Reaction and speciation",
        "description": "Reaction mechanisms, speciation, absorption chemistry, and reaction constants.",
    },
    {
        "id": "transport-and-kinetics",
        "label": "Transport and kinetics",
        "description": "Mass transfer, diffusivity, viscosity, rate-based models, and kinetic limits.",
    },
    {
        "id": "data-and-uncertainty",
        "label": "Data and uncertainty",
        "description": "Measurements, data quality, uncertainty quantification, and source comparability.",
    },
    {
        "id": "numerical-equilibrium",
        "label": "Numerical equilibrium",
        "description": "Optimization, stability analysis, continuation, solvers, and computational robustness.",
    },
    {
        "id": "process-integration",
        "label": "Process integration",
        "description": "Process design, columns, scale-up, flowsheets, and model-to-process handoffs.",
    },
    {
        "id": "lithium-selectivity-and-mechanisms",
        "label": "Lithium selectivity and mechanisms",
        "description": "Lithium selectivity, co-ion effects, extraction mechanisms, and solvent design.",
    },
    {
        "id": "model-comparison-and-validation",
        "label": "Model comparison and validation",
        "description": "Benchmarks, prediction checks, validation data, and competing model assumptions.",
    },
)

_PROJECT_DOMAIN_SUGGESTIONS = {
    "epcsaft-equilibrium": "epcsaft",
    "mea-thermodynamics": "mea-co2-capture",
    "lithium-extraction": "lithium-extraction",
}

_DOMAIN_SUGGESTION_TERMS = {
    "epcsaft": ("ePC-SAFT", "ePC SAFT", "PC-SAFT", "PC SAFT", "SAFT"),
    "mea-co2-capture": (
        "CO2 capture",
        "carbon capture",
        "carbon dioxide capture",
        "monoethanolamine",
        "methyldiethanolamine",
        "alkanolamine",
        "absorption",
        "desorption",
    ),
    "lithium-extraction": (
        "lithium",
        "brine",
        "solvent extraction",
        "direct lithium extraction",
        "lithium recovery",
    ),
    "electrolyte-thermodynamics": (
        "electrolyte",
        "ionic liquid",
        "ion",
        "salt",
        "born",
        "debye",
        "pitzer",
        "activity coefficient",
        "osmotic coefficient",
        "solvation",
    ),
    "phase-equilibria": (
        "phase equilibrium",
        "phase equilibria",
        "vapor-liquid",
        "vapour-liquid",
        "liquid-liquid",
        "phase behavior",
        "phase behaviour",
        "phase stability",
        "flash calculation",
        "tangent-plane",
    ),
    "thermophysical-data": (
        "thermophysical",
        "thermodynamic properties",
        "physical properties",
        "density",
        "viscosity",
        "heat capacity",
        "vapor pressure",
        "vapour pressure",
        "solubility",
        "database",
        "experimental data",
    ),
    "transport": (
        "transport",
        "mass transfer",
        "diffusivity",
        "diffusion",
        "viscosity",
        "thermal conductivity",
        "heat transfer",
        "rate-based",
        "kinetics",
    ),
    "numerical-modeling": (
        "numerical",
        "algorithm",
        "optimization",
        "solver",
        "simulation",
        "machine learning",
        "uncertainty quantification",
        "ipopt",
        "pyomo",
        "equation-oriented",
    ),
    "process-systems": (
        "process",
        "column",
        "flowsheet",
        "scale-up",
        "scale up",
        "pilot plant",
        "process design",
        "process simulation",
        "aspen plus",
    ),
}

_THREAD_SUGGESTION_TERMS = {
    "parameterization-and-regression": (
        "parameter",
        "parameterization",
        "parameter estimation",
        "regression",
        "fitting",
        "fit",
        "combining rule",
        "born diameter",
    ),
    "electrolyte-solvation": (
        "electrolyte",
        "ion",
        "ionic liquid",
        "born",
        "debye",
        "pitzer",
        "activity coefficient",
        "osmotic coefficient",
        "solvation",
        "dielectric",
    ),
    "phase-and-chemical-equilibrium": (
        "phase equilibrium",
        "phase equilibria",
        "chemical equilibrium",
        "vapor-liquid",
        "vapour-liquid",
        "liquid-liquid",
        "flash calculation",
        "phase stability",
        "speciation",
    ),
    "reaction-and-speciation": (
        "reaction",
        "reactive",
        "speciation",
        "carbamate",
        "absorption",
        "desorption",
        "amine",
        "kinetics",
    ),
    "transport-and-kinetics": (
        "transport",
        "mass transfer",
        "diffusivity",
        "diffusion",
        "viscosity",
        "rate-based",
        "kinetics",
    ),
    "data-and-uncertainty": (
        "data",
        "database",
        "measurement",
        "experimental",
        "uncertainty",
        "validation",
        "benchmark",
    ),
    "numerical-equilibrium": (
        "numerical",
        "algorithm",
        "optimization",
        "solver",
        "continuation",
        "tangent-plane",
        "ipopt",
        "gibbs",
        "stability",
    ),
    "process-integration": (
        "process",
        "column",
        "flowsheet",
        "scale-up",
        "scale up",
        "pilot plant",
        "process design",
        "aspen plus",
    ),
    "lithium-selectivity-and-mechanisms": (
        "lithium",
        "selectivity",
        "extraction mechanism",
        "coexisting ions",
        "brine",
        "lithium recovery",
    ),
    "model-comparison-and-validation": (
        "validation",
        "benchmark",
        "comparison",
        "predicting",
        "prediction",
        "model evaluation",
        "experimental and modeling",
    ),
}

CLAIM_REQUIRED_METADATA = (
    "claim_id",
    "project",
    "status",
    "confidence",
    "claim_type",
    "zotero_key",
    "derived_from",
    "locator",
)

class WikiError(RuntimeError):
    """Raised when a wiki operation cannot safely proceed."""


@dataclass(frozen=True)
class WikiSnapshot:
    """Read-only data collected from Zotero's local API."""

    items: tuple[dict[str, Any], ...]
    collections: tuple[dict[str, Any], ...]
    tags: tuple[dict[str, Any], ...]
    searches: tuple[dict[str, Any], ...]
    # Registered project slug -> Zotero collection key (see projects.py).
    projects: tuple[tuple[str, str], ...] = ()

    @classmethod
    def from_api(cls, api: Any, projects: Mapping[str, str] | None = None) -> WikiSnapshot:
        return cls(
            items=tuple(api.items()),
            collections=tuple(api.collections()),
            tags=tuple(api.tags()),
            searches=tuple(api.searches()),
            projects=tuple(sorted((projects or {}).items())),
        )


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _write_atomic(path: Path, content: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    if isinstance(content, str):
        temporary.write_text(content, encoding="utf-8")
    else:
        temporary.write_bytes(content)
    os.replace(temporary, path)


def _sha256(content: str | bytes) -> str:
    raw = content.encode("utf-8") if isinstance(content, str) else content
    return hashlib.sha256(raw).hexdigest()


def _data(obj: Mapping[str, Any]) -> Mapping[str, Any]:
    value = obj.get("data", obj)
    return value if isinstance(value, Mapping) else {}


def _key(obj: Mapping[str, Any]) -> str:
    data = _data(obj)
    return str(obj.get("key") or data.get("key") or "")


def _creator_name(creator: Mapping[str, Any]) -> str:
    if creator.get("name"):
        return str(creator["name"])
    return " ".join(
        str(part)
        for part in (creator.get("firstName"), creator.get("lastName"))
        if part
    ).strip()


def _normalize_tags(raw_tags: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_tags, Sequence) or isinstance(raw_tags, (str, bytes)):
        return []
    tags = []
    for raw in raw_tags:
        if not isinstance(raw, Mapping) or not raw.get("tag"):
            continue
        try:
            tag_type = int(raw.get("type", 0) or 0)
        except (TypeError, ValueError):
            tag_type = 0
        tags.append({"name": str(raw["tag"]), "type": 1 if tag_type == 1 else 0})
    return sorted(tags, key=lambda tag: (tag["name"].casefold(), tag["type"]))


def _collection_name_map(collections: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    names: dict[str, str] = {}
    for collection in collections:
        key = _key(collection)
        name = _data(collection).get("name")
        if key and name:
            names[key] = str(name)
    return names


def _default_classification_config() -> dict[str, Any]:
    return {
        "schema_version": CLASSIFICATION_SCHEMA_VERSION,
        "description": (
            "Curated, reviewable source classifications. Metadata suggestions in triage "
            "are not assignments until recorded here."
        ),
        "domains": [dict(entry) for entry in DEFAULT_CLASSIFICATION_DOMAINS],
        "research_threads": [dict(entry) for entry in DEFAULT_RESEARCH_THREADS],
        "assignments": {},
    }


def _classification_path(root: Path) -> Path:
    return Path(root) / CURATION_DIRNAME / ASSIGNMENTS_FILENAME


def _string_values(value: Any, *, field: str, path: Path, key: str = "") -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        subject = f" for {key}" if key else ""
        raise WikiError(f"{path}: {field}{subject} must be a list of strings")
    values = []
    for item in value:
        item_value = str(item).strip()
        if item_value and item_value not in values:
            values.append(item_value)
    return sorted(values)


def _classification_vocabulary(
    raw: Any,
    *,
    field: str,
    path: Path,
) -> list[dict[str, str]]:
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise WikiError(f"{path}: {field} must be a list")
    entries: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, value in enumerate(raw):
        if not isinstance(value, Mapping):
            raise WikiError(f"{path}: {field}[{index}] must be an object")
        identifier = str(value.get("id", "")).strip()
        if not identifier:
            raise WikiError(f"{path}: {field}[{index}] is missing id")
        if identifier in seen:
            raise WikiError(f"{path}: duplicate {field} id {identifier}")
        seen.add(identifier)
        entries.append(
            {
                "id": identifier,
                "label": str(value.get("label", identifier)).strip() or identifier,
                "description": str(value.get("description", "")).strip(),
            }
        )
    return entries


def _load_classification_config(root: Path) -> dict[str, Any]:
    """Load and validate the curated source-classification layer."""

    path = _classification_path(Path(root))
    if not path.exists():
        raw = _default_classification_config()
    else:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WikiError(f"Could not read classification file {path}: {exc}") from exc
    if not isinstance(raw, Mapping):
        raise WikiError(f"Classification file is not a JSON object: {path}")
    try:
        schema_version = int(raw.get("schema_version", 0) or 0)
    except (TypeError, ValueError) as exc:
        raise WikiError(f"Invalid classification schema version in {path}") from exc
    if schema_version != CLASSIFICATION_SCHEMA_VERSION:
        raise WikiError(
            f"Unsupported classification schema version {schema_version} in {path}; "
            f"expected {CLASSIFICATION_SCHEMA_VERSION}"
        )
    domains = _classification_vocabulary(raw.get("domains", []), field="domains", path=path)
    research_threads = _classification_vocabulary(
        raw.get("research_threads", []),
        field="research_threads",
        path=path,
    )
    domain_ids = {entry["id"] for entry in domains}
    thread_ids = {entry["id"] for entry in research_threads}
    raw_assignments = raw.get("assignments", {})
    if not isinstance(raw_assignments, Mapping):
        raise WikiError(f"{path}: assignments must be an object keyed by Zotero item key")
    assignments: dict[str, dict[str, Any]] = {}
    for raw_key, raw_assignment in raw_assignments.items():
        key = str(raw_key).strip()
        if not key:
            raise WikiError(f"{path}: assignment key cannot be empty")
        if not isinstance(raw_assignment, Mapping):
            raise WikiError(f"{path}: assignment {key} must be an object")
        state = str(raw_assignment.get("state", "")).strip()
        if state not in ASSIGNMENT_STATES:
            allowed = ", ".join(ASSIGNMENT_STATES)
            raise WikiError(f"{path}: assignment {key} has invalid state; use {allowed}")
        relevance = str(raw_assignment.get("relevance", "")).strip()
        if relevance not in ASSIGNMENT_RELEVANCES:
            allowed = ", ".join(ASSIGNMENT_RELEVANCES)
            raise WikiError(f"{path}: assignment {key} has invalid relevance; use {allowed}")
        reason = str(raw_assignment.get("reason", "")).strip()
        if not reason:
            raise WikiError(f"{path}: assignment {key} requires a non-empty reason")
        assignment_domains = _string_values(
            raw_assignment.get("domains", []),
            field="domains",
            path=path,
            key=key,
        )
        unknown_domains = sorted(set(assignment_domains) - domain_ids)
        if unknown_domains:
            raise WikiError(
                f"{path}: assignment {key} uses unknown domains: {', '.join(unknown_domains)}"
            )
        assignment_threads = _string_values(
            raw_assignment.get("research_threads", []),
            field="research_threads",
            path=path,
            key=key,
        )
        unknown_threads = sorted(set(assignment_threads) - thread_ids)
        if unknown_threads:
            raise WikiError(
                f"{path}: assignment {key} uses unknown research threads: "
                f"{', '.join(unknown_threads)}"
            )
        assignments[key] = {
            "state": state,
            "relevance": relevance,
            "domains": assignment_domains,
            "research_threads": assignment_threads,
            "reason": reason,
            "reviewer": str(raw_assignment.get("reviewer", "")).strip(),
            "reviewed_at": str(raw_assignment.get("reviewed_at", "")).strip(),
        }
    config = {
        "schema_version": CLASSIFICATION_SCHEMA_VERSION,
        "description": str(raw.get("description", "")).strip(),
        "domains": domains,
        "research_threads": research_threads,
        "assignments": assignments,
    }
    return {
        "path": path,
        "config": config,
        "domains": domains,
        "research_threads": research_threads,
        "assignments": assignments,
    }


def _classification_text(record: Mapping[str, Any]) -> str:
    tags = " ".join(
        str(tag.get("name", ""))
        for tag in record.get("tags", [])
        if isinstance(tag, Mapping)
    )
    values = (
        record.get("title", ""),
        record.get("abstract", ""),
        record.get("note", ""),
        tags,
        " ".join(str(value) for value in record.get("collections", [])),
        " ".join(str(value) for value in record.get("projects", [])),
    )
    return " ".join(str(value) for value in values if value).casefold().replace("–", "-").replace("—", "-")


def _contains_any(text: str, terms: Sequence[str]) -> bool:
    return any(term.casefold() in text for term in terms)


def _suggested_classification(record: Mapping[str, Any]) -> dict[str, list[str]]:
    """Suggest, but never silently assign, taxonomy values from metadata."""

    text = _classification_text(record)
    projects = {str(value) for value in record.get("projects", []) if value}
    domains = {
        _PROJECT_DOMAIN_SUGGESTIONS[project]
        for project in projects
        if project in _PROJECT_DOMAIN_SUGGESTIONS
    }
    domains.update(
        identifier
        for identifier, terms in _DOMAIN_SUGGESTION_TERMS.items()
        if _contains_any(text, terms)
    )
    threads = {
        identifier
        for identifier, terms in _THREAD_SUGGESTION_TERMS.items()
        if _contains_any(text, terms)
    }
    if "epcsaft-equilibrium" in projects:
        threads.add("phase-and-chemical-equilibrium")
    if "mea-thermodynamics" in projects:
        threads.add("reaction-and-speciation")
    if "lithium-extraction" in projects:
        threads.add("lithium-selectivity-and-mechanisms")
    return {
        "domains": sorted(domains),
        "research_threads": sorted(threads),
    }


def _child_metadata(item: Mapping[str, Any]) -> dict[str, Any]:
    data = _data(item)
    link_mode = data.get("linkMode", "")
    filename = data.get("filename", "")
    if link_mode == "linked_file" and not filename:
        filename = Path(str(data.get("path", ""))).name
    return {
        "key": _key(item),
        "item_type": data.get("itemType", ""),
        "title": data.get("title", ""),
        "filename": filename,
        "content_type": data.get("contentType", ""),
        "link_mode": link_mode,
        "parent_key": data.get("parentItem", ""),
    }


def build_source_records(snapshot: WikiSnapshot) -> list[dict[str, Any]]:
    """Convert a Zotero snapshot into deterministic source records."""

    collection_names = _collection_name_map(snapshot.collections)
    collection_tree = collection_table(snapshot.collections)
    projects = dict(snapshot.projects)
    children: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for item in snapshot.items:
        parent_key = str(_data(item).get("parentItem") or "")
        if parent_key:
            children[parent_key].append(item)

    records: list[dict[str, Any]] = []
    for item in snapshot.items:
        data = _data(item)
        item_type = str(data.get("itemType", ""))
        key = _key(item)
        if not key or item_type == "attachment" or data.get("parentItem"):
            continue
        collection_keys = [str(value) for value in data.get("collections", []) or []]
        names = sorted(
            {collection_names[key] for key in collection_keys if key in collection_names},
            key=str.casefold,
        )
        child_items = children.get(key, [])
        attachments = sorted(
            (_child_metadata(child) for child in child_items if _data(child).get("itemType") == "attachment"),
            key=lambda child: (child["filename"].casefold(), child["key"]),
        )
        notes = sorted(
            (_child_metadata(child) for child in child_items if _data(child).get("itemType") == "note"),
            key=lambda child: child["key"],
        )
        creators = [
            name
            for name in (_creator_name(creator) for creator in data.get("creators", []) or [])
            if name
        ]
        record = {
            "zotero_key": key,
            "version": item.get("version", data.get("version", "")),
            "item_type": item_type,
            "title": str(data.get("title") or data.get("name") or "Untitled"),
            "creators": creators,
            "date": data.get("date", ""),
            "year": _year(data.get("date")),
            "citation_key": data.get("citationKey", ""),
            "doi": data.get("DOI", ""),
            "url": data.get("url", ""),
            "abstract": data.get("abstractNote", ""),
            "note": data.get("note", ""),
            "tags": _normalize_tags(data.get("tags", [])),
            "collections": names,
            "projects": memberships(collection_keys, collection_tree, projects),
            "attachments": attachments,
            "child_notes": notes,
        }
        records.append(record)
    return sorted(records, key=lambda record: (record["title"].casefold(), record["zotero_key"]))


def _year(value: Any) -> str:
    match = re.search(r"\b(\d{4})\b", str(value or ""))
    return match.group(1) if match else ""


def _source_markdown(record: Mapping[str, Any]) -> str:
    title = str(record["title"]).replace("\n", " ").strip()
    lines = [
        "<!-- Generated from Zotero metadata. Put curated interpretation in wiki/claims or wiki/projects. -->",
        f"# {title}",
        "",
        f"- Zotero key: `{record['zotero_key']}`",
        f"- Item type: `{record['item_type']}`",
        f"- Citation key: `{record['citation_key'] or 'not-set'}`",
        f"- Date: {record['date'] or 'not-set'}",
        f"- DOI: {record['doi'] or 'not-set'}",
        f"- Projects: {', '.join(record['projects']) or 'unassigned'}",
        "",
        "## Creators",
        "",
    ]
    lines.extend(f"- {creator}" for creator in record["creators"])
    if not record["creators"]:
        lines.append("- Not recorded")
    lines.extend(["", "## Collections", ""])
    lines.extend(f"- {name}" for name in record["collections"])
    if not record["collections"]:
        lines.append("- Not assigned")
    lines.extend(["", "## Tags", ""])
    lines.extend(f"- `{tag['name']}` (type {tag['type']})" for tag in record["tags"])
    if not record["tags"]:
        lines.append("- None")
    lines.extend(["", "## Abstract", "", str(record["abstract"] or "No abstract recorded."), ""])
    if record["attachments"]:
        lines.extend(["## Attachments", ""])
        lines.extend(
            f"- `{attachment['key']}` — {attachment['filename'] or attachment['item_type']}"
            for attachment in record["attachments"]
        )
        lines.append("")
    return "\n".join(lines)


def _catalog(snapshot: WikiSnapshot) -> dict[str, Any]:
    collections = []
    for collection in snapshot.collections:
        data = _data(collection)
        collections.append(
            {
                "key": _key(collection),
                "name": data.get("name", ""),
                "parent_key": data.get("parentCollection", ""),
            }
        )
    tags = []
    for tag in snapshot.tags:
        tags.append({"name": tag.get("tag", ""), "item_count": (tag.get("meta") or {}).get("numItems")})
    searches = []
    for search in snapshot.searches:
        data = _data(search)
        searches.append({"key": _key(search), "name": data.get("name", "")})
    return {
        "collections": sorted(collections, key=lambda value: (str(value["name"]).casefold(), value["key"])),
        "tags": sorted(tags, key=lambda value: str(value["name"]).casefold()),
        "searches": sorted(searches, key=lambda value: str(value["name"]).casefold()),
    }


def _manifest(snapshot: WikiSnapshot, records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    manifest_records = []
    for record in records:
        record_json = _stable_json(record)
        key = str(record["zotero_key"])
        manifest_records.append(
            {
                "zotero_key": key,
                "version": record.get("version", ""),
                "title": record.get("title", ""),
                "projects": list(record.get("projects", [])),
                "record_path": f"{SOURCE_DIRNAME}/{key}/record.json",
                "content_sha256": _sha256(record_json),
            }
        )
    return {
        "schema_version": WIKI_SCHEMA_VERSION,
        "source": "zotero-local-api",
        "item_count": len(snapshot.items),
        "source_count": len(records),
        "collection_count": len(snapshot.collections),
        "tag_count": len(snapshot.tags),
        "search_count": len(snapshot.searches),
        "records": manifest_records,
    }


def _existing_manifest(root: Path) -> dict[str, Any]:
    path = root / MANIFEST_FILENAME
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WikiError(f"Could not read {path}: {exc}") from exc
    return value if isinstance(value, dict) else {}


def materialize_snapshot(
    snapshot: WikiSnapshot,
    root: Path = Path("wiki"),
    *,
    apply: bool = False,
    records: Sequence[Mapping[str, Any]] | None = None,
    rebuild_index: bool = True,
) -> dict[str, Any]:
    """Plan or write a Zotero snapshot without deleting existing wiki records."""

    root = Path(root)
    records = list(records) if records is not None else build_source_records(snapshot)
    manifest = _manifest(snapshot, records)
    catalog = _catalog(snapshot)
    previous = _existing_manifest(root)
    previous_records = {
        str(entry.get("zotero_key")): entry
        for entry in previous.get("records", [])
        if isinstance(entry, Mapping)
    }
    changed = []
    unchanged = []
    for record in records:
        key = record["zotero_key"]
        digest = next(
            entry["content_sha256"]
            for entry in manifest["records"]
            if entry["zotero_key"] == key
        )
        if previous_records.get(key, {}).get("content_sha256") == digest:
            unchanged.append(key)
        else:
            changed.append(key)
    previous_keys = set(previous_records)
    current_keys = {record["zotero_key"] for record in records}
    orphaned = sorted(previous_keys - current_keys)
    result = {
        "mode": "apply" if apply else "dry-run",
        "wiki_root": str(root),
        "items_considered": len(snapshot.items),
        "sources": len(records),
        "changed": len(changed),
        "unchanged": len(unchanged),
        "orphaned_records": orphaned,
        "deleted": 0,
    }
    if not apply:
        result["changed_keys"] = changed
        return result

    root.mkdir(parents=True, exist_ok=True)
    for record in records:
        key = record["zotero_key"]
        source_root = root / SOURCE_DIRNAME / key
        _write_atomic(source_root / "record.json", _stable_json(record))
        _write_atomic(source_root / "source.md", _source_markdown(record))
    _write_atomic(root / CATALOG_FILENAME, _stable_json(catalog))
    _write_atomic(root / MANIFEST_FILENAME, _stable_json(manifest))
    result["changed_keys"] = changed
    if rebuild_index:
        index_result = index_wiki(root, records=records)
        result["index"] = str(root / INDEX_FILENAME)
        result["triage"] = str(root / TRIAGE_FILENAME)
        result["evidence_files"] = index_result["evidence_files"]
        result["evidence_chunks"] = index_result["evidence_chunks"]
        result["triage_queues"] = index_result["triage_queues"]
    return result


def _index_connection(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode=DELETE")
    return connection


def _collect_evidence_chunks(
    root: Path,
    *,
    chunk_lines: int = 12,
    overlap_lines: int = 2,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    """Collect deterministic, non-PDF evidence chunks for the local index."""

    if chunk_lines < 1:
        raise ValueError("chunk_lines must be positive")
    if overlap_lines < 0 or overlap_lines >= chunk_lines:
        raise ValueError("overlap_lines must be non-negative and smaller than chunk_lines")
    root = Path(root)
    evidence_root = root / EVIDENCE_DIRNAME
    if not evidence_root.exists():
        return [], [], []

    chunks: list[dict[str, Any]] = []
    files: list[dict[str, Any]] = []
    warnings: list[str] = []
    stride = chunk_lines - overlap_lines
    for bundle in sorted(path for path in evidence_root.iterdir() if path.is_dir()):
        manifest_path = bundle / "manifest.json"
        if not manifest_path.exists():
            warnings.append(f"Evidence manifest is missing: {manifest_path}")
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            warnings.append(f"Could not read evidence manifest {manifest_path}: {exc}")
            continue
        if not isinstance(manifest, Mapping):
            warnings.append(f"Evidence manifest is not a JSON object: {manifest_path}")
            continue
        entries = manifest.get("files", [])
        if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
            warnings.append(f"Evidence manifest files are not a list: {manifest_path}")
            continue
        zotero_key = bundle.name
        for entry in entries:
            if not isinstance(entry, Mapping):
                warnings.append(f"Ignored malformed evidence entry in {manifest_path}")
                continue
            relative_path = str(entry.get("path", ""))
            if not relative_path:
                warnings.append(f"Ignored evidence entry without a path in {manifest_path}")
                continue
            file_path = _evidence_file_path(bundle, relative_path)
            searchable = file_path.suffix.casefold() in {".md", ".mmd"}
            file_info: dict[str, Any] = {
                "zotero_key": zotero_key,
                "zotero_attachment_key": str(entry.get("zotero_attachment_key", "")),
                "path": _display_path(root, file_path),
                "role": str(entry.get("role", "")),
                "format": str(entry.get("format", "")),
                "source_filename": str(entry.get("source_filename", "")),
                "searchable": searchable,
                "declared_sha256": str(entry.get("sha256", "")) or None,
                "content_sha256": None,
                "hash_matches": None,
                "chunk_count": 0,
            }
            files.append(file_info)
            if not file_path.exists():
                warnings.append(f"Evidence companion is missing: {file_path}")
                continue
            if not searchable:
                # In particular, never read or convert a PDF in the indexer.
                continue
            try:
                raw = file_path.read_bytes()
                text = raw.decode("utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                warnings.append(f"Could not read evidence companion {file_path}: {exc}")
                continue
            content_sha256 = _sha256(raw)
            declared_sha256 = file_info["declared_sha256"]
            hash_matches = (
                None
                if not declared_sha256
                else content_sha256 == declared_sha256
            )
            file_info["content_sha256"] = content_sha256
            file_info["hash_matches"] = hash_matches
            if hash_matches is False:
                warnings.append(f"Evidence companion hash mismatch: {file_path}")
            lines = text.splitlines()
            for start in range(0, len(lines), stride):
                end = min(len(lines), start + chunk_lines)
                chunk_text = "\n".join(lines[start:end]).strip()
                if not chunk_text:
                    if end == len(lines):
                        break
                    continue
                section = _section_for_line(lines, start)
                identity = "\n".join(
                    (
                        zotero_key,
                        file_info["zotero_attachment_key"],
                        file_info["path"],
                        content_sha256,
                        str(start + 1),
                        str(end),
                        chunk_text,
                    )
                )
                chunks.append(
                    {
                        "chunk_id": f"evidence-{_sha256(identity)}",
                        "zotero_key": zotero_key,
                        "zotero_attachment_key": file_info["zotero_attachment_key"],
                        "path": file_info["path"],
                        "role": file_info["role"],
                        "format": file_info["format"],
                        "source_filename": file_info["source_filename"],
                        "content_sha256": content_sha256,
                        "declared_sha256": declared_sha256,
                        "hash_matches": hash_matches,
                        "line_start": start + 1,
                        "line_end": end,
                        "section": section,
                        "text": chunk_text,
                    }
                )
                file_info["chunk_count"] += 1
                if end == len(lines):
                    break
    return chunks, files, warnings


def _curated_source_paths(root: Path, directory: str) -> dict[str, str]:
    """Find source keys in curated Markdown without requiring valid metadata."""

    paths: dict[str, str] = {}
    for path in sorted((Path(root) / directory).glob("*.md")):
        if path.name.casefold() == "readme.md":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.splitlines():
            match = re.match(
                r"^\s*-\s*(?:Zotero key|zotero_key)\s*:\s*(?:\x60)?([A-Za-z0-9]+)",
                line,
            )
            if match:
                paths[match.group(1)] = _display_path(Path(root), path)
                break
    return paths


def _curated_source_metadata(root: Path, directory: str) -> dict[str, dict[str, str]]:
    """Return curated source paths plus explicit scaffold/brief state."""

    metadata: dict[str, dict[str, str]] = {}
    for path in sorted((Path(root) / directory).glob("*.md")):
        if path.name.casefold() == "readme.md":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        key_match = re.search(
            r"^\s*-\s*(?:Zotero key|zotero_key)\s*:\s*(?:\x60)?([A-Za-z0-9]+)",
            text,
            flags=re.MULTILINE,
        )
        if not key_match:
            continue
        status_match = re.search(
            r"^\s*-\s*brief_status\s*:\s*([^\s]+)",
            text,
            flags=re.MULTILINE | re.IGNORECASE,
        )
        metadata[key_match.group(1)] = {
            "path": _display_path(Path(root), path),
            "status": status_match.group(1).strip().casefold() if status_match else "briefed",
        }
    return metadata


def _build_triage_index(
    root: Path,
    records: Sequence[Mapping[str, Any]],
    *,
    evidence_files: Sequence[Mapping[str, Any]],
    evidence_chunks: Sequence[Mapping[str, Any]],
    evidence_warnings: Sequence[str],
) -> dict[str, Any]:
    """Build the generated all-source curation and relevance queue."""

    root = Path(root)
    classification = _load_classification_config(root)
    assignments = classification["assignments"]
    assignment_path = Path(classification["path"])
    record_keys = {str(record.get("zotero_key", "")) for record in records}
    assignment_orphans = sorted(set(assignments) - record_keys)
    brief_metadata = _curated_source_metadata(root, "papers")
    brief_paths = {key: value["path"] for key, value in brief_metadata.items()}
    claim_paths = _curated_source_paths(root, CLAIMS_DIRNAME)
    evidence_by_key: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "searchable_file_count": 0,
            "attachment_keys": set(),
            "chunk_count": 0,
            "hash_mismatch_count": 0,
        }
    )
    for file_info in evidence_files:
        if not file_info.get("searchable"):
            continue
        key = str(file_info.get("zotero_key", ""))
        if not key:
            continue
        summary = evidence_by_key[key]
        summary["searchable_file_count"] += 1
        attachment_key = str(file_info.get("zotero_attachment_key", ""))
        if attachment_key:
            summary["attachment_keys"].add(attachment_key)
        if file_info.get("hash_matches") is False:
            summary["hash_mismatch_count"] += 1
    for chunk in evidence_chunks:
        key = str(chunk.get("zotero_key", ""))
        if key:
            evidence_by_key[key]["chunk_count"] += 1

    entries: list[dict[str, Any]] = []
    for record in records:
        key = str(record.get("zotero_key", ""))
        projects = sorted(str(value) for value in record.get("projects", []) if value)
        evidence = evidence_by_key.get(key, {})
        assignment = assignments.get(key)
        suggestions = _suggested_classification(record)
        if assignment:
            classification_view = {
                **assignment,
                "path": _display_path(root, assignment_path),
            }
            assignment_state = str(assignment["state"])
            relevance = str(assignment["relevance"])
            relevance_basis = "curated-assignment"
            domains = list(assignment["domains"])
            research_threads = list(assignment["research_threads"])
        else:
            classification_view = {
                "state": "unassigned",
                "relevance": "",
                "domains": [],
                "research_threads": [],
                "reason": "",
                "reviewer": "",
                "reviewed_at": "",
                "path": _display_path(root, assignment_path),
            }
            assignment_state = "unassigned"
            relevance = ""
            relevance_basis = "project-collection" if projects else "none"
            domains = []
            research_threads = []
        brief_status = str(brief_metadata.get(key, {}).get("status", ""))
        briefed = key in brief_paths and brief_status != "scaffold"
        brief_scaffolded = key in brief_paths and brief_status == "scaffold"
        claims_curated = key in claim_paths
        if briefed:
            status = "briefed"
        elif brief_scaffolded:
            status = "brief-scaffolded"
        elif claims_curated:
            status = "claims-curated"
        elif evidence.get("chunk_count", 0):
            status = "evidence-ready"
        elif projects or relevance in {"candidate", "relevant", "uncertain"}:
            status = "candidate"
        else:
            status = "discovered"
        queue_reason = ""
        if assignment is None:
            queue_reason = (
                "Needs deliberate classification; metadata suggestions are review aids, "
                "not assignments."
            )
        elif assignment_state == "proposed":
            queue_reason = "Has a proposed classification awaiting review."
        elif relevance == "not_relevant":
            queue_reason = "Explicitly marked not relevant; retained for discoverability."
        elif (projects or relevance in {"candidate", "relevant"}) and not briefed:
            queue_reason = "Mapped to an initial project view but has no paper brief."
        elif evidence.get("chunk_count", 0) and not briefed:
            queue_reason = "Has indexed companion evidence but has no paper brief."
        if brief_scaffolded:
            queue_reason = "Has a metadata-only brief scaffold; fill it from reviewed evidence."
        relevance_signals = [f"project:{project}" for project in projects]
        if assignment:
            relevance_signals.append(f"assignment:{relevance}")
        relevance_signals.extend(f"suggested-domain:{domain}" for domain in suggestions["domains"])
        relevance_signals.extend(
            f"suggested-thread:{thread}"
            for thread in suggestions["research_threads"]
        )
        entries.append(
            {
                "zotero_key": key,
                "title": record.get("title", ""),
                "citation_key": record.get("citation_key", ""),
                "item_type": record.get("item_type", ""),
                "year": record.get("year", ""),
                "projects": projects,
                "collections": list(record.get("collections", [])),
                "tags": [
                    tag.get("name", "")
                    for tag in record.get("tags", [])
                    if isinstance(tag, Mapping)
                ],
                "relevance_signals": relevance_signals,
                "relevance_basis": relevance_basis,
                "domains": domains,
                "research_threads": research_threads,
                "suggested_domains": suggestions["domains"],
                "suggested_research_threads": suggestions["research_threads"],
                "classification": classification_view,
                "status": status,
                "brief_path": brief_paths.get(key, ""),
                "brief_status": brief_status,
                "claim_paths": [claim_paths[key]] if key in claim_paths else [],
                "evidence": {
                    "searchable_file_count": evidence.get("searchable_file_count", 0),
                    "attachment_keys": sorted(evidence.get("attachment_keys", set())),
                    "chunk_count": evidence.get("chunk_count", 0),
                    "hash_mismatch_count": evidence.get("hash_mismatch_count", 0),
                },
                "queue_reason": queue_reason,
            }
        )
    queues = {
        "needs_classification": [
            entry["zotero_key"]
            for entry in entries
            if entry["classification"]["state"] == "unassigned"
        ],
        "classification_review": [
            entry["zotero_key"]
            for entry in entries
            if entry["classification"]["state"] == "proposed"
        ],
        "unbriefed_relevant": [
            entry["zotero_key"]
            for entry in entries
            if entry["classification"]["relevance"] != "not_relevant"
            and (entry["projects"] or entry["classification"]["relevance"] in {"candidate", "relevant", "uncertain"})
            and entry["status"] != "briefed"
        ],
        "brief_scaffolded": [
            entry["zotero_key"]
            for entry in entries
            if entry["status"] == "brief-scaffolded"
        ],
        "evidence_ready": [
            entry["zotero_key"]
            for entry in entries
            if entry["status"] == "evidence-ready"
        ],
        "briefed": [
            entry["zotero_key"]
            for entry in entries
            if entry["status"] == "briefed"
        ],
        "discovered": [
            entry["zotero_key"]
            for entry in entries
            if entry["status"] == "discovered"
        ],
    }
    counts: dict[str, int] = defaultdict(int)
    for entry in entries:
        counts[entry["status"]] += 1
    classification_counts: dict[str, int] = defaultdict(int)
    relevance_counts: dict[str, int] = defaultdict(int)
    for entry in entries:
        state = str(entry["classification"]["state"])
        classification_counts[state] += 1
        relevance_value = str(entry["classification"]["relevance"] or "unclassified")
        relevance_counts[relevance_value] += 1
    warnings = list(evidence_warnings)
    if assignment_orphans:
        warnings.append(
            "Classification assignments reference sources not present in the current snapshot: "
            + ", ".join(assignment_orphans)
        )
    return {
        "schema_version": TRIAGE_SCHEMA_VERSION,
        "source": "zotero-companion-generated",
        "source_count": len(entries),
        "brief_count": sum(1 for entry in entries if entry["status"] == "briefed"),
        "brief_scaffold_count": sum(1 for entry in entries if entry["status"] == "brief-scaffolded"),
        "claim_source_count": len(claim_paths),
        "evidence_chunk_count": len(evidence_chunks),
        "evidence_file_count": sum(
            1 for file_info in evidence_files if file_info.get("searchable")
        ),
        "status_counts": dict(sorted(counts.items())),
        "classification_counts": dict(sorted(classification_counts.items())),
        "relevance_counts": dict(sorted(relevance_counts.items())),
        "classification_path": _display_path(root, assignment_path),
        "classification_vocabulary": {
            "domains": classification["domains"],
            "research_threads": classification["research_threads"],
            "assignment_states": list(ASSIGNMENT_STATES),
            "relevances": list(ASSIGNMENT_RELEVANCES),
        },
        "relevance_policy": (
            "A project collection is a triage signal, not a validated scientific conclusion. "
            "Metadata suggestions are review aids only; explicit domains and research threads "
            "require a curated assignment with a reason. Sources remain discoverable even "
            "when they have no relevance signal."
        ),
        "queues": queues,
        "entries": entries,
        "warnings": warnings,
    }


def _markdown_table_cell(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip()


def _source_index_link(value: str, root: Path) -> str:
    """Turn a generated wiki path into a link from ``wiki/sources/index.md``."""

    raw = Path(value)
    if raw.is_absolute():
        try:
            raw = raw.resolve().relative_to(Path(root).resolve())
        except ValueError:
            return str(value)
    if raw.parts and raw.parts[0] == Path(root).name:
        raw = Path(*raw.parts[1:])
    return f"../{raw.as_posix()}"


def _source_corpus_index(root: Path, triage: Mapping[str, Any]) -> str:
    """Build the generated human-readable catalog for the whole Zotero corpus."""

    entries = triage.get("entries", [])
    lines = [
        "# Zotero source corpus",
        "",
        "<!-- Generated by `wiki-index`; do not hand-edit. -->",
        "",
        f"Materialized top-level Zotero sources: **{triage.get('source_count', 0)}**.",
        "",
        "This is the whole-library browse surface. Use the generated source record",
        "for bibliographic facts, the triage queues for curation work, and evidence",
        "or paper briefs before reopening a PDF.",
        "",
        "| Source | Zotero key | Year | Type | State | Classification | Projects | Brief | Evidence |",
        "| --- | --- | ---: | --- | --- | --- | --- | --- | --- |",
    ]
    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
        entries = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        key = str(entry.get("zotero_key", ""))
        title = _markdown_table_cell(entry.get("title", "Untitled")) or "Untitled"
        source_link = f"[{title}]({key}/source.md)"
        domains = [str(value) for value in entry.get("domains", []) if value]
        threads = [str(value) for value in entry.get("research_threads", []) if value]
        if domains or threads:
            classification = "; ".join(domains + threads)
        else:
            suggested = [
                f"suggested:{value}"
                for value in entry.get("suggested_domains", [])
                if value
            ] + [
                f"suggested:{value}"
                for value in entry.get("suggested_research_threads", [])
                if value
            ]
            classification = "; ".join(suggested) if suggested else "unassigned"
        evidence = entry.get("evidence", {})
        evidence_files = int(evidence.get("searchable_file_count", 0) or 0) if isinstance(evidence, Mapping) else 0
        evidence_chunks = int(evidence.get("chunk_count", 0) or 0) if isinstance(evidence, Mapping) else 0
        evidence_link = (
            f"[{evidence_files} files/{evidence_chunks} chunks](../{EVIDENCE_DIRNAME}/{key}/README.md)"
            if evidence_files
            else "—"
        )
        brief_path = str(entry.get("brief_path", ""))
        brief_link = (
            f"[brief]({_source_index_link(brief_path, root)})"
            if brief_path
            else "—"
        )
        lines.append(
            "| "
            + " | ".join(
                (
                    source_link,
                    f"`{_markdown_table_cell(key)}`",
                    _markdown_table_cell(entry.get("year", "")) or "—",
                    _markdown_table_cell(entry.get("item_type", "")) or "—",
                    _markdown_table_cell(entry.get("status", "")) or "—",
                    _markdown_table_cell(classification),
                    _markdown_table_cell(", ".join(str(value) for value in entry.get("projects", []) if value)) or "—",
                    brief_link,
                    evidence_link,
                )
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def index_wiki(root: Path = Path("wiki"), *, records: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """Build an ignored SQLite search index from materialized source records."""

    root = Path(root)
    if records is None:
        manifest_path = root / MANIFEST_FILENAME
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise WikiError(f"Could not read manifest {manifest_path}: {exc}") from exc
            if not isinstance(manifest, Mapping):
                raise WikiError(f"Manifest is not a JSON object: {manifest_path}")
            manifest_records = manifest.get("records", [])
            if not isinstance(manifest_records, Sequence) or isinstance(manifest_records, (str, bytes)):
                raise WikiError(f"Manifest records are not a list: {manifest_path}")
            paths = [
                root / SOURCE_DIRNAME / str(entry.get("zotero_key")) / "record.json"
                for entry in manifest_records
                if isinstance(entry, Mapping) and str(entry.get("zotero_key", "")).strip()
            ]
        else:
            paths = sorted((root / SOURCE_DIRNAME).glob("*/record.json"))
        records = []
        for path in paths:
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise WikiError(f"Could not read source record {path}: {exc}") from exc
            if isinstance(record, Mapping):
                records.append(record)
    root.mkdir(parents=True, exist_ok=True)
    index_path = root / INDEX_FILENAME
    temporary = root / f".{INDEX_FILENAME}.tmp"
    if temporary.exists():
        temporary.unlink()
    connection = _index_connection(temporary)
    try:
        try:
            connection.execute(
                "CREATE VIRTUAL TABLE documents USING fts5(" 
                "zotero_key UNINDEXED, title, body, projects UNINDEXED, path UNINDEXED)"
            )
            fts = True
        except sqlite3.OperationalError:
            connection.execute(
                "CREATE TABLE documents (zotero_key TEXT PRIMARY KEY, title TEXT, body TEXT, projects TEXT, path TEXT)"
            )
            fts = False
        for record in records:
            key = str(record["zotero_key"])
            body = _search_text(record)
            connection.execute(
                "INSERT INTO documents(zotero_key, title, body, projects, path) VALUES (?, ?, ?, ?, ?)",
                (
                    key,
                    str(record.get("title", "")),
                    body,
                    " ".join(record.get("projects", [])),
                    f"{SOURCE_DIRNAME}/{key}/record.json",
                ),
            )
        evidence_chunks, evidence_files, evidence_warnings = _collect_evidence_chunks(root)
        connection.execute(
            """
            CREATE TABLE evidence_chunks (
                chunk_id TEXT PRIMARY KEY,
                zotero_key TEXT NOT NULL,
                zotero_attachment_key TEXT,
                path TEXT NOT NULL,
                role TEXT,
                format TEXT,
                source_filename TEXT,
                content_sha256 TEXT NOT NULL,
                declared_sha256 TEXT,
                hash_matches INTEGER,
                line_start INTEGER NOT NULL,
                line_end INTEGER NOT NULL,
                section TEXT,
                text TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX evidence_chunks_source_idx ON evidence_chunks(zotero_key)"
        )
        connection.execute(
            "CREATE INDEX evidence_chunks_path_idx ON evidence_chunks(path)"
        )
        for chunk in evidence_chunks:
            connection.execute(
                """
                INSERT INTO evidence_chunks(
                    chunk_id, zotero_key, zotero_attachment_key, path, role,
                    format, source_filename, content_sha256, declared_sha256,
                    hash_matches, line_start, line_end, section, text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk["chunk_id"],
                    chunk["zotero_key"],
                    chunk["zotero_attachment_key"],
                    chunk["path"],
                    chunk["role"],
                    chunk["format"],
                    chunk["source_filename"],
                    chunk["content_sha256"],
                    chunk["declared_sha256"],
                    chunk["hash_matches"],
                    chunk["line_start"],
                    chunk["line_end"],
                    chunk["section"],
                    chunk["text"],
                ),
            )
        connection.execute("CREATE TABLE index_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute(
            "INSERT INTO index_metadata(key, value) VALUES (?, ?)",
            ("fts5", "true" if fts else "false"),
        )
        connection.execute(
            "INSERT INTO index_metadata(key, value) VALUES (?, ?)",
            ("schema_version", str(INDEX_SCHEMA_VERSION)),
        )
        connection.execute(
            "INSERT INTO index_metadata(key, value) VALUES (?, ?)",
            ("evidence_chunk_count", str(len(evidence_chunks))),
        )
        connection.commit()
    finally:
        connection.close()
    os.replace(temporary, index_path)
    triage = _build_triage_index(
        root,
        records,
        evidence_files=evidence_files,
        evidence_chunks=evidence_chunks,
        evidence_warnings=evidence_warnings,
    )
    _write_atomic(root / TRIAGE_FILENAME, _stable_json(triage))
    source_index_path = root / SOURCE_DIRNAME / "index.md"
    _write_atomic(source_index_path, _source_corpus_index(root, triage))
    return {
        "index": str(index_path),
        "source_index": str(source_index_path),
        "documents": len(records),
        "fts5": fts,
        "evidence_files": sum(
            1 for file_info in evidence_files if file_info.get("searchable")
        ),
        "evidence_manifest_entries": len(evidence_files),
        "evidence_chunks": len(evidence_chunks),
        "evidence_warnings": evidence_warnings,
        "triage": str(root / TRIAGE_FILENAME),
        "triage_queues": {
            name: len(values)
            for name, values in triage.get("queues", {}).items()
        },
    }


def _search_text(record: Mapping[str, Any]) -> str:
    values = [
        record.get("title", ""),
        " ".join(record.get("creators", [])),
        record.get("abstract", ""),
        record.get("note", ""),
        " ".join(tag.get("name", "") for tag in record.get("tags", [])),
        " ".join(record.get("collections", [])),
        " ".join(record.get("projects", [])),
    ]
    return "\n".join(str(value) for value in values if value)


def _load_index_metadata(connection: sqlite3.Connection) -> bool:
    try:
        value = connection.execute(
            "SELECT value FROM index_metadata WHERE key='fts5'"
        ).fetchone()
    except sqlite3.OperationalError:
        return False
    return bool(value and value[0] == "true")


def search_wiki(
    root: Path = Path("wiki"),
    *,
    query: str = "",
    project: str | None = None,
    limit: int | None = 20,
) -> list[dict[str, Any]]:
    """Search materialized source records using the local SQLite index."""

    if limit is not None and limit < 1:
        raise ValueError("limit must be positive")
    sql_limit = -1 if limit is None else limit
    index_path = Path(root) / INDEX_FILENAME
    if not index_path.exists():
        raise WikiError(f"Search index is missing: {index_path}; run sync --apply first")
    connection = sqlite3.connect(index_path)
    try:
        fts = _load_index_metadata(connection)
        project_filter = ""
        project_params: list[str] = []
        if project:
            manifest_keys: set[str] = set()
            try:
                manifest = manifest_lookup(Path(root), project)
            except ManifestError:
                manifest = None
            if manifest is not None:
                raw_source_keys = manifest.get("source_keys", [])
                if isinstance(raw_source_keys, (str, bytes)) or not isinstance(
                    raw_source_keys, Sequence
                ):
                    raw_source_keys = []
                manifest_keys = {
                    str(key).strip()
                    for key in raw_source_keys
                    if str(key).strip()
                }
            project_filter = " AND (instr(' ' || projects || ' ', ' ' || ? || ' ') > 0"
            project_params.append(project)
            if manifest_keys:
                placeholders = ",".join("?" for _ in manifest_keys)
                project_filter += f" OR zotero_key IN ({placeholders})"
                project_params.extend(sorted(manifest_keys))
            project_filter += ")"
        if query.strip() and fts:
            terms = [term for term in re.findall(r"[\w-]+", query, flags=re.UNICODE) if term]
            if not terms:
                rows = []
            else:
                match = " AND ".join(f'"{term.replace(chr(34), "")}"' for term in terms)
                params = [match, *project_params, sql_limit]
                rows = connection.execute(
                    "SELECT zotero_key, title, projects, path FROM documents "
                    "WHERE documents MATCH ?" + project_filter
                    + " ORDER BY bm25(documents, 0, 5, 1, 0, 0), zotero_key LIMIT ?",
                    params,
                ).fetchall()
        elif query.strip():
            pattern = f"%{query.casefold()}%"
            params = [pattern, *project_params, sql_limit]
            connection.create_function(
                "relevance", 2,
                lambda title, body: 5 * _query_score(query, [title]) + _query_score(query, [body]),
            )
            rows = connection.execute(
                "SELECT zotero_key, title, projects, path FROM documents "
                "WHERE lower(title || ' ' || body) LIKE ?" + project_filter
                + " ORDER BY relevance(title, body) DESC, zotero_key LIMIT ?",
                params,
            ).fetchall()
        else:
            params = [*project_params, sql_limit]
            rows = connection.execute(
                "SELECT zotero_key, title, projects, path FROM documents "
                "WHERE 1=1" + project_filter + " ORDER BY zotero_key LIMIT ?",
                params,
            ).fetchall()
    finally:
        connection.close()
    results = []
    for key, title, projects, path in rows:
        record_path = Path(root) / path
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WikiError(f"Could not read indexed source {record_path}: {exc}") from exc
        results.append(
            {
                "zotero_key": key,
                "title": title,
                "projects": record.get("projects", []),
                "item_type": record.get("item_type", ""),
                "citation_key": record.get("citation_key", ""),
                "path": path,
                "doi": record.get("doi", ""),
                "year": record.get("year", ""),
            }
        )
        if limit is not None and len(results) >= limit:
            break
    return results


def evidence_coverage(
    root: Path,
    *,
    source_keys: Sequence[str],
) -> dict[str, Any]:
    """Report indexed companion coverage for the sources in a context pack."""

    keys = sorted({str(key) for key in source_keys if key})
    index_path = Path(root) / INDEX_FILENAME
    result: dict[str, Any] = {
        "index_path": _display_path(Path(root), index_path),
        "index_available": False,
        "matched_source_count": len(keys),
        "sources_with_indexed_evidence": 0,
        "sources_without_indexed_evidence": keys,
        "coverage_ratio": None if not keys else 0.0,
        "evidence_file_count": 0,
        "evidence_attachment_count": 0,
        "evidence_chunk_count": 0,
        "hash_mismatch_count": 0,
    }
    if not index_path.exists() or not keys:
        return result
    connection = sqlite3.connect(index_path)
    try:
        try:
            placeholders = ",".join("?" for _ in keys)
            rows = connection.execute(
                f"""
                SELECT zotero_key,
                       COUNT(DISTINCT path),
                       COUNT(DISTINCT zotero_attachment_key),
                       COUNT(*),
                       SUM(CASE WHEN hash_matches = 0 THEN 1 ELSE 0 END)
                FROM evidence_chunks
                WHERE zotero_key IN ({placeholders})
                GROUP BY zotero_key
                """,
                keys,
            ).fetchall()
        except sqlite3.OperationalError:
            return result
        indexed_keys = {str(row[0]) for row in rows}
        result["index_available"] = True
        result["sources_with_indexed_evidence"] = len(indexed_keys)
        result["sources_without_indexed_evidence"] = [
            key for key in keys if key not in indexed_keys
        ]
        result["coverage_ratio"] = round(len(indexed_keys) / len(keys), 3)
        result["evidence_file_count"] = sum(int(row[1] or 0) for row in rows)
        result["evidence_attachment_count"] = sum(int(row[2] or 0) for row in rows)
        result["evidence_chunk_count"] = sum(int(row[3] or 0) for row in rows)
        result["hash_mismatch_count"] = sum(int(row[4] or 0) for row in rows)
    finally:
        connection.close()
    return result


def search_evidence_chunks(
    root: Path,
    *,
    source_keys: Sequence[str] | None = None,
    query: str = "",
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Search rebuildable evidence chunks without reopening source companions."""

    if limit < 1:
        raise ValueError("limit must be positive")
    terms = _query_terms(query)
    if not terms:
        return []
    index_path = Path(root) / INDEX_FILENAME
    if not index_path.exists():
        raise WikiError(f"Search index is missing: {index_path}; run wiki-index --apply first")
    keys = sorted({str(key) for key in source_keys or () if key})
    connection = sqlite3.connect(index_path)
    try:
        try:
            columns = (
                "chunk_id, zotero_key, zotero_attachment_key, path, role, format, "
                "source_filename, content_sha256, declared_sha256, hash_matches, "
                "line_start, line_end, section, text"
            )
            if source_keys is None:
                rows = connection.execute(
                    f"SELECT {columns} FROM evidence_chunks"
                ).fetchall()
            elif not keys:
                return []
            else:
                placeholders = ",".join("?" for _ in keys)
                rows = connection.execute(
                    f"SELECT {columns} FROM evidence_chunks "
                    f"WHERE zotero_key IN ({placeholders})",
                    keys,
                ).fetchall()
        except sqlite3.OperationalError as exc:
            raise WikiError(
                f"Evidence chunk index is unavailable in {index_path}; run wiki-index --apply"
            ) from exc
    finally:
        connection.close()

    candidates: list[tuple[int, int, str, int, dict[str, Any]]] = []
    for row in rows:
        (
            chunk_id,
            zotero_key,
            attachment_key,
            path,
            role,
            file_format,
            source_filename,
            content_sha256,
            declared_sha256,
            hash_matches,
            line_start,
            line_end,
            section,
            text,
        ) = row
        values = (text, section)
        score = _query_score(query, values)
        if score == 0:
            continue
        haystack = "\n".join(str(value) for value in values if value).casefold()
        matched_terms = [term for term in terms if term in haystack]
        passage = {
            "chunk_id": chunk_id,
            "zotero_key": zotero_key,
            "zotero_attachment_key": attachment_key,
            "path": path,
            "role": role,
            "format": file_format,
            "source_filename": source_filename,
            "content_sha256": content_sha256,
            "declared_sha256": declared_sha256,
            "hash_matches": None if hash_matches is None else bool(hash_matches),
            "hash_verification": "index-time; current companion file not rechecked",
            "line_start": line_start,
            "line_end": line_end,
            "section": section,
            "locator": f"{path}:L{line_start}-L{line_end}",
            "matched_terms": sorted(set(matched_terms)),
            "match_score": score,
            "text": text,
        }
        role_priority = 0 if role == "main_article" else 1
        candidates.append((score, role_priority, str(path), int(line_start), passage))
    candidates.sort(key=lambda item: (-item[0], item[1], item[2], item[3]))
    results: list[dict[str, Any]] = []
    occupied: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for _, _, path, _, passage in candidates:
        interval = (int(passage["line_start"]), int(passage["line_end"]))
        if any(
            interval[0] <= existing_end and existing_start <= interval[1]
            for existing_start, existing_end in occupied[path]
        ):
            continue
        occupied[path].append(interval)
        results.append(passage)
        if len(results) >= limit:
            break
    return results


def triage_wiki(
    root: Path = Path("wiki"),
    *,
    status: str | None = None,
    project: str | None = None,
    queue: str | None = None,
    domain: str | None = None,
    research_thread: str | None = None,
    relevance: str | None = None,
    classification_state: str | None = None,
    assigned_only: bool = False,
    limit: int = 20,
) -> dict[str, Any]:
    """Read the generated all-source triage index and bounded work queue."""

    if limit < 1:
        raise ValueError("limit must be positive")
    root = Path(root)
    path = root / TRIAGE_FILENAME
    if not path.exists():
        raise WikiError(f"Triage index is missing: {path}; run wiki-index --apply first")
    try:
        triage = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WikiError(f"Could not read triage index {path}: {exc}") from exc
    if not isinstance(triage, Mapping):
        raise WikiError(f"Triage index is not a JSON object: {path}")
    entries = [
        dict(entry)
        for entry in triage.get("entries", [])
        if isinstance(entry, Mapping)
    ]
    if queue:
        queue_keys = {
            str(key) for key in triage.get("queues", {}).get(queue, [])
        }
        entries = [entry for entry in entries if entry.get("zotero_key") in queue_keys]
    if status:
        entries = [entry for entry in entries if entry.get("status") == status]
    if project:
        entries = [
            entry
            for entry in entries
            if project in entry.get("projects", [])
        ]
    vocabulary = triage.get("classification_vocabulary", {})
    domain_ids = {
        str(entry.get("id"))
        for entry in vocabulary.get("domains", [])
        if isinstance(entry, Mapping)
    }
    thread_ids = {
        str(entry.get("id"))
        for entry in vocabulary.get("research_threads", [])
        if isinstance(entry, Mapping)
    }
    if domain and domain_ids and domain not in domain_ids:
        raise WikiError(f"Unknown domain {domain}; use one of: {', '.join(sorted(domain_ids))}")
    if research_thread and thread_ids and research_thread not in thread_ids:
        raise WikiError(
            f"Unknown research thread {research_thread}; use one of: {', '.join(sorted(thread_ids))}"
        )
    if relevance and relevance not in ASSIGNMENT_RELEVANCES:
        raise WikiError(
            f"Unknown relevance {relevance}; use one of: {', '.join(ASSIGNMENT_RELEVANCES)}"
        )
    if classification_state and classification_state not in {"unassigned", *ASSIGNMENT_STATES}:
        allowed = ("unassigned",) + ASSIGNMENT_STATES
        raise WikiError(
            f"Unknown classification state {classification_state}; use one of: {', '.join(allowed)}"
        )
    if relevance:
        entries = [
            entry
            for entry in entries
            if str((entry.get("classification") or {}).get("relevance", "")) == relevance
        ]
    if classification_state:
        entries = [
            entry
            for entry in entries
            if str((entry.get("classification") or {}).get("state", ""))
            == classification_state
        ]
    if domain:
        entries = [
            entry
            for entry in entries
            if domain
            in (
                entry.get("domains", [])
                if assigned_only
                else set(entry.get("domains", [])) | set(entry.get("suggested_domains", []))
            )
        ]
    if research_thread:
        entries = [
            entry
            for entry in entries
            if research_thread
            in (
                entry.get("research_threads", [])
                if assigned_only
                else set(entry.get("research_threads", []))
                | set(entry.get("suggested_research_threads", []))
            )
        ]
    total = len(entries)
    all_queues = triage.get("queues", {})
    queue_counts = {
        str(name): len(values)
        for name, values in all_queues.items()
        if isinstance(values, Sequence) and not isinstance(values, (str, bytes))
    }
    return {
        "path": _display_path(root, path),
        "queue": queue or "",
        "status": status or "",
        "project": project or "",
        "domain": domain or "",
        "research_thread": research_thread or "",
        "relevance": relevance or "",
        "classification_state": classification_state or "",
        "assigned_only": assigned_only,
        "total": total,
        "entries": entries[:limit],
        "queue_counts": queue_counts,
        "status_counts": triage.get("status_counts", {}),
        "classification_counts": triage.get("classification_counts", {}),
        "relevance_counts": triage.get("relevance_counts", {}),
        "warnings": triage.get("warnings", []),
    }


def classify_source(
    root: Path = Path("wiki"),
    zotero_key: str = "",
    *,
    relevance: str,
    domains: Sequence[str] = (),
    research_threads: Sequence[str] = (),
    reason: str,
    state: str = "proposed",
    reviewer: str = "",
    reviewed_at: str = "",
    apply: bool = False,
) -> dict[str, Any]:
    """Plan or record one explicit, reasoned source classification."""

    root = Path(root)
    key = str(zotero_key).strip()
    if not key:
        raise ValueError("zotero_key must not be empty")
    source_path = root / SOURCE_DIRNAME / key / "record.json"
    if not source_path.exists():
        raise WikiError(f"Cannot classify missing materialized source: {source_path}")
    classification = _load_classification_config(root)
    path = Path(classification["path"])
    domain_ids = {str(entry["id"]) for entry in classification["domains"]}
    thread_ids = {str(entry["id"]) for entry in classification["research_threads"]}
    normalized_domains = _string_values(domains, field="domains", path=path, key=key)
    normalized_threads = _string_values(
        research_threads,
        field="research_threads",
        path=path,
        key=key,
    )
    unknown_domains = sorted(set(normalized_domains) - domain_ids)
    if unknown_domains:
        raise ValueError(f"Unknown domains: {', '.join(unknown_domains)}")
    unknown_threads = sorted(set(normalized_threads) - thread_ids)
    if unknown_threads:
        raise ValueError(f"Unknown research threads: {', '.join(unknown_threads)}")
    if state not in ASSIGNMENT_STATES:
        raise ValueError(f"state must be one of: {', '.join(ASSIGNMENT_STATES)}")
    if relevance not in ASSIGNMENT_RELEVANCES:
        raise ValueError(f"relevance must be one of: {', '.join(ASSIGNMENT_RELEVANCES)}")
    normalized_reason = str(reason).strip()
    if not normalized_reason:
        raise ValueError("reason must not be empty")
    assignment = {
        "state": state,
        "relevance": relevance,
        "domains": normalized_domains,
        "research_threads": normalized_threads,
        "reason": normalized_reason,
        "reviewer": str(reviewer).strip(),
        "reviewed_at": str(reviewed_at).strip(),
    }
    previous = classification["assignments"].get(key)
    result: dict[str, Any] = {
        "mode": "apply" if apply else "dry-run",
        "zotero_key": key,
        "classification_path": _display_path(root, path),
        "changed": previous != assignment,
        "assignment": assignment,
        "repository_only": True,
        "zotero_mutation": False,
    }
    if not apply:
        result["would_write"] = _display_path(root, path)
        return result
    updated = dict(classification["config"])
    updated_assignments = dict(updated.get("assignments", {}))
    updated_assignments[key] = assignment
    updated["assignments"] = updated_assignments
    _write_atomic(path, _stable_json(updated))
    index_result = index_wiki(root)
    result["index"] = index_result["index"]
    result["triage"] = index_result["triage"]
    result["triage_queues"] = index_result["triage_queues"]
    return result


def _strip_metadata_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "`\"'":
        return value[1:-1].strip()
    return value.strip("`").strip()


def _markdown_section(text: str, heading: str) -> str:
    """Return the body of one level-two Markdown section."""

    lines = text.splitlines()
    heading_key = heading.casefold()
    start: int | None = None
    for index, line in enumerate(lines):
        if line.startswith("## ") and line[3:].strip().casefold() == heading_key:
            start = index + 1
            break
    if start is None:
        return ""
    end = len(lines)
    for index in range(start, len(lines)):
        if lines[index].startswith("## "):
            end = index
            break
    return "\n".join(lines[start:end]).strip()


def _resolve_reference(root: Path, reference: str, *, base: Path | None = None) -> Path:
    """Resolve a repo or wiki-relative reference without accepting path escapes."""

    raw = Path(reference)
    if raw.is_absolute():
        candidate = raw
    elif base is not None:
        candidate = base / raw
    else:
        root = Path(root)
        candidates = [root / raw]
        if root.name and raw.parts and raw.parts[0] == root.name:
            candidates.insert(0, root.parent / raw)
        candidate = next((path for path in candidates if path.exists()), candidates[0])
    resolved = candidate.resolve()
    root_resolved = Path(root).resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise WikiError(f"Reference escapes repository root: {reference}")
    return resolved


def _display_path(root: Path, path: Path) -> str:
    path = path.resolve()
    root = Path(root).resolve()
    try:
        return str(path.relative_to(root.parent))
    except ValueError:
        return str(path.relative_to(root))


def _parse_claim_document(root: Path, path: Path) -> dict[str, Any]:
    """Parse one curated claim Markdown file and enforce its provenance header."""

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise WikiError(f"Could not read claim {path}: {exc}") from exc
    title = next(
        (line[2:].strip() for line in text.splitlines() if line.startswith("# ")),
        path.stem,
    )
    metadata: dict[str, str] = {}
    for line in text.splitlines():
        if line.startswith("## "):
            break
        match = re.match(r"^-\s+([A-Za-z][\w-]*):\s*(.+?)\s*$", line)
        if match:
            metadata[match.group(1)] = _strip_metadata_value(match.group(2))
    missing = [field for field in CLAIM_REQUIRED_METADATA if not metadata.get(field)]
    if missing:
        fields = ", ".join(missing)
        raise WikiError(f"Claim {path} is missing required metadata: {fields}")
    claim_text = _markdown_section(text, "Claim")
    if not claim_text:
        raise WikiError(f"Claim {path} has no Claim section")
    return {
        "path": _display_path(root, path),
        "title": title,
        **metadata,
        "claim": claim_text,
        "evidence": _markdown_section(text, "Evidence and limits"),
        "implementation": _markdown_section(text, "Implementation mapping"),
        "open_question": _markdown_section(text, "Open question"),
    }


def _load_claim_documents(root: Path) -> list[dict[str, Any]]:
    claims_path = Path(root) / CLAIMS_DIRNAME
    if not claims_path.exists():
        return []
    documents = []
    for path in sorted(claims_path.glob("*.md")):
        if path.name.casefold() == "readme.md":
            continue
        documents.append(_parse_claim_document(Path(root), path))
    return documents


def _query_matches(query: str, values: Iterable[Any]) -> bool:
    terms = [term.casefold() for term in re.findall(r"[\w-]+", query, flags=re.UNICODE)]
    if not terms:
        return True
    haystack = "\n".join(str(value) for value in values if value).casefold()
    return all(term in haystack for term in terms)


def _query_score(query: str, values: Iterable[Any]) -> int:
    terms = [term.casefold() for term in re.findall(r"[\w-]+", query, flags=re.UNICODE)]
    if not terms:
        return 0
    haystack = "\n".join(str(value) for value in values if value).casefold()
    return sum(term in haystack for term in terms)


def _query_terms(query: str) -> list[str]:
    return [term.casefold() for term in re.findall(r"[\w-]+", query, flags=re.UNICODE)]


def _evidence_file_path(bundle: Path, relative_path: str) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise WikiError(f"Evidence file escapes its bundle: {relative_path}")
    resolved = (bundle / relative).resolve()
    bundle_resolved = bundle.resolve()
    if resolved != bundle_resolved and bundle_resolved not in resolved.parents:
        raise WikiError(f"Evidence file escapes its bundle: {relative_path}")
    return resolved


def _section_for_line(lines: Sequence[str], line_index: int) -> str:
    heading = ""
    for index in range(min(line_index + 1, len(lines))):
        match = re.match(r"^#{1,6}\s+(.+?)\s*$", lines[index])
        if match:
            heading = match.group(1)
            continue
        latex_match = re.match(
            r"^\\(?:section|subsection|subsubsection)\*?\{(.+?)\}\s*$",
            lines[index],
        )
        if latex_match:
            heading = latex_match.group(1)
    return heading


def evidence_passages(
    root: Path,
    key: str,
    *,
    query: str = "",
    limit: int = 8,
    context_lines: int = 2,
) -> dict[str, Any]:
    """Search declared Markdown companions without converting or mutating PDFs."""

    if limit < 1:
        raise ValueError("limit must be positive")
    if context_lines < 0:
        raise ValueError("context_lines must be non-negative")
    root = Path(root)
    source = source_record(root, key)
    bundle = root / EVIDENCE_DIRNAME / key
    manifest_path = bundle / "manifest.json"
    if not manifest_path.exists():
        raise WikiError(f"Evidence manifest not found: {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WikiError(f"Could not read evidence manifest {manifest_path}: {exc}") from exc
    if not isinstance(manifest, Mapping):
        raise WikiError(f"Evidence manifest is not a JSON object: {manifest_path}")

    warnings: list[str] = []
    file_results: list[dict[str, Any]] = []
    candidates: list[tuple[int, int, str, int, dict[str, Any]]] = []
    terms = _query_terms(query)
    for entry in manifest.get("files", []):
        if not isinstance(entry, Mapping):
            warnings.append(f"Ignored malformed evidence entry in {manifest_path}")
            continue
        relative_path = str(entry.get("path", ""))
        if not relative_path:
            warnings.append(f"Ignored evidence entry without a path in {manifest_path}")
            continue
        file_path = _evidence_file_path(bundle, relative_path)
        searchable = file_path.suffix.casefold() in {".md", ".mmd"}
        file_result: dict[str, Any] = {
            "role": entry.get("role", ""),
            "zotero_attachment_key": entry.get("zotero_attachment_key", ""),
            "source_filename": entry.get("source_filename", ""),
            "path": _display_path(root, file_path),
            "format": entry.get("format", ""),
            "sha256": entry.get("sha256", ""),
            "searchable": searchable,
            "hash_matches": None,
            "passages": [],
        }
        if not file_path.exists():
            warnings.append(f"Evidence companion is missing: {file_path}")
            file_results.append(file_result)
            continue
        if not searchable:
            file_results.append(file_result)
            continue
        try:
            raw = file_path.read_bytes()
            text = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            warnings.append(f"Could not read evidence companion {file_path}: {exc}")
            file_results.append(file_result)
            continue
        expected_hash = str(entry.get("sha256", ""))
        file_result["hash_matches"] = bool(expected_hash) and _sha256(raw) == expected_hash
        if expected_hash and not file_result["hash_matches"]:
            warnings.append(f"Evidence companion hash mismatch: {file_path}")
        if not terms:
            file_results.append(file_result)
            continue
        lines = text.splitlines()
        for line_index in range(len(lines)):
            start = max(0, line_index - context_lines)
            end = min(len(lines), line_index + context_lines + 1)
            snippet_lines = lines[start:end]
            score = _query_score(query, snippet_lines)
            if score == 0:
                continue
            matched_terms = [term for term in terms if term in "\n".join(snippet_lines).casefold()]
            passage = {
                "path": _display_path(root, file_path),
                "role": entry.get("role", ""),
                "zotero_attachment_key": entry.get("zotero_attachment_key", ""),
                "line_start": start + 1,
                "line_end": end,
                "section": _section_for_line(lines, line_index),
                "locator": f"{_display_path(root, file_path)}:L{start + 1}-L{end}",
                "matched_terms": sorted(set(matched_terms)),
                "match_score": score,
                "text": "\n".join(snippet_lines),
            }
            role_priority = 0 if entry.get("role") == "main_article" else 1
            candidates.append(
                (score, role_priority, _display_path(root, file_path), start, passage)
            )
        file_results.append(file_result)

    candidates.sort(key=lambda item: (-item[0], item[1], item[2], item[3]))
    passages: list[dict[str, Any]] = []
    occupied: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for _, _, path, _, passage in candidates:
        interval = (int(passage["line_start"]), int(passage["line_end"]))
        if any(
            interval[0] <= existing_end and existing_start <= interval[1]
            for existing_start, existing_end in occupied[path]
        ):
            continue
        occupied[path].append(interval)
        passages.append(passage)
        if len(passages) >= limit:
            break
    if query and not passages:
        warnings.append("No matching passages were found in the declared Markdown companions")
    if not query:
        warnings.append("No passage query supplied; returning companion inventory only")
    for file_result in file_results:
        file_result["passages"] = [
            passage for passage in passages if passage["path"] == file_result["path"]
        ]
    return {
        "zotero_key": key,
        "citation_key": manifest.get("citation_key", source.get("citation_key", "")),
        "title": source.get("title", ""),
        "doi": manifest.get("doi", source.get("doi", "")),
        "query": query,
        "evidence_path": _display_path(root, bundle),
        "conversion": manifest.get("conversion", {}),
        "files": file_results,
        "passages": passages,
        "warnings": warnings,
    }


def _project_claims(
    claims: Sequence[Mapping[str, Any]],
    *,
    project: str,
    query: str,
    limit: int,
) -> list[dict[str, Any]]:
    ranked: list[tuple[int, Mapping[str, Any]]] = []
    for claim in claims:
        if claim.get("project") != project:
            continue
        score = _query_score(
            query,
            (
                claim.get("claim_id"),
                claim.get("title"),
                claim.get("claim"),
                claim.get("evidence"),
                claim.get("implementation"),
            ),
        )
        if query and score == 0:
            continue
        ranked.append((score, claim))
    ranked.sort(key=lambda pair: (-pair[0], str(pair[1].get("path", ""))))
    return [dict(claim) for _, claim in ranked[:limit]]


def _graph_claim_links(root: Path, path: Path, graph: Mapping[str, Any]) -> list[str]:
    links: list[str] = []
    for node in graph.get("nodes", []):
        if not isinstance(node, Mapping):
            continue
        for link in node.get("links", []):
            if not isinstance(link, Mapping) or link.get("type") != "internal":
                continue
            target = str(link.get("target", ""))
            if not target:
                continue
            try:
                target_path = _resolve_reference(root, target, base=path.parent)
            except WikiError:
                continue
            if target_path.parent.name == CLAIMS_DIRNAME and target_path.suffix == ".md":
                links.append(_display_path(root, target_path))
    return sorted(set(links))


def _graph_documents(
    root: Path,
    *,
    project: str,
    query: str,
    limit: int,
    claims: Sequence[Mapping[str, Any]],
    all_claims: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    graph_path = Path(root) / GRAPH_DIRNAME
    if not graph_path.exists():
        return []
    selected_claim_paths = {str(claim.get("path")) for claim in claims}
    project_claim_paths = {
        str(claim.get("path"))
        for claim in all_claims
        if claim.get("project") == project
    }
    selected = []
    for path in sorted(graph_path.glob("*.nodegraph.json")):
        try:
            graph = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WikiError(f"Could not read graph {path}: {exc}") from exc
        if not isinstance(graph, Mapping):
            raise WikiError(f"Graph is not a JSON object: {path}")
        claim_paths = _graph_claim_links(Path(root), path, graph)
        linked_project_claims = set(claim_paths) & project_claim_paths
        linked_claims = {
            str(claim.get("path")): claim
            for claim in claims
            if str(claim.get("path")) in claim_paths
        }
        graph_values = [
            graph.get("title"),
            graph.get("source"),
            json.dumps(graph.get("nodes", []), ensure_ascii=False),
        ]
        project_linked = bool(linked_project_claims)
        query_match = not query or _query_matches(query, graph_values)
        if not project_linked and not query_match:
            continue
        if query and selected_claim_paths and not linked_claims and not query_match:
            continue
        selected.append(
            {
                "path": _display_path(root, path),
                "title": graph.get("title", path.stem),
                "source": graph.get("source", {}),
                "claim_paths": claim_paths,
                "nodes": graph.get("nodes", []),
                "edges": graph.get("edges", []),
            }
        )
        if len(selected) >= limit:
            break
    return selected


def _evidence_documents(root: Path, claims: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    bundles: list[dict[str, Any]] = []
    seen: set[str] = set()
    for claim in claims:
        key = str(claim.get("zotero_key", ""))
        if not key or key in seen:
            continue
        bundle = Path(root) / EVIDENCE_DIRNAME / key
        if not bundle.exists():
            continue
        seen.add(key)
        files = sorted(
            _display_path(root, file)
            for file in bundle.rglob("*")
            if file.is_file()
        )
        bundles.append(
            {
                "zotero_key": key,
                "path": _display_path(root, bundle),
                "files": files,
            }
        )
    return bundles


def _implementation_documents(claims: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for claim in claims:
        reference = str(claim.get("implementation_ref", "")).strip()
        if not reference:
            continue
        entry = grouped.setdefault(
            reference,
            {
                "ref": reference,
                "claim_ids": [],
                "statuses": [],
            },
        )
        entry["claim_ids"].append(str(claim["claim_id"]))
        status = str(claim.get("implementation_status", "")).strip()
        if status and status not in entry["statuses"]:
            entry["statuses"].append(status)
    return list(grouped.values())


def _open_question_documents(
    claims: Sequence[Mapping[str, Any]],
    graphs: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    for claim in claims:
        if str(claim.get("claim_type", "")).casefold() not in {"open-question", "question", "gap"} and not str(claim.get("status", "")).casefold().startswith("open"):
            continue
        questions.append(
            {
                "kind": "claim",
                "claim_id": claim["claim_id"],
                "title": claim["title"],
                "path": claim["path"],
                "claim": claim["claim"],
                "locator": claim["locator"],
                "confidence": claim["confidence"],
            }
        )
    for graph in graphs:
        for node in graph.get("nodes", []):
            if not isinstance(node, Mapping) or node.get("template") not in {"question", "gap"}:
                continue
            questions.append(
                {
                    "kind": "graph_node",
                    "graph_path": graph["path"],
                    "node_id": node.get("id", ""),
                    "title": node.get("title", ""),
                    "content": node.get("content", ""),
                }
            )
    return questions


def _validate_nodegraph(root: Path, path: Path) -> list[str]:
    """Validate the portable subset of the NodeGraph 1.0 paper-graph contract."""

    errors: list[str] = []
    try:
        graph = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"Invalid NodeGraph JSON {path}: {exc}"]
    if not isinstance(graph, Mapping):
        return [f"NodeGraph is not a JSON object: {path}"]
    if graph.get("version") != "1.0.0":
        errors.append(f"NodeGraph {path} must use version 1.0.0")
    for field in ("title", "created", "modified", "nodes", "edges"):
        if field not in graph:
            errors.append(f"NodeGraph {path} is missing {field}")
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    if not isinstance(nodes, list):
        return errors + [f"NodeGraph {path} nodes must be a list"]
    if not isinstance(edges, list):
        return errors + [f"NodeGraph {path} edges must be a list"]
    node_ids: set[str] = set()
    for node in nodes:
        if not isinstance(node, Mapping):
            errors.append(f"NodeGraph {path} contains a non-object node")
            continue
        node_id = str(node.get("id", ""))
        if not node_id:
            errors.append(f"NodeGraph {path} contains a node without an id")
        elif node_id in node_ids:
            errors.append(f"NodeGraph {path} has duplicate node id {node_id}")
        node_ids.add(node_id)
        for field in ("template", "title", "content", "children", "links", "position"):
            if field not in node:
                errors.append(f"Node {node_id or '<unknown>'} in {path} is missing {field}")
        position = node.get("position", {})
        if not isinstance(position, Mapping) or not isinstance(position.get("x"), (int, float)) or not isinstance(position.get("y"), (int, float)):
            errors.append(f"Node {node_id or '<unknown>'} in {path} has invalid position")
        for child in node.get("children", []) if isinstance(node.get("children", []), list) else []:
            if child not in node_ids and not any(
                isinstance(candidate, Mapping) and candidate.get("id") == child for candidate in nodes
            ):
                errors.append(f"Node {node_id or '<unknown>'} references missing child {child}")
        original = node.get("original")
        if original is not None and (
            not isinstance(original, Mapping)
            or not str(original.get("text", "")).strip()
            or not str(original.get("location", "")).strip()
        ):
            errors.append(f"Node {node_id or '<unknown>'} in {path} has incomplete original evidence")
        for link in node.get("links", []) if isinstance(node.get("links", []), list) else []:
            if not isinstance(link, Mapping):
                errors.append(f"Node {node_id or '<unknown>'} in {path} contains a non-object link")
                continue
            if link.get("type") not in {"pdf", "obsidian", "url", "internal"}:
                errors.append(f"Node {node_id or '<unknown>'} in {path} has an invalid link type")
            if not str(link.get("target", "")).strip():
                errors.append(f"Node {node_id or '<unknown>'} in {path} has an empty link target")
            if link.get("type") == "internal":
                target = str(link.get("target", ""))
                try:
                    target_path = _resolve_reference(root, target, base=path.parent)
                except WikiError as exc:
                    errors.append(f"Node {node_id or '<unknown>'} in {path}: {exc}")
                else:
                    if not target_path.exists():
                        errors.append(f"Node {node_id or '<unknown>'} links to missing file {target}")
    backbone = [
        node
        for node in nodes
        if isinstance(node, Mapping) and node.get("template") == "main_topic"
    ]
    if len(backbone) != 5:
        errors.append(f"NodeGraph {path} must contain exactly five main_topic backbone nodes")
    else:
        ordered = sorted(backbone, key=lambda node: float(node["position"]["y"]))
        if any(float(node["position"]["x"]) != 0 for node in ordered):
            errors.append(f"NodeGraph {path} backbone nodes must be positioned at x=0")
        expected_edges = set(zip((str(node["id"]) for node in ordered), (str(node["id"]) for node in ordered[1:])))
        actual_arrows = {
            (str(edge.get("source", "")), str(edge.get("target", "")))
            for edge in edges
            if isinstance(edge, Mapping) and edge.get("type") == "arrow"
        }
        if not expected_edges.issubset(actual_arrows):
            errors.append(f"NodeGraph {path} is missing a sequential arrow backbone")
    edge_keys: set[tuple[str, str, str]] = set()
    for edge in edges:
        if not isinstance(edge, Mapping):
            errors.append(f"NodeGraph {path} contains a non-object edge")
            continue
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        edge_type = str(edge.get("type", ""))
        if source not in node_ids or target not in node_ids:
            errors.append(f"NodeGraph {path} has an edge with a missing endpoint")
        if edge_type not in {"arrow", "line"}:
            errors.append(f"NodeGraph {path} has an invalid edge type {edge_type}")
        edge_key = (source, target, edge_type)
        if edge_key in edge_keys:
            errors.append(f"NodeGraph {path} has a duplicate edge {source}->{target}")
        edge_keys.add(edge_key)
    return errors


def source_record(root: Path, key: str) -> dict[str, Any]:
    if not key or "/" in key or "\\" in key:
        raise ValueError("source key must be a single Zotero item key")
    path = Path(root) / SOURCE_DIRNAME / key / "record.json"
    if not path.exists():
        raise WikiError(f"Source record not found: {path}")
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WikiError(f"Could not read source record {path}: {exc}") from exc
    if not isinstance(record, dict):
        raise WikiError(f"Source record is not a JSON object: {path}")
    record["wiki"] = _source_wiki_metadata(Path(root), key)
    return record


def _source_wiki_metadata(root: Path, key: str) -> dict[str, Any]:
    """Expose the wiki-side routes for a source without copying source text."""

    brief = _curated_source_metadata(root, "papers").get(key)
    brief_view = None
    if brief is not None:
        brief_view = {
            "path": brief["path"],
            "status": brief["status"],
            "available": bool(brief["path"]),
        }

    bundle = Path(root) / EVIDENCE_DIRNAME / key
    manifest_path = bundle / "manifest.json"
    evidence: dict[str, Any] = {
        "available": False,
        "bundle_path": _display_path(root, bundle),
        "manifest_path": _display_path(root, manifest_path),
        "readme_path": _display_path(root, bundle / "README.md"),
        "file_count": 0,
        "companion_attachment_keys": [],
        "pdf_attachment_keys": [],
        "files": [],
        "conversion": {},
    }
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            manifest = {}
        if isinstance(manifest, Mapping):
            files = manifest.get("files", [])
            if isinstance(files, Sequence) and not isinstance(files, (str, bytes)):
                file_views: list[dict[str, Any]] = []
                companion_keys: list[str] = []
                pdf_keys: list[str] = []
                for item in files:
                    if not isinstance(item, Mapping):
                        continue
                    file_format = str(item.get("format", ""))
                    attachment_key = str(item.get("zotero_attachment_key", ""))
                    searchable = file_format in {"markdown", "mmd", "mathpix-markdown"}
                    if searchable and attachment_key:
                        companion_keys.append(attachment_key)
                    if file_format == "pdf" and attachment_key:
                        pdf_keys.append(attachment_key)
                    file_views.append(
                        {
                            "path": str(item.get("path", "")),
                            "format": file_format,
                            "role": str(item.get("role", "")),
                            "zotero_attachment_key": attachment_key,
                            "searchable": searchable,
                            "sha256": str(item.get("sha256", "")),
                        }
                    )
                evidence.update(
                    {
                        "available": True,
                        "file_count": len(file_views),
                        "companion_attachment_keys": sorted(set(companion_keys)),
                        "pdf_attachment_keys": sorted(set(pdf_keys)),
                        "files": file_views,
                        "conversion": dict(manifest.get("conversion", {}))
                        if isinstance(manifest.get("conversion", {}), Mapping)
                        else {},
                    }
                )
    return {"brief": brief_view, "evidence": evidence}


def freshness_status(root: Path, api: Any | None = None) -> dict[str, Any]:
    """Report local snapshot state and optionally compare it with Zotero."""

    root = Path(root)
    manifest_path = root / MANIFEST_FILENAME
    status: dict[str, Any] = {
        "manifest_path": _display_path(root, manifest_path),
        "materialized_source_count": 0,
        "materialized_item_count": 0,
        "stale": None,
        "refresh_required": False,
        "live_check": {
            "checked": False,
            "available": False,
            "reason": "not_requested",
        },
    }
    if not manifest_path.exists():
        status["live_check"] = {
            "checked": False,
            "available": False,
            "reason": "manifest_missing",
        }
        return status
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        status["live_check"] = {
            "checked": False,
            "available": False,
            "reason": "manifest_unreadable",
        }
        return status
    if isinstance(manifest, Mapping):
        status["materialized_source_count"] = len(manifest.get("records", []))
        status["materialized_item_count"] = int(manifest.get("item_count", 0) or 0)
    if api is None:
        return status
    try:
        comparison = stale_report(root, api)
    except Exception:  # pragma: no cover - local API failures are integration-specific
        status["live_check"] = {
            "checked": False,
            "available": False,
            "reason": "local_zotero_unavailable",
        }
        return status
    status["stale"] = bool(comparison.get("stale", False))
    status["refresh_required"] = status["stale"]
    status["live_check"] = {
        "checked": True,
        "available": True,
        **comparison,
    }
    return status


def context_pack(
    root: Path,
    *,
    project: str,
    query: str = "",
    limit: int = 12,
    registry_root: str | Path | None = None,
    data_root: str | Path | None = None,
    api: Any | None = None,
) -> dict[str, Any]:
    """Return a compact, provenance-linked project context pack for an agent."""

    project_path = Path(root) / PROJECT_DIRNAME / f"{project}.md"
    warnings: list[str] = []
    resolved_registry_root = (
        _registry_root(Path(root), registry_root)
        if registry_root is not None
        else (
            Path(data_root)
            / "domains"
            / "thermophysical"
            / "source"
            / "registry"
            if data_root is not None
            else None
        )
    )
    project_text = ""
    if project_path.exists():
        project_text = project_path.read_text(encoding="utf-8")
    else:
        warnings.append(f"Project scaffold is missing: {project_path}")
    project_sources = search_wiki(
        root,
        query="",
        project=project,
        limit=None if query else limit,
    )
    sources = (
        search_wiki(root, query=query, project=project, limit=limit)
        if query
        else project_sources
    )
    if not sources:
        warnings.append("No source metadata matched project/query; evidence may match independently")
    freshness = freshness_status(Path(root), api=api)
    if freshness["refresh_required"]:
        warnings.append(
            "Materialized Zotero source layer is stale; review freshness before relying on source metadata"
        )
    elif not freshness["live_check"]["checked"]:
        warnings.append("Live Zotero freshness check was not available for this context pack")
    all_claims = _load_claim_documents(Path(root))
    claims = _project_claims(
        all_claims,
        project=project,
        query=query,
        limit=limit,
    )
    if not claims:
        warnings.append("No curated claims matched this project/query")
    graphs = _graph_documents(
        Path(root),
        project=project,
        query=query,
        limit=limit,
        claims=claims,
        all_claims=all_claims,
    )
    if not graphs:
        warnings.append("No NodeGraph artifacts matched this project/query")
    evidence = _evidence_documents(Path(root), claims)
    if not evidence:
        warnings.append("No evidence bundles are linked from the matched claims")
    implementation = _implementation_documents(claims)
    if not implementation:
        warnings.append("No implementation references are linked from the matched claims")
    evidence_scope_sources = list(project_sources if query else sources)
    evidence_scope_sources.extend(source for source in sources if source not in evidence_scope_sources)
    evidence_source_keys = {
        str(source.get("zotero_key", ""))
        for source in evidence_scope_sources
        if source.get("zotero_key")
    }
    evidence_source_keys.update(
        str(claim.get("zotero_key", ""))
        for claim in claims
        if claim.get("zotero_key")
    )
    evidence_source_keys = {key for key in evidence_source_keys if key}
    evidence_coverage_result = evidence_coverage(
        Path(root),
        source_keys=sorted(evidence_source_keys),
    )
    try:
        evidence_hits = search_evidence_chunks(
            Path(root),
            source_keys=sorted(evidence_source_keys),
            query=query,
            limit=limit,
        )
    except WikiError as exc:
        evidence_hits = []
        warnings.append(str(exc))
    evidence_coverage_result["query_hit_count"] = len(evidence_hits)
    if evidence_coverage_result["hash_mismatch_count"]:
        warnings.append(
            "Indexed evidence contains hash mismatches; review evidence freshness before relying on hits"
        )
    if query and not evidence_hits and evidence_coverage_result["index_available"]:
        warnings.append("No indexed evidence chunks matched this context query")
    source_by_key = {
        str(source.get("zotero_key")): source
        for source in project_sources
        if str(source.get("zotero_key", "")).strip()
    }
    evidence_keys = list(dict.fromkeys(str(hit.get("zotero_key", "")) for hit in evidence_hits))
    evidence_sources = [source_by_key[key] for key in evidence_keys if key in source_by_key]
    sources = (evidence_sources + [source for source in sources if source not in evidence_sources])[:limit]
    knowledge_records: list[dict[str, Any]] = []
    try:
        project_manifest = manifest_lookup(Path(root), project)
    except ManifestError:
        project_manifest = None
    if project_manifest is not None:
        allowed_ids = {
            str(record_id)
            for record_id in project_manifest.get("record_ids", [])
            if isinstance(record_id, str)
        }
        candidates = search_records(Path(root), query=query, limit=max(limit, len(allowed_ids), 1) * 4)
        knowledge_records = [
            record for record in candidates if record.get("record_id") in allowed_ids
        ][:limit]
    else:
        knowledge_records = search_records(Path(root), query=query, limit=limit)
    if not knowledge_records:
        warnings.append("No typed knowledge records matched this project/query")
    registry_context: dict[str, Any] = {
        "registry_root": "",
        "query": query,
        "count": 0,
        "total_matches": 0,
        "results": [],
        "warnings": ["No registry root was provided"],
        "read_only": True,
    }
    registry_query = query or ("MEA" if project == "mea-thermodynamics" else "")
    if resolved_registry_root is not None and registry_query:
        try:
            from .scientific_data import search_registry

            registry_context = search_registry(
                resolved_registry_root,
                query=registry_query,
                limit=limit,
            )
        except Exception as exc:  # pragma: no cover - defensive CLI boundary
            registry_context["warnings"] = [f"Registry discovery unavailable: {exc}"]
            warnings.append(registry_context["warnings"][0])
    elif resolved_registry_root is not None:
        registry_context["registry_root"] = str(Path(resolved_registry_root).expanduser().resolve())
        registry_context["warnings"] = ["Registry discovery requires a query"]
    synthesis = []
    synthesis_path = Path(root) / "synthesis"
    if synthesis_path.exists():
        for path in sorted(synthesis_path.glob("*.md")):
            if path.name.casefold() == "readme.md":
                continue
            first_heading = next(
                (line[2:].strip() for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("# ")),
                path.stem,
            )
            synthesis.append({"title": first_heading, "path": _display_path(Path(root), path)})
    return {
        "project": project,
        "project_path": str(project_path),
        "project_context": project_text,
        "query": query,
        "sources": sources,
        "freshness": freshness,
        "claims": claims,
        "graphs": graphs,
        "evidence": evidence,
        "evidence_hits": evidence_hits,
        "evidence_coverage": evidence_coverage_result,
        "data": registry_context,
        "implementation": implementation,
        "knowledge_records": knowledge_records,
        "synthesis": synthesis[:limit],
        "open_questions": _open_question_documents(claims, graphs),
        "warnings": warnings,
        "authority_rule": "Treat Zotero records as sources and claims as derived until independently curated.",
    }


def verify_wiki(root: Path = Path("wiki")) -> dict[str, Any]:
    """Check generated records, manifest hashes, catalog, index, and claims."""

    root = Path(root)
    errors: list[str] = []
    warnings: list[str] = []
    manifest_path = root / MANIFEST_FILENAME
    catalog_path = root / CATALOG_FILENAME
    if not manifest_path.exists():
        errors.append(f"Missing {manifest_path}")
        return {"ok": False, "errors": errors, "warnings": warnings}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"Invalid manifest {manifest_path}: {exc}")
        return {"ok": False, "errors": errors, "warnings": warnings}
    if not catalog_path.exists():
        errors.append(f"Missing {catalog_path}")
    manifest_keys: set[str] = set()
    for entry in manifest.get("records", []):
        key = str(entry.get("zotero_key", ""))
        manifest_keys.add(key)
        record_path = root / str(entry.get("record_path", ""))
        markdown_path = record_path.parent / "source.md"
        if not record_path.exists():
            errors.append(f"Missing source record: {record_path}")
            continue
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"Invalid source record {record_path}: {exc}")
            continue
        if record.get("zotero_key") != key:
            errors.append(f"Key mismatch in {record_path}")
        if _sha256(_stable_json(record)) != entry.get("content_sha256"):
            errors.append(f"Manifest hash mismatch: {record_path}")
        if not markdown_path.exists():
            errors.append(f"Missing generated Markdown: {markdown_path}")
    for record_path in sorted((root / SOURCE_DIRNAME).glob("*/record.json")):
        key = record_path.parent.name
        if key not in manifest_keys:
            warnings.append(f"Orphaned source record not in manifest: {record_path}")
    index_path = root / INDEX_FILENAME
    if not index_path.exists():
        warnings.append(f"Search index missing: {index_path}")
    triage_path = root / TRIAGE_FILENAME
    triage: Mapping[str, Any] = {}
    if not triage_path.exists():
        warnings.append(f"Triage index missing: {triage_path}")
    else:
        try:
            loaded_triage = json.loads(triage_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"Invalid triage index {triage_path}: {exc}")
        else:
            if not isinstance(loaded_triage, Mapping):
                errors.append(f"Triage index is not a JSON object: {triage_path}")
            else:
                triage = loaded_triage
                if int(triage.get("source_count", 0) or 0) != len(manifest.get("records", [])):
                    errors.append(
                        f"Triage source count does not match manifest: {triage_path}"
                    )
                if int(triage.get("schema_version", 0) or 0) != TRIAGE_SCHEMA_VERSION:
                    errors.append(
                        f"Unsupported triage schema version in {triage_path}; "
                        f"expected {TRIAGE_SCHEMA_VERSION}"
                    )
    classification_path = _classification_path(root)
    try:
        classification = _load_classification_config(root)
    except WikiError as exc:
        errors.append(str(exc))
    else:
        assignment_orphans = sorted(
            set(classification["assignments"]) - manifest_keys
        )
        if assignment_orphans:
            warnings.append(
                "Classification assignments reference sources not present in the current manifest: "
                + ", ".join(assignment_orphans)
            )
        if classification_path.exists() and not triage_path.exists():
            warnings.append(f"Classification layer is present but triage is missing: {classification_path}")
    claims_path = root / CLAIMS_DIRNAME
    uncited_claims: list[str] = []
    parsed_claims: list[dict[str, Any]] = []
    if claims_path.exists():
        for claim_path in sorted(claims_path.glob("*.md")):
            if claim_path.name.casefold() == "readme.md":
                continue
            try:
                claim = _parse_claim_document(root, claim_path)
            except WikiError as exc:
                errors.append(str(exc))
                uncited_claims.append(str(claim_path))
                continue
            parsed_claims.append(claim)
            try:
                derived_path = _resolve_reference(root, str(claim["derived_from"]))
            except WikiError as exc:
                errors.append(f"Claim {claim_path}: {exc}")
            else:
                if not derived_path.exists():
                    errors.append(f"Claim {claim_path} references missing evidence {claim['derived_from']}")
            if str(claim["zotero_key"]) not in manifest_keys:
                warnings.append(
                    f"Claim {claim_path} cites Zotero key not present in current manifest: {claim['zotero_key']}"
                )
    graph_path = root / GRAPH_DIRNAME
    graph_count = 0
    if graph_path.exists():
        graph_files = sorted(graph_path.glob("*.nodegraph.json"))
        graph_count = len(graph_files)
        for graph_file in graph_files:
            errors.extend(_validate_nodegraph(root, graph_file))
    record_lint = lint_records(root)
    errors.extend(f"Typed record: {error}" for error in record_lint["errors"])
    warnings.extend(f"Typed record: {warning}" for warning in record_lint["warnings"])
    manifest_lint = lint_manifests(root)
    errors.extend(f"Project manifest: {error}" for error in manifest_lint["errors"])
    warnings.extend(f"Project manifest: {warning}" for warning in manifest_lint["warnings"])
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "source_count": len(manifest.get("records", [])),
        "uncited_claim_count": len(uncited_claims),
        "claim_count": len(parsed_claims),
        "graph_count": graph_count,
        "triage_source_count": int(triage.get("source_count", 0) or 0),
        "evidence_chunk_count": int(triage.get("evidence_chunk_count", 0) or 0),
        "record_count": record_lint["record_count"],
        "relation_count": record_lint["relation_count"],
        "typed_record_lint": record_lint,
        "manifest_lint": manifest_lint,
    }


def stale_report(root: Path, api: Any) -> dict[str, Any]:
    """Compare materialized Zotero versions with a fresh read-only snapshot."""

    manifest_path = Path(root) / MANIFEST_FILENAME
    if not manifest_path.exists():
        raise WikiError(f"Missing {manifest_path}; run sync --apply first")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    previous = {
        str(entry.get("zotero_key")): str(entry.get("version", ""))
        for entry in manifest.get("records", [])
        if isinstance(entry, Mapping)
    }
    try:
        current_items = api.items(top_level=True)
    except TypeError:
        current_items = api.items()
    current = {
        _key(item): str(item.get("version", _data(item).get("version", "")))
        for item in current_items
        if _key(item)
        and _data(item).get("itemType") != "attachment"
        and not _data(item).get("parentItem")
    }
    changed = sorted(key for key in current.keys() & previous.keys() if current[key] != previous[key])
    added = sorted(set(current) - set(previous))
    removed = sorted(set(previous) - set(current))
    result = {
        "stale": bool(changed or added or removed),
        "changed": changed,
        "added": added,
        "removed": removed,
        "current_sources": len(current),
        "materialized_sources": len(previous),
    }
    from .health import health_report

    health = health_report(
        Path(root),
        stale_source_keys=[*changed, *removed],
    )
    result["curated_review_queue"] = health["review_queue"]
    result["curated_review_queue_total"] = health["review_queue_total"]
    result["dependency_health_ok"] = health["ok"]
    return result


__all__ = [
    "CATALOG_FILENAME",
    "CLAIMS_DIRNAME",
    "ASSIGNMENTS_FILENAME",
    "CURATION_DIRNAME",
    "EVIDENCE_DIRNAME",
    "GRAPH_DIRNAME",
    "INDEX_FILENAME",
    "INDEX_SCHEMA_VERSION",
    "MANIFEST_FILENAME",
    "SOURCE_DIRNAME",
    "TRIAGE_FILENAME",
    "TRIAGE_SCHEMA_VERSION",
    "WikiError",
    "WikiSnapshot",
    "build_source_records",
    "classify_source",
    "context_pack",
    "evidence_coverage",
    "evidence_passages",
    "freshness_status",
    "index_wiki",
    "materialize_snapshot",
    "search_evidence_chunks",
    "search_wiki",
    "source_record",
    "stale_report",
    "triage_wiki",
    "verify_wiki",
]
