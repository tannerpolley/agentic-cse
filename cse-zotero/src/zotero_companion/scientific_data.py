"""LinkML validation and direct DuckDB queries for scientific data."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb
from linkml.validator import validate_file
from linkml_runtime.utils.schemaview import SchemaView


class ScientificDataError(ValueError):
    """Raised when scientific data cannot be validated or queried."""


def validate_catalog(
    data_path: Path,
    schema_path: Path = Path("schema/companion.yaml"),
    target_class: str = "CompanionCatalog",
) -> dict[str, Any]:
    """Validate one YAML, JSON, CSV, or TSV file against a LinkML class."""

    data_path = Path(data_path)
    schema_path = Path(schema_path)
    if not data_path.is_file():
        raise ScientificDataError(f"Data file does not exist: {data_path}")
    if not schema_path.is_file():
        raise ScientificDataError(f"LinkML schema does not exist: {schema_path}")
    schema = SchemaView(
        schema_path.resolve(),
        base_dir=str(schema_path.resolve().parent),
        merge_imports=True,
    ).schema
    report = validate_file(data_path, schema, target_class)
    results = [str(result) for result in report.results]
    return {
        "ok": not results,
        "data": str(data_path),
        "schema": str(schema_path),
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
