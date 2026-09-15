from pathlib import Path
import subprocess
import sys
import tempfile

import duckdb
import pytest
import csv
import hashlib
import json

from zotero_companion.scientific_data import (
    ScientificDataError,
    query_table,
    search_registry,
    validate_catalog,
)


ROOT = Path(__file__).resolve().parents[1]


def _registry_fixture(tmp_path: Path) -> tuple[Path, Path]:
    registry = tmp_path / "source" / "registry"
    package = registry / "data/species/monoethanolamine/properties/density/example"
    package.mkdir(parents=True)
    resource = package / "raw/observations.csv"
    resource.parent.mkdir()
    resource.write_text("value,value_unit,uncertainty_unit\n1.0,kg/m3,kg/m3\n", encoding="utf-8")
    metadata = {
        "schema_version": 1,
        "record_type": "dataset",
        "dataset_id": "ds:example-mea-density",
        "version": "1.0.0",
        "system": {"kind": "species", "id": "monoethanolamine"},
        "title": "Monoethanolamine density example",
        "property": "liquid mass density",
        "quality_state": "unreviewed",
        "components": ["monoethanolamine"],
        "composition_basis": "Pure component",
        "conditions": {"temperature_K": 298.15},
        "source": {
            "zotero_key": "ABCD1234",
            "locator": {"kind": "table", "value": "Table 1"},
        },
        "resources": [
            {
                "path": "raw/observations.csv",
                "format": "csv",
                "role": "source-faithful",
                "row_count": 1,
                "required_columns": ["value", "value_unit"],
            }
        ],
    }
    metadata_path = package / "dataset.json"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    normalized = tmp_path / "normalized"
    normalized.mkdir()
    metadata_relative = str(metadata_path.relative_to(registry))
    resource_relative = str(resource.relative_to(registry))
    with (normalized / "registry-records.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["record_type", "record_id", "title", "quality_state", "source_path", "sha256", "source"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "record_type": "dataset",
                "record_id": metadata["dataset_id"],
                "title": metadata["title"],
                "quality_state": metadata["quality_state"],
                "source_path": metadata_relative,
                "sha256": hashlib.sha256(metadata_path.read_bytes()).hexdigest(),
                "source": json.dumps(metadata["source"]),
            }
        )
    with (normalized / "source-files.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["source_path", "sha256"])
        writer.writeheader()
        writer.writerow({"source_path": resource_relative, "sha256": hashlib.sha256(resource.read_bytes()).hexdigest()})
    return registry, resource


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


def test_registry_search_resolves_aliases_units_and_provenance(tmp_path):
    registry, _ = _registry_fixture(tmp_path)
    candidate_index = tmp_path / "normalized/source-ready-candidates.csv"
    candidate_index.write_text("candidate_id\ncandidate:mea\n")
    candidate = registry / "candidate.json"
    candidate.write_text(json.dumps({
        "dataset_id": "candidate:mea", "title": "Monoethanolamine density",
        "resources": [{"path": "unreviewed.csv"}],
    }))

    result = search_registry(registry, query="MEA density", limit=5)

    assert result["read_only"] is True
    assert result["count"] == 1
    assert result["candidate_inventories"] == [str(candidate_index)]
    packet = result["results"][0]
    assert packet["record_id"] == "ds:example-mea-density"
    assert packet["quality_state"] == "unreviewed"
    assert packet["composition_basis"] == "Pure component"
    assert packet["provenance"]["zotero_key"] == "ABCD1234"
    resource = packet["resources"][0]
    assert Path(resource["path"]).is_absolute()
    assert resource["exists"] is True
    assert resource["hash_matches"] is True
    assert packet["integrity"]["verified"] is True
    assert resource["units_in_table"] == {
        "unit_columns": ["value_unit", "uncertainty_unit"],
        "sampled_unit_values": {"uncertainty_unit": "kg/m3", "value_unit": "kg/m3"},
    }


def test_cli_dataset_discovery_and_local_reuse(tmp_path):
    registry, expected_resource = _registry_fixture(tmp_path)
    corpus_root = registry.parent.parent
    original = {
        path: path.read_bytes()
        for path in corpus_root.rglob("*")
        if path.is_file()
    }

    def run_cli(*args):
        completed = subprocess.run(
            [sys.executable, "-m", "zotero_companion.cli", *args],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(completed.stdout)

    discovered = run_cli(
        "data-search",
        "MEA density",
        "--registry-root",
        str(registry),
        "--json",
    )
    assert discovered["count"] == 1
    packet = discovered["results"][0]
    resource = packet["resources"][0]
    source_resource = Path(resource["path"])
    assert packet["record_id"] == "ds:example-mea-density"
    assert source_resource == expected_resource
    assert packet["provenance"]["zotero_key"] == "ABCD1234"
    assert packet["provenance"]["locator"] == {"kind": "table", "value": "Table 1"}
    assert resource["units_in_table"]["sampled_unit_values"]["value_unit"] == "kg/m3"
    assert hashlib.sha256(source_resource.read_bytes()).hexdigest() == resource["sha256"]
    assert resource["sha256"] == resource["declared_sha256"]
    assert resource["hash_matches"] is True
    assert packet["integrity"]["verified"] is True

    with tempfile.TemporaryDirectory() as project:
        local_resource = Path(project) / "observations.csv"
        local_resource.write_bytes(source_resource.read_bytes())
        queried = run_cli(
            "data-query",
            str(local_resource),
            "--sql",
            "SELECT value, value_unit FROM records",
            "--json",
        )
        assert queried["table"] == str(local_resource)
        assert queried["rows"] == [{"value": 1.0, "value_unit": "kg/m3"}]

    assert not Path(project).exists()
    assert {
        path: path.read_bytes()
        for path in corpus_root.rglob("*")
        if path.is_file()
    } == original


def test_registry_search_reports_missing_and_hash_mismatch(tmp_path):
    registry, resource = _registry_fixture(tmp_path)
    resource.write_text("value,value_unit,uncertainty_unit\n2.0,kg/m3,kg/m3\n", encoding="utf-8")

    mismatch = search_registry(registry, query="MEA", limit=5)["results"][0]
    assert mismatch["integrity"]["ok"] is False
    assert mismatch["integrity"]["verified"] is False
    assert mismatch["resources"][0]["hash_matches"] is False
    assert "SHA-256" in mismatch["integrity"]["errors"][0]

    resource.unlink()
    missing = search_registry(registry, query="MEA", limit=5)["results"][0]
    assert missing["integrity"]["ok"] is False
    assert missing["integrity"]["verified"] is False
    assert missing["resources"][0]["exists"] is False
    assert "missing" in missing["integrity"]["errors"][0]


def test_registry_search_requires_the_canonical_inventory(tmp_path):
    (tmp_path / "registry").mkdir()
    with pytest.raises(ScientificDataError, match="Normalized registry inventory is missing"):
        search_registry(tmp_path / "registry", query="MEA")


def _rewrite_fixture_metadata(registry, **changes):
    index = registry.parent.parent / "normalized/registry-records.csv"
    with index.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    path = registry / rows[0]["source_path"]
    metadata = json.loads(path.read_text())
    metadata.update(changes)
    path.write_text(json.dumps(metadata))
    rows[0]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    with index.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


@pytest.mark.parametrize("resources", [[None], {"path": "raw/observations.csv"}, []])
def test_registry_malformed_resources_never_verify(tmp_path, resources):
    registry, _ = _registry_fixture(tmp_path)
    _rewrite_fixture_metadata(registry, resources=resources)
    packet = search_registry(registry, query="MEA")["results"][0]
    assert packet["integrity"]["ok"] is False
    assert packet["integrity"]["verified"] is False
    assert packet["integrity"]["errors"]


def test_registry_missing_resource_inventory_never_verifies(tmp_path):
    registry, _ = _registry_fixture(tmp_path)
    (tmp_path / "normalized/source-files.csv").unlink()
    result = search_registry(registry, query="MEA")
    assert result["warnings"]
    assert result["results"][0]["integrity"]["verified"] is False
    assert result["results"][0]["integrity"]["ok"] is False


@pytest.mark.parametrize("property_name", ["density", "viscosity"])
def test_registry_aliases_preserve_literal_property_matches(tmp_path, property_name):
    registry, _ = _registry_fixture(tmp_path)
    _rewrite_fixture_metadata(registry, property=property_name, title="Measurement")
    assert search_registry(registry, query=property_name)["count"] == 1
