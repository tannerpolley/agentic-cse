"""LinkML validation and read-only access to scientific data."""

from __future__ import annotations

import csv
from contextlib import contextmanager
from datetime import date, datetime, time
from decimal import Decimal
import hashlib
from importlib.resources import as_file, files
import json
import os
from pathlib import Path
import re
import tempfile
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
_IDENTITY_FIELDS = (
    "dataset_id",
    "parameter_set_id",
    "correlation_id",
    "reaction_constant_id",
    "observation_id",
    "package_id",
    "record_id",
)
_DATA_RECORD_TYPES = {"dataset", "observation"}
_MODEL_RECORD_TYPES = {"parameter_set", "parameter-set", "correlation", "reaction_constant"}
_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


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
    raw = Path(str(value)).expanduser()
    candidate = raw.resolve() if raw.is_absolute() else (root / raw).resolve()
    if raw.is_absolute():
        return candidate
    if candidate != root and root not in candidate.parents:
        raise ScientificDataError(f"Registry path escapes registry root: {value}")
    return candidate


def _read_inventory(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as stream:
            return [dict(row) for row in csv.DictReader(stream)]
    except (OSError, csv.Error) as exc:
        raise ScientificDataError(f"Could not read registry inventory {path}: {exc}") from exc


def _read_inventory_table(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.is_file():
        return [], []
    try:
        with path.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            fields = list(reader.fieldnames or [])
            return [dict(row) for row in reader], fields
    except (OSError, csv.Error) as exc:
        raise ScientificDataError(f"Could not read registry inventory {path}: {exc}") from exc


def _within(root: Path, value: Path) -> bool:
    return value == root or root in value.parents


def _inventory_path(root: Path, value: str) -> Path:
    raw = Path(str(value)).expanduser()
    return (raw if raw.is_absolute() else root / raw).resolve()


def _stored_path(root: Path, value: Path) -> str:
    value = value.resolve()
    return value.relative_to(root).as_posix() if _within(root, value) else str(value)


def _identity(metadata: Mapping[str, Any]) -> tuple[str, str]:
    populated = [
        (field, str(metadata.get(field, "")).strip())
        for field in _IDENTITY_FIELDS
        if str(metadata.get(field, "")).strip()
    ]
    if not populated:
        raise ScientificDataError(
            "Package metadata must declare one stable identity field: "
            + ", ".join(_IDENTITY_FIELDS)
        )
    if len({value for _field, value in populated}) > 1:
        raise ScientificDataError("Package metadata declares conflicting identity values")
    return populated[0]


def _source_identity(value: Any) -> tuple[tuple[str, str], ...]:
    source = value if isinstance(value, Mapping) else {}
    return tuple(
        (field, str(source[field]).strip())
        for field in (
            "zotero_key",
            "attachment_key",
            "citation_key",
            "doi",
            "source_item_id",
            "source_attachment_id",
            "repository",
            "path",
        )
        if str(source.get(field, "")).strip()
    )


def _package_metadata_path(package: Path) -> Path:
    package = Path(package).expanduser().resolve()
    if package.is_file():
        return package
    if not package.is_dir():
        raise ScientificDataError(f"Package path does not exist: {package}")
    candidates = sorted(
        path
        for path in package.glob("*.json")
        if path.is_file() and path.name.casefold() != "readme.json"
    )
    preferred = [
        path for path in candidates
        if path.name.casefold() in {
            "dataset.json",
            "observation.json",
            "parameter-set.json",
            "parameter_set.json",
            "correlation.json",
            "reaction-constant.json",
            "package.json",
            "metadata.json",
        }
    ]
    if len(preferred) == 1:
        return preferred[0]
    if preferred:
        candidates = preferred
    if len(candidates) != 1:
        detail = "no metadata JSON found" if not candidates else "multiple metadata JSON files found"
        raise ScientificDataError(f"Package directory must contain exactly one metadata JSON: {detail}")
    return candidates[0]


def _infer_registry_root(metadata_path: Path) -> Path:
    for ancestor in (metadata_path.parent, *metadata_path.parents):
        if ancestor.name == "registry":
            return ancestor
        if (ancestor.parent.parent / "normalized").is_dir():
            return ancestor
    try:
        from .config import load_config

        config = load_config()
    except (OSError, RuntimeError, ValueError):
        config = None
    if config is not None:
        return config.data_root / "domains" / "thermophysical" / "source" / "registry"
    raise ScientificDataError(
        "Cannot infer the registry root; pass --registry-root for a package outside source/registry"
    )


def _resource_rows(
    metadata_path: Path,
    metadata: Mapping[str, Any],
    registry_root: Path,
) -> list[dict[str, Any]]:
    declared = metadata.get("resources")
    if not isinstance(declared, list) or not declared:
        raise ScientificDataError("Package metadata resources must be a nonempty array")
    rows: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for index, resource in enumerate(declared):
        if not isinstance(resource, Mapping):
            raise ScientificDataError(f"resources[{index}] must be an object")
        raw_path = str(resource.get("path", "")).strip()
        if not raw_path:
            raise ScientificDataError(f"resources[{index}] path is missing")
        raw = Path(raw_path).expanduser()
        candidate = (raw if raw.is_absolute() else metadata_path.parent / raw).resolve()
        if candidate in seen:
            raise ScientificDataError(f"resources[{index}] duplicates resource path {raw_path}")
        seen.add(candidate)
        if not candidate.is_file():
            raise ScientificDataError(f"resource file does not exist: {raw_path}")
        if (
            _within(registry_root, metadata_path)
            and not raw.is_absolute()
            and not _within(registry_root, candidate)
        ):
            raise ScientificDataError(
                f"resource path escapes registry root; use an absolute path for an explicit external link: {raw_path}"
            )
        if (
            not _within(registry_root, metadata_path)
            and not raw.is_absolute()
            and not _within(metadata_path.parent, candidate)
        ):
            raise ScientificDataError(
                f"resource path escapes the package directory; use an absolute path for an explicit external link: {raw_path}"
            )
        actual_hash = _sha256(candidate)
        declared_hash = str(resource.get("sha256", "")).strip()
        if declared_hash and not _SHA256_PATTERN.fullmatch(declared_hash):
            raise ScientificDataError(f"resource SHA-256 is invalid: {raw_path}")
        if declared_hash and declared_hash.casefold() != actual_hash:
            raise ScientificDataError(f"resource SHA-256 does not match its declaration: {raw_path}")
        rows.append(
            {
                "metadata_path": raw_path,
                "path": candidate,
                "stored_path": _stored_path(registry_root, candidate),
                "sha256": actual_hash,
                "bytes": candidate.stat().st_size,
                "rows": _row_count(candidate),
            }
        )
    return rows


def _row_count(path: Path) -> int | None:
    if path.suffix.casefold() != ".csv":
        return None
    try:
        with path.open(newline="", encoding="utf-8-sig") as stream:
            return max(sum(1 for _ in csv.reader(stream)) - 1, 0)
    except (OSError, UnicodeDecodeError, csv.Error):
        return None


def _has_value(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(_has_value(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_has_value(item) for item in value)
    return bool(str(value).strip())


def _registration_metadata_errors(
    record_type: str,
    metadata: Mapping[str, Any],
    resource_rows: list[dict[str, Any]],
) -> list[str]:
    if record_type not in _DATA_RECORD_TYPES and record_type not in _MODEL_RECORD_TYPES:
        return []
    errors: list[str] = []
    source = metadata.get("source", metadata.get("provenance", {}))
    if not _source_identity(source):
        errors.append(f"{record_type} package needs source provenance identity")
    if not isinstance(source, Mapping) or not _has_value(
        source.get("locator", source.get("locators", source.get("exact_locators", "")))
    ):
        errors.append(f"{record_type} package needs an exact source locator")
    review = metadata.get(
        "quality_state",
        metadata.get("scientific_review", metadata.get("review", "")),
    )
    if not _has_value(review):
        errors.append(f"{record_type} package needs scientific review status")
    if record_type in _MODEL_RECORD_TYPES and not _has_value(
        metadata.get("model", metadata.get("reference_state", ""))
    ):
        errors.append(f"{record_type} package needs model or reference-state conventions")
    units = metadata.get("units", metadata.get("unit", ""))
    table_units = any(
        bool(_units_in_table(row["path"])["sampled_unit_values"])
        for row in resource_rows
    )
    if not _has_value(units) and not table_units:
        errors.append(f"{record_type} package needs units in metadata or resource columns")
    uncertainty = metadata.get("uncertainty", metadata.get("uncertainty_interpretation", ""))
    if not _has_value(uncertainty):
        errors.append(
            f"{record_type} package needs uncertainty or an interpretation of missing uncertainty"
        )
    return errors


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
    *,
    allow_external: bool = False,
) -> dict[str, Any]:
    relative = str(resource.get("path", "")).strip()
    empty_units = {"unit_columns": [], "sampled_unit_values": {}}
    raw = Path(relative).expanduser()
    candidate = (raw if raw.is_absolute() else metadata_path.parent / raw).resolve()
    inside_root = _within(registry_root, candidate)
    metadata_external = not _within(registry_root, metadata_path)
    linked_external = allow_external and (
        raw.is_absolute() or _within(metadata_path.parent, candidate)
    )
    in_scope = inside_root or linked_external
    exists = in_scope and candidate.is_file()
    actual_hash = _sha256(candidate) if exists else ""
    declared_hash = str(resource.get("sha256", "")).strip()
    expected_hash = expected_hash or declared_hash
    hash_matches = (
        None
        if not expected_hash or not exists
        else actual_hash.casefold() == expected_hash.casefold()
    )
    errors: list[str] = []
    if not relative:
        errors.append("resource path is missing")
    elif not in_scope:
        errors.append("resource path escapes registry root")
    elif not exists:
        errors.append("resource file is missing")
    elif hash_matches is False:
        errors.append("resource SHA-256 does not match its declaration")
    elif hash_matches is None:
        errors.append("resource SHA-256 is unchecked; expected hash is missing")
    if declared_hash and expected_hash.casefold() != declared_hash.casefold():
        errors.append("resource and inventory SHA-256 declarations disagree")
    return {
        "path": str(candidate),
        "relative_path": str(candidate.relative_to(registry_root)) if inside_root else str(candidate),
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
        metadata_relative = _stored_path(root, metadata_path)
        metadata_actual_hash = _sha256(metadata_path)
        metadata_expected_hash = str(inventory_row.get("sha256", "")).strip()
        metadata_hash_matches = (
            None
            if not metadata_expected_hash
            else metadata_actual_hash.casefold() == metadata_expected_hash.casefold()
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
                else str(candidate)
            )
            resources.append(
                _resource_packet(
                    root,
                    metadata_path,
                    resource,
                    expected_hash=source_files.get(resource_relative, ""),
                    allow_external=(
                        not _within(root, metadata_path)
                        or Path(str(resource.get("path", ""))).expanduser().is_absolute()
                    ),
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
                    "package_id",
                    "record_id",
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
            "data_authority": str(
                metadata.get("data_authority", metadata.get("ownership", "shared"))
            ),
            "supersedes": str(inventory_row.get("supersedes", "")).strip(),
            "amount_basis": metadata.get("amount_basis", ""),
            "quantities": metadata.get("quantities", metadata.get("quantity", [])),
            "uncertainty": metadata.get("uncertainty", {}),
            "transformations": metadata.get("transformations", metadata.get("transformation", [])),
            "model": metadata.get("model", ""),
            "reference_state": metadata.get("reference_state", ""),
            "review": metadata.get("review", metadata.get("scientific_review", {})),
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


def _read_package_metadata(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ScientificDataError(f"Could not read package metadata {path}: {exc}") from exc
    if not isinstance(value, Mapping):
        raise ScientificDataError("Package metadata must be a JSON object")
    return dict(value)


def _write_inventory_table(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> Path:
    handle = tempfile.NamedTemporaryFile(
        mode="w", newline="", encoding="utf-8", dir=path.parent,
        prefix=f".{path.name}.", suffix=".tmp", delete=False,
    )
    temporary = Path(handle.name)
    try:
        with handle:
            writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows({field: row.get(field, "") for field in fields} for row in rows)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return temporary


def _replace_inventory_tables(updates: list[tuple[Path, list[str], list[dict[str, Any]]]]) -> None:
    originals = {
        path: path.read_bytes() if path.exists() else None
        for path, _fields, _rows in updates
    }
    temporary_paths: list[Path] = []
    replaced: list[Path] = []
    try:
        for path, fields, rows in updates:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = _write_inventory_table(path, fields, rows)
            temporary_paths.append(temporary)
        for (path, _fields, _rows), temporary in zip(updates, temporary_paths, strict=True):
            os.replace(temporary, path)
            replaced.append(path)
    except BaseException as exc:
        for path in reversed(replaced):
            original = originals[path]
            try:
                if original is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_bytes(original)
            except OSError:
                pass
        if isinstance(exc, OSError):
            raise ScientificDataError(f"Could not safely update registry inventories: {exc}") from exc
        raise
    finally:
        for temporary in temporary_paths:
            temporary.unlink(missing_ok=True)


def _same_resource_inventory(
    root: Path,
    resource_rows: list[dict[str, Any]],
    source_rows: list[dict[str, str]],
) -> bool:
    indexed = {
        _inventory_path(root, str(row.get("source_path", ""))): str(row.get("sha256", "")).strip()
        for row in source_rows
        if str(row.get("source_path", "")).strip()
    }
    return all(indexed.get(row["path"]) == row["sha256"] for row in resource_rows)


def register_package(
    package: Path,
    *,
    registry_root: Path | None = None,
    apply: bool = False,
    supersede: str | None = None,
) -> dict[str, Any]:
    """Plan or register one existing package without copying its resources."""

    metadata_path = _package_metadata_path(Path(package))
    metadata = _read_package_metadata(metadata_path)
    record_type = str(metadata.get("record_type", "")).strip()
    if not record_type:
        raise ScientificDataError("Package metadata is missing record_type")
    identity_field, record_id = _identity(metadata)
    basis = next(
        (
            str(metadata.get(field, "")).strip()
            for field in ("composition_basis", "amount_basis", "basis")
            if str(metadata.get(field, "")).strip()
        ),
        "",
    )
    if record_type in _DATA_RECORD_TYPES and not basis:
        raise ScientificDataError(
            f"{record_type} package is missing composition/amount basis"
        )

    root = (
        Path(registry_root).expanduser().resolve()
        if registry_root is not None
        else _infer_registry_root(metadata_path)
    )
    if not root.is_dir():
        raise ScientificDataError(f"Registry root does not exist: {root}")
    inventory_path = root.parent.parent / "normalized" / "registry-records.csv"
    source_files_path = root.parent.parent / "normalized" / "source-files.csv"
    resource_rows = _resource_rows(metadata_path, metadata, root)
    metadata_errors = _registration_metadata_errors(record_type, metadata, resource_rows)
    if metadata_errors:
        raise ScientificDataError("; ".join(metadata_errors))
    metadata_hash = _sha256(metadata_path)
    metadata_stored_path = _stored_path(root, metadata_path)
    inventory_rows, inventory_fields = _read_inventory_table(inventory_path)
    source_rows, source_fields = _read_inventory_table(source_files_path)
    warnings: list[str] = []

    declared_supersede = str(metadata.get("supersedes", "")).strip()
    requested_supersede = str(supersede or "").strip()
    if declared_supersede and requested_supersede and declared_supersede != requested_supersede:
        raise ScientificDataError("metadata supersedes and --supersede identify different records")
    supersede_id = requested_supersede or declared_supersede
    if supersede_id and not any(
        str(row.get("record_id", "")).strip() == supersede_id for row in inventory_rows
    ):
        raise ScientificDataError(f"Cannot supersede unknown record identity: {supersede_id}")

    record_rows = [
        row for row in inventory_rows
        if str(row.get("record_id", "")).strip() == record_id
    ]
    same_path_rows = [
        row for row in inventory_rows
        if str(row.get("source_path", "")).strip()
        and _inventory_path(root, str(row["source_path"])) == metadata_path
    ]
    source_index = {
        _inventory_path(root, str(row.get("source_path", ""))): row
        for row in source_rows
        if str(row.get("source_path", "")).strip()
    }
    for resource in resource_rows:
        previous = source_index.get(resource["path"])
        if previous is not None and str(previous.get("sha256", "")).strip() != resource["sha256"]:
            raise ScientificDataError(
                f"resource identity already has a different hash: {resource['stored_path']}"
            )

    if same_path_rows:
        if any(str(row.get("record_id", "")).strip() != record_id for row in same_path_rows):
            raise ScientificDataError(
                f"metadata path is already registered with a conflicting identity: {metadata_stored_path}"
            )
        if any(str(row.get("sha256", "")).strip() != metadata_hash for row in same_path_rows):
            raise ScientificDataError(
                "metadata path changed in place; retain the older package at a new path before superseding"
            )
        if _same_resource_inventory(root, resource_rows, source_rows):
            return {
                "ok": True,
                "mode": "unchanged",
                "apply": apply,
                "record_id": record_id,
                "record_type": record_type,
                "metadata_path": metadata_stored_path,
                "inventory_path": str(inventory_path),
                "source_files_path": str(source_files_path),
                "warnings": warnings,
                "lineage": {"supersedes": supersede_id} if supersede_id else {},
            }

    for row in record_rows:
        row_hash = str(row.get("sha256", "")).strip()
        if row_hash == metadata_hash and _same_resource_inventory(root, resource_rows, source_rows):
            warnings.append(
                f"record identity {record_id} is already registered at another metadata path"
            )
            return {
                "ok": True,
                "mode": "unchanged",
                "apply": apply,
                "record_id": record_id,
                "record_type": record_type,
                "metadata_path": metadata_stored_path,
                "inventory_path": str(inventory_path),
                "source_files_path": str(source_files_path),
                "warnings": warnings,
                "lineage": {"supersedes": supersede_id} if supersede_id else {},
            }
        if supersede_id != record_id:
            raise ScientificDataError(
                f"conflicting record identity {record_id}; pass --supersede {str(row.get('record_id', record_id))}"
            )

    current_source = _source_identity(metadata.get("source", metadata.get("provenance", {})))
    if current_source:
        for row in inventory_rows:
            if str(row.get("record_id", "")).strip() == record_id:
                continue
            if current_source == _source_identity(_source_metadata(row)):
                warnings.append(
                    f"source identity is already used by record {str(row.get('record_id', '')).strip()}"
                )
    for resource in resource_rows:
        previous = source_index.get(resource["path"])
        if previous is not None and str(previous.get("sha256", "")).strip() == resource["sha256"]:
            warnings.append(f"resource identity is already registered: {resource['stored_path']}")

    record_fields = list(inventory_fields) or [
        "record_type", "record_id", "title", "quality_state", "source_path", "sha256", "source"
    ]
    for field in ("record_type", "record_id", "title", "quality_state", "source_path", "sha256", "source"):
        if field not in record_fields:
            record_fields.append(field)
    if supersede_id and "supersedes" not in record_fields:
        record_fields.append("supersedes")
    new_record = {field: "" for field in record_fields}
    source_value = metadata.get("source", metadata.get("provenance", {}))
    new_record.update(
        {
            "record_type": record_type,
            "record_id": record_id,
            "title": str(metadata.get("title", "")).strip(),
            "quality_state": str(metadata.get("quality_state", metadata.get("status", ""))).strip(),
            "source_path": metadata_stored_path,
            "sha256": metadata_hash,
            "source": json.dumps(source_value, sort_keys=True) if isinstance(source_value, Mapping) else str(source_value),
        }
    )
    if supersede_id:
        new_record["supersedes"] = supersede_id

    source_fields = list(source_fields) or ["source_path", "bytes", "rows", "sha256"]
    for field in ("source_path", "bytes", "rows", "sha256"):
        if field not in source_fields:
            source_fields.append(field)
    new_source_rows = list(source_rows)
    for resource in resource_rows:
        if resource["path"] in source_index:
            continue
        new_source_rows.append(
            {
                "source_path": resource["stored_path"],
                "bytes": resource["bytes"],
                "rows": "" if resource["rows"] is None else resource["rows"],
                "sha256": resource["sha256"],
            }
        )
    new_inventory_rows = [*inventory_rows, new_record]
    payload = {
        "ok": True,
        "mode": "apply" if apply else "dry-run",
        "apply": apply,
        "record_id": record_id,
        "identity_field": identity_field,
        "record_type": record_type,
        "data_authority": str(metadata.get("data_authority", metadata.get("ownership", "shared"))),
        "metadata_path": metadata_stored_path,
        "resource_paths": [row["stored_path"] for row in resource_rows],
        "inventory_path": str(inventory_path),
        "source_files_path": str(source_files_path),
        "warnings": warnings,
        "lineage": {"supersedes": supersede_id} if supersede_id else {},
        "would_write": [str(inventory_path), str(source_files_path)],
    }
    if apply:
        _replace_inventory_tables(
            [
                (inventory_path, record_fields, new_inventory_rows),
                (source_files_path, source_fields, new_source_rows),
            ]
        )
    return payload


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
    "register_package",
    "search_registry",
    "validate_catalog",
]
