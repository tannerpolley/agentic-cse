"""LinkML validation and read-only access to scientific data."""

from __future__ import annotations

import csv
from contextlib import contextmanager
from datetime import date, datetime, time
from decimal import Decimal
import hashlib
from importlib.resources import as_file, files
import json
from pathlib import Path
import re
from collections.abc import Iterator, Mapping
from typing import Any

import duckdb
from linkml.validator import validate_file
from linkml_runtime.utils.schemaview import SchemaView


class ScientificDataError(ValueError):
    """Raised when scientific data cannot be validated or queried."""


_QUERY_ALIASES = {
    "mea": ("monoethanolamine",),
    "mono ethanolamine": ("monoethanolamine",),
    "co2": ("carbon dioxide", "carbon-dioxide"),
    "carbon dioxide": ("carbon-dioxide",),
    "density": ("mass density", "liquid density"),
    "viscosity": ("dynamic viscosity",),
}


@contextmanager
def _linkml_schema(schema_path: Path | None) -> Iterator[tuple[Path, str]]:
    if schema_path is not None:
        path = Path(schema_path)
        yield path, str(path)
        return

    resource = files("zotero_companion").joinpath("schemas/linkml/companion.yaml")
    with as_file(resource) as path:
        yield path, "zotero_companion/schemas/linkml/companion.yaml"


def _normalise_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).casefold()).strip()


def _query_terms(query: str) -> list[tuple[str, tuple[str, ...]]]:
    """Return searchable terms and their retained-data aliases."""

    normalised = _normalise_text(query)
    terms = re.findall(r"[a-z0-9]+", normalised)
    result: list[tuple[str, tuple[str, ...]]] = []
    for term in terms:
        aliases = _QUERY_ALIASES.get(term, ())
        result.append((term, tuple(_normalise_text(alias) for alias in aliases)))
    return result


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative_path(root: Path, value: str) -> Path:
    candidate = (root / value).resolve()
    if candidate != root and root not in candidate.parents:
        raise ScientificDataError(f"Registry path escapes registry root: {value}")
    return candidate


def _read_inventory(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as stream:
            return [dict(row) for row in csv.DictReader(stream)]
    except (OSError, csv.Error) as exc:
        raise ScientificDataError(f"Could not read registry inventory {path}: {exc}") from exc


def _source_metadata(row: Mapping[str, Any]) -> dict[str, Any]:
    value = row.get("source", "")
    if isinstance(value, Mapping):
        return dict(value)
    if not str(value).strip():
        return {}
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return {"description": str(value)}
    return dict(parsed) if isinstance(parsed, Mapping) else {"description": str(value)}


def _units_in_table(path: Path) -> dict[str, Any]:
    """Read only the header and first row to expose source-reported units."""

    empty = {"unit_columns": [], "sampled_unit_values": {}}

    if path.suffix.casefold() != ".csv" or not path.is_file():
        return empty
    try:
        with path.open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            row = next(reader, None)
    except (OSError, csv.Error, UnicodeError):
        return empty
    if not row:
        return {
            "unit_columns": [
                str(key) for key in reader.fieldnames or [] if "unit" in str(key).casefold()
            ],
            "sampled_unit_values": {},
        }
    unit_columns = [
        str(key) for key in reader.fieldnames or [] if "unit" in str(key).casefold()
    ]
    return {
        "unit_columns": unit_columns,
        "sampled_unit_values": {
            key: str(row.get(key, "")).strip()
            for key in unit_columns
            if str(row.get(key, "")).strip()
        },
    }


def _resource_packet(
    registry_root: Path,
    metadata_path: Path,
    resource: Mapping[str, Any],
    expected_hash: str = "",
) -> dict[str, Any]:
    relative = str(resource.get("path", "")).strip()
    empty_units = {"unit_columns": [], "sampled_unit_values": {}}
    candidate = (metadata_path.parent / relative).resolve()
    inside_root = candidate == registry_root or registry_root in candidate.parents
    exists = inside_root and candidate.is_file()
    actual_hash = _sha256(candidate) if exists else ""
    declared_hash = str(resource.get("sha256", "")).strip()
    expected_hash = expected_hash or declared_hash
    hash_matches = None if not expected_hash or not exists else actual_hash == expected_hash
    errors: list[str] = []
    if not relative:
        errors.append("resource path is missing")
    elif not inside_root:
        errors.append("resource path escapes registry root")
    elif not exists:
        errors.append("resource file is missing")
    elif hash_matches is False:
        errors.append("resource SHA-256 does not match its declaration")
    elif hash_matches is None:
        errors.append("resource SHA-256 is unchecked; expected hash is missing")
    if declared_hash and expected_hash != declared_hash:
        errors.append("resource and inventory SHA-256 declarations disagree")
    return {
        "path": str(candidate),
        "relative_path": str(candidate.relative_to(registry_root)) if inside_root else relative,
        "format": str(resource.get("format", "")),
        "role": str(resource.get("role", "")),
        "row_count": resource.get("row_count"),
        "required_columns": list(resource.get("required_columns", [])),
        "numeric_columns": list(resource.get("numeric_columns", [])),
        "composition_groups": list(resource.get("composition_groups", [])),
        "exists": exists,
        "sha256": actual_hash,
        "declared_sha256": expected_hash,
        "hash_source": (
            "normalized/source-files.csv" if expected_hash and expected_hash != declared_hash
            else "resource-metadata" if declared_hash
            else "unchecked"
        ),
        "hash_matches": hash_matches,
        "units_in_table": _units_in_table(candidate) if exists else empty_units,
        "errors": errors,
    }


def search_registry(
    registry_root: Path,
    *,
    query: str = "",
    limit: int = 20,
) -> dict[str, Any]:
    """Find retained registry packages and resolve their source resources.

    This searches the canonical normalized inventory instead of creating a
    second index or discovering arbitrary files.  Raw files remain data owned
    by the registry; this result is only a read-only packet for callers that
    need to decide what to inspect.
    """

    if limit < 1:
        raise ValueError("limit must be positive")
    root = Path(registry_root).expanduser().resolve()
    if not root.is_dir():
        raise ScientificDataError(f"Registry root does not exist: {root}")
    terms = _query_terms(query)
    warnings: list[str] = []
    inventory_path = root.parent.parent / "normalized" / "registry-records.csv"
    source_files_path = root.parent.parent / "normalized" / "source-files.csv"
    if not inventory_path.is_file():
        raise ScientificDataError(
            f"Normalized registry inventory is missing: {inventory_path}"
        )
    inventory = _read_inventory(inventory_path)
    source_files = (
        {
            str(row.get("source_path", "")).strip(): str(row.get("sha256", "")).strip()
            for row in _read_inventory(source_files_path)
            if str(row.get("source_path", "")).strip()
        }
        if source_files_path.is_file()
        else {}
    )
    if not source_files_path.is_file():
        warnings.append(f"Resource hashes are unchecked; inventory is missing: {source_files_path}")
    packages: list[tuple[int, Path, dict[str, Any], dict[str, str]]] = []
    for inventory_row in inventory:
        relative_metadata = str(inventory_row.get("source_path", "")).strip()
        if not relative_metadata or "/raw/" in f"/{relative_metadata}/":
            continue
        try:
            metadata_path = _relative_path(root, relative_metadata)
        except ScientificDataError as exc:
            warnings.append(str(exc))
            continue
        try:
            value = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            warnings.append(f"Could not read registry metadata {metadata_path}: {exc}")
            continue
        if not isinstance(value, Mapping) or "resources" not in value:
            continue
        metadata = dict(value)
        searchable = _normalise_text(json.dumps({**inventory_row, **metadata}, ensure_ascii=False))
        if terms:
            score = 0
            for term, aliases in terms:
                options = (term, *aliases)
                matches = sum(
                    len(re.findall(r"(?<!\w)" + re.escape(option) + r"(?!\w)", searchable))
                    for option in options
                )
                if not matches:
                    break
                score += matches
            else:
                packages.append((score, metadata_path, metadata, inventory_row))
        else:
            packages.append((0, metadata_path, metadata, inventory_row))
    packages.sort(key=lambda item: (-item[0], item[1].as_posix()))

    results: list[dict[str, Any]] = []
    for score, metadata_path, metadata, inventory_row in packages[:limit]:
        metadata_relative = str(metadata_path.relative_to(root))
        metadata_actual_hash = _sha256(metadata_path)
        metadata_expected_hash = str(inventory_row.get("sha256", "")).strip()
        metadata_hash_matches = (
            None
            if not metadata_expected_hash
            else metadata_actual_hash == metadata_expected_hash
        )
        resources = []
        resource_errors: list[str] = []
        declared_resources = metadata.get("resources")
        if not isinstance(declared_resources, list) or not declared_resources:
            resource_errors.append("resources must be a nonempty array")
            declared_resources = []
        for resource in declared_resources:
            if not isinstance(resource, Mapping):
                resource_errors.append("each resource must be an object")
                continue
            candidate = (metadata_path.parent / str(resource.get("path", ""))).resolve()
            resource_relative = (
                str(candidate.relative_to(root))
                if candidate == root or root in candidate.parents
                else ""
            )
            resources.append(
                _resource_packet(
                    root,
                    metadata_path,
                    resource,
                    expected_hash=source_files.get(resource_relative, ""),
                )
            )
        integrity_errors = resource_errors + [
            f"{resource['relative_path']}: {error}"
            for resource in resources
            for error in resource["errors"]
        ]
        if metadata_hash_matches is False:
            integrity_errors.insert(0, "metadata SHA-256 does not match normalized registry inventory")
        elif metadata_hash_matches is None:
            integrity_errors.insert(0, "metadata SHA-256 is unchecked; expected hash is missing")
        verified = bool(
            not integrity_errors
            and resources
            and metadata_hash_matches is True
            and all(resource["hash_matches"] is True for resource in resources)
        )
        record_id = next(
            (
                str(metadata.get(field, ""))
                for field in (
                    "dataset_id",
                    "parameter_set_id",
                    "correlation_id",
                    "reaction_constant_id",
                    "observation_id",
                )
                if str(metadata.get(field, "")).strip()
            ),
            "",
        )
        packet = {
            "record_id": record_id,
            "record_type": str(metadata.get("record_type", "")),
            "title": str(metadata.get("title", "")),
            "metadata_path": str(metadata_path),
            "metadata_relative_path": metadata_relative,
            "metadata_sha256": metadata_actual_hash,
            "declared_metadata_sha256": metadata_expected_hash,
            "metadata_hash_matches": metadata_hash_matches,
            "version": str(metadata.get("version", "")),
            "system": metadata.get("system", {}),
            "components": list(metadata.get("components", [])),
            "property": str(metadata.get("property", "")),
            "quality_state": str(metadata.get("quality_state", "")),
            "units": metadata.get("units", metadata.get("unit", ""))
            or "see per-resource unit columns",
            "composition_basis": metadata.get(
                "composition_basis", metadata.get("basis", "")
            ),
            "conditions": metadata.get("conditions", {}),
            "provenance": metadata.get("source")
            or metadata.get("provenance")
            or _source_metadata(inventory_row),
            "known_issues": list(metadata.get("known_issues", [])),
            "notes": str(metadata.get("notes", "")),
            "resources": resources,
            "integrity": {
                "ok": verified,
                "verified": verified,
                "errors": integrity_errors,
                "metadata_hash_checked": metadata_hash_matches is not None,
                "metadata_hash_unchecked": metadata_hash_matches is None,
                "metadata_hash_mismatch": metadata_hash_matches is False,
                "resource_hash_unchecked": any(
                    resource["hash_matches"] is None for resource in resources
                ),
            },
            "match_score": score,
        }
        results.append(packet)
    return {
        "registry_root": str(root),
        "inventory_path": str(inventory_path),
        "scope": "canonical packages with resources; zero matches does not exclude review candidates",
        "candidate_inventories": [
            str(path) for path in (
                root.parent.parent / "normalized/source-ready-candidates.csv",
                root.parent.parent / "quarantine/source-blocked-candidates.csv",
            ) if path.is_file()
        ],
        "query": query,
        "count": len(results),
        "total_matches": len(packages),
        "results": results,
        "warnings": warnings,
        "read_only": True,
    }


def validate_catalog(
    data_path: Path,
    schema_path: Path | None = None,
    target_class: str = "CompanionCatalog",
) -> dict[str, Any]:
    """Validate one YAML, JSON, CSV, or TSV file against a LinkML class."""

    data_path = Path(data_path)
    if not data_path.is_file():
        raise ScientificDataError(f"Data file does not exist: {data_path}")
    with _linkml_schema(schema_path) as (resolved_schema, schema_label):
        if not resolved_schema.is_file():
            raise ScientificDataError(f"LinkML schema does not exist: {resolved_schema}")
        schema = SchemaView(
            resolved_schema.resolve(),
            base_dir=str(resolved_schema.resolve().parent),
            merge_imports=True,
        ).schema
        report = validate_file(data_path, schema, target_class)
    results = [str(result) for result in report.results]
    return {
        "ok": not results,
        "data": str(data_path),
        "schema": schema_label,
        "target_class": target_class,
        "errors": results,
    }


def query_table(table: Path, sql: str, limit: int = 100) -> dict[str, Any]:
    """Run a bounded read-only query against CSV, Parquet, or JSON data."""

    table = Path(table).resolve()
    if not table.is_file():
        raise ScientificDataError(f"Table does not exist: {table}")
    statement = sql.strip()
    if not statement.casefold().startswith(("select ", "with ")) or ";" in statement:
        raise ScientificDataError("Only one SELECT or WITH query is allowed")
    if limit < 1 or limit > 10_000:
        raise ScientificDataError("limit must be between 1 and 10000")

    suffix = table.suffix.casefold()
    if suffix not in {".csv", ".parquet", ".json", ".jsonl"}:
        raise ScientificDataError(f"Unsupported table type: {suffix}")

    connection = duckdb.connect(":memory:")
    try:
        if suffix == ".csv":
            relation = connection.read_csv(str(table))
        elif suffix == ".parquet":
            relation = connection.from_parquet(str(table))
        else:
            relation = connection.read_json(str(table))
        relation.create("records")
        connection.execute("SET enable_external_access = false")
        connection.execute("SET lock_configuration = true")
        cursor = connection.execute(f"SELECT * FROM ({statement}) AS result LIMIT ?", [limit])
        columns = [item[0] for item in cursor.description]
        rows = [
            dict(zip(columns, (_json_value(value) for value in values), strict=True))
            for values in cursor.fetchall()
        ]
    except duckdb.Error as exc:
        raise ScientificDataError(f"DuckDB query failed: {exc}") from exc
    finally:
        connection.close()
    return {"table": str(table), "sql": statement, "rows": rows, "count": len(rows)}


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date | datetime | time):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    return value


__all__ = [
    "ScientificDataError",
    "query_table",
    "search_registry",
    "validate_catalog",
]
