from pathlib import Path

import duckdb
import pytest

from zotero_companion.scientific_data import ScientificDataError, query_table, validate_catalog


ROOT = Path(__file__).resolve().parents[1]


def test_linkml_example_is_valid():
    result = validate_catalog(
        ROOT / "data/examples/core-records.yaml", ROOT / "schema/companion.yaml"
    )
    assert result["ok"] is True
    assert result["errors"] == []


def test_thermophysical_domain_record_is_valid():
    result = validate_catalog(
        ROOT / "data/examples/thermophysical-record.yaml",
        ROOT / "schema/thermophysical.yaml",
        "ThermophysicalRecord",
    )
    assert result["ok"] is True
    assert result["errors"] == []


def test_duckdb_query_returns_grouped_registry_counts(tmp_path):
    table = tmp_path / "records.csv"
    table.write_text("record_type,value\ndataset,1\ndataset,2\nsource,3\n")
    result = query_table(
        table,
        "SELECT record_type, count(*) AS count FROM records GROUP BY record_type ORDER BY record_type",
    )
    assert result["rows"] == [
        {"record_type": "dataset", "count": 2},
        {"record_type": "source", "count": 1},
    ]


def test_duckdb_rejects_mutating_sql(tmp_path):
    table = tmp_path / "records.csv"
    table.write_text("record_type\ndataset\n")
    with pytest.raises(ScientificDataError, match="Only one SELECT"):
        query_table(table, "DELETE FROM records")


def test_duckdb_blocks_external_file_access(tmp_path):
    table = tmp_path / "records.csv"
    table.write_text("record_type\ndataset\n")
    with pytest.raises(ScientificDataError, match="file system operations are disabled"):
        query_table(table, "SELECT * FROM glob('*')")


def test_duckdb_results_are_json_safe_without_losing_decimal_text(tmp_path):
    table = tmp_path / "records.parquet"
    connection = duckdb.connect(":memory:")
    connection.execute(
        "COPY (SELECT CAST(1.20 AS DECIMAL(4,2)) AS value, DATE '2026-08-13' AS observed) "
        f"TO '{table}' (FORMAT PARQUET)"
    )
    connection.close()

    result = query_table(table, "SELECT * FROM records")

    assert result["rows"] == [{"value": "1.20", "observed": "2026-08-13"}]
