import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import duckdb
import pytest
import csv
import hashlib

from zotero_companion.scientific_data import (
    ScientificDataError,
    query_table,
    register_package,
    search_registry,
    select_resource,
    validate_catalog,
)


ROOT = Path(__file__).resolve().parents[1]
REGISTER_FIXTURE = ROOT / "examples/data-register/package"


def _registration_fixture(tmp_path: Path) -> tuple[Path, Path]:
    package = tmp_path / "project" / "data" / "registered-package"
    shutil.copytree(REGISTER_FIXTURE, package)
    registry = tmp_path / "source" / "registry"
    registry.mkdir(parents=True)
    return package, registry


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
    result = validate_catalog(ROOT / "examples/core-records.yaml")
    assert result["ok"] is True
    assert result["errors"] == []


def test_default_schema_cli_works_from_unrelated_directory(tmp_path):
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "src")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "zotero_companion.cli",
            "schema-validate",
            str(ROOT / "examples/core-records.yaml"),
            "--json",
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["ok"] is True


def test_thermophysical_domain_record_is_valid():
    result = validate_catalog(
        ROOT / "examples/thermophysical-record.yaml",
        ROOT / "src/zotero_companion/schemas/linkml/thermophysical.yaml",
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


def test_registry_search_accepts_case_insensitive_hash_declarations(tmp_path):
    registry, _ = _registry_fixture(tmp_path)
    for name in ("registry-records.csv", "source-files.csv"):
        path = tmp_path / "normalized" / name
        with path.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
            fields = list(rows[0])
        for row in rows:
            row["sha256"] = row["sha256"].upper()
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    assert search_registry(registry, query="MEA")["results"][0]["integrity"]["verified"] is True


def test_registry_search_requires_the_canonical_inventory(tmp_path):
    (tmp_path / "registry").mkdir()
    with pytest.raises(ScientificDataError, match="Normalized registry inventory is missing"):
        search_registry(tmp_path / "registry", query="MEA")


@pytest.mark.parametrize("name", ["registry-records.csv", "source-files.csv"])
@pytest.mark.parametrize("declaration", [
    "unexpected\nvalue\n",
    "source_path,sha256\n," + "0" * 64 + "\n",
    "source_path,sha256\nfile.csv,not-a-hash\n",
    "source_path,sha256\nfile.csv\n",
])
def test_registry_rejects_malformed_current_inventory(tmp_path, name, declaration):
    registry, _ = _registry_fixture(tmp_path)
    (tmp_path / "normalized" / name).write_text(declaration)

    with pytest.raises(ScientificDataError, match="Registry inventory|Malformed registry"):
        search_registry(registry, limit=None)


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


def test_data_register_links_external_package_and_repeated_registration_is_unchanged(tmp_path):
    package, registry = _registration_fixture(tmp_path)
    metadata = package / "dataset.json"

    preview = register_package(metadata, registry_root=registry)
    assert preview["mode"] == "dry-run"
    assert not (tmp_path / "normalized").exists()

    applied = register_package(metadata, registry_root=registry, apply=True)
    repeated = register_package(metadata, registry_root=registry, apply=True)

    assert applied["mode"] == "apply"
    assert repeated["mode"] == "unchanged"
    assert not (registry / "observations.csv").exists()
    result = search_registry(registry, query="MEA density")
    assert result["count"] == 1
    packet = result["results"][0]
    assert packet["record_id"] == "ds:registered-mea-density"
    assert packet["data_authority"] == "shared"
    assert packet["provenance"]["attachment_key"] == "ATT1234"
    assert packet["resources"][0]["path"] == str(package / "observations.csv")
    assert packet["integrity"]["verified"] is True


def test_data_register_cli_defaults_to_dry_run(tmp_path):
    package, registry = _registration_fixture(tmp_path)
    cli = shutil.which("cse-zotero") or str(Path(sys.executable).with_name("cse-zotero"))
    result = subprocess.run(
        [
            cli,
            "data-register",
            str(package),
            "--registry-root",
            str(registry),
            "--json",
        ],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["mode"] == "dry-run"


def test_data_register_revision_keeps_lineage_and_old_input(tmp_path):
    package, registry = _registration_fixture(tmp_path)
    register_package(package, registry_root=registry, apply=True)
    revision = tmp_path / "project" / "data" / "registered-package-v2"
    shutil.copytree(package, revision)
    revision_metadata = revision / "dataset.json"
    metadata = json.loads(revision_metadata.read_text(encoding="utf-8"))
    metadata["version"] = "2.0.0"
    revision_metadata.write_text(json.dumps(metadata), encoding="utf-8")
    (revision / "observations.csv").write_text(
        "value,value_unit,uncertainty,uncertainty_unit\n1011.4,kg/m3,,kg/m3\n",
        encoding="utf-8",
    )

    result = register_package(
        revision_metadata,
        registry_root=registry,
        apply=True,
        supersede="ds:registered-mea-density",
    )

    assert result["lineage"] == {"supersedes": "ds:registered-mea-density"}
    packets = search_registry(registry)["results"]
    revised = next(packet for packet in packets if packet["metadata_path"] == str(revision_metadata))
    assert revised["version"] == "2.0.0"
    assert revised["supersedes"] == "ds:registered-mea-density"
    assert len(packets) == 2
    assert (package / "observations.csv").read_text(encoding="utf-8").startswith("value,value_unit")


def test_data_select_copies_one_resource_and_preserves_lineage(tmp_path):
    package, registry = _registration_fixture(tmp_path)
    register_package(package, registry_root=registry, apply=True)
    analysis = tmp_path / "analyses" / "density"

    result = select_resource(
        registry,
        "ds:registered-mea-density",
        analysis,
        resource="observations.csv",
        apply=True,
    )

    selected = analysis / "inputs/observations.csv"
    lineage = analysis / "inputs/observations.csv.lineage.json"
    assert result["mode"] == "apply"
    assert selected.read_bytes() == (package / "observations.csv").read_bytes()
    assert not selected.is_symlink()
    record = json.loads(lineage.read_text(encoding="utf-8"))
    assert record["record_id"] == "ds:registered-mea-density"
    assert record["source"]["zotero_key"] == "ABCD1234"
    assert record["source"]["locator"] == {
        "kind": "table",
        "value": "Table 2, row 1",
    }
    assert record["composition_basis"] == "pure component"
    assert record["uncertainty"] == {"interpretation": "not reported by source"}
    assert record["resource"]["sha256"] == hashlib.sha256(selected.read_bytes()).hexdigest()


def test_data_select_unchanged_rerun_does_not_rewrite_snapshot(tmp_path):
    package, registry = _registration_fixture(tmp_path)
    register_package(package, registry_root=registry, apply=True)
    analysis = tmp_path / "analyses" / "density"
    first = select_resource(
        registry,
        "ds:registered-mea-density",
        analysis,
        resource="observations.csv",
        apply=True,
    )
    selected = analysis / "inputs/observations.csv"
    lineage = analysis / "inputs/observations.csv.lineage.json"
    before = {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in (selected, lineage)
    }

    repeated = select_resource(
        registry,
        "ds:registered-mea-density",
        analysis,
        resource="observations.csv",
        apply=True,
    )

    assert first["mode"] == "apply"
    assert repeated["mode"] == "unchanged"
    assert repeated["would_write"] == []
    assert {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in (selected, lineage)
    } == before


def test_data_select_refuses_tampered_registered_resource(tmp_path):
    package, registry = _registration_fixture(tmp_path)
    register_package(package, registry_root=registry, apply=True)
    (package / "observations.csv").write_text(
        "value,value_unit,uncertainty,uncertainty_unit\n999,kg/m3,,kg/m3\n",
        encoding="utf-8",
    )

    with pytest.raises(ScientificDataError, match="hash mismatch|unverified"):
        select_resource(
            registry,
            "ds:registered-mea-density",
            tmp_path / "analyses" / "density",
            resource="observations.csv",
            apply=True,
        )


def test_data_select_reports_missing_registered_resource(tmp_path):
    package, registry = _registration_fixture(tmp_path)
    register_package(package, registry_root=registry, apply=True)
    (package / "observations.csv").unlink()

    with pytest.raises(ScientificDataError, match="missing|unverified"):
        select_resource(
            registry,
            "ds:registered-mea-density",
            tmp_path / "analyses" / "density",
            resource="observations.csv",
            apply=True,
        )


def test_data_select_cli_defaults_to_dry_run(tmp_path):
    package, registry = _registration_fixture(tmp_path)
    register_package(package, registry_root=registry, apply=True)
    analysis = tmp_path / "analyses" / "density"
    cli = shutil.which("cse-zotero") or str(Path(sys.executable).with_name("cse-zotero"))

    result = subprocess.run(
        [
            cli,
            "data-select",
            "ds:registered-mea-density",
            "--resource",
            "observations.csv",
            "--analysis",
            str(analysis),
            "--registry-root",
            str(registry),
            "--json",
        ],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["mode"] == "dry-run"
    assert not (analysis / "inputs").exists()


def test_data_select_requires_explicit_registered_revision(tmp_path):
    package, registry = _registration_fixture(tmp_path)
    register_package(package, registry_root=registry, apply=True)
    revision = tmp_path / "project" / "data" / "registered-package-v2"
    shutil.copytree(package, revision)
    revision_metadata = revision / "dataset.json"
    metadata = json.loads(revision_metadata.read_text(encoding="utf-8"))
    metadata["version"] = "2.0.0"
    revision_metadata.write_text(json.dumps(metadata), encoding="utf-8")
    (revision / "observations.csv").write_text(
        "value,value_unit,uncertainty,uncertainty_unit\n1011.4,kg/m3,,kg/m3\n",
        encoding="utf-8",
    )
    register_package(
        revision_metadata,
        registry_root=registry,
        apply=True,
        supersede="ds:registered-mea-density",
    )

    with pytest.raises(ScientificDataError, match="--version"):
        select_resource(
            registry,
            "ds:registered-mea-density",
            tmp_path / "analyses" / "density",
            resource="observations.csv",
            apply=True,
        )

    selected = select_resource(
        registry,
        "ds:registered-mea-density",
        tmp_path / "analyses" / "density-v2",
        resource="observations.csv",
        version="2.0.0",
        apply=True,
    )
    assert selected["version"] == "2.0.0"
    assert json.loads(
        (tmp_path / "analyses/density-v2/inputs/observations.csv.lineage.json").read_text()
    )["version"] == "2.0.0"


def test_data_select_refuses_conflicting_existing_snapshot(tmp_path):
    package, registry = _registration_fixture(tmp_path)
    register_package(package, registry_root=registry, apply=True)
    analysis = tmp_path / "analyses" / "density"
    select_resource(
        registry,
        "ds:registered-mea-density",
        analysis,
        resource="observations.csv",
        apply=True,
    )
    selected = analysis / "inputs/observations.csv"
    selected.write_text("value,value_unit\n999,kg/m3\n", encoding="utf-8")

    with pytest.raises(ScientificDataError, match="Selected input hash mismatch"):
        select_resource(
            registry,
            "ds:registered-mea-density",
            analysis,
            resource="observations.csv",
            apply=True,
        )


def test_data_register_rejects_basis_tampering_and_conflicting_identity(tmp_path):
    package, registry = _registration_fixture(tmp_path)
    metadata_path = package / "dataset.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata.pop("composition_basis")
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(ScientificDataError, match="composition/amount basis"):
        register_package(metadata_path, registry_root=registry)

    metadata["composition_basis"] = "pure component"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    register_package(metadata_path, registry_root=registry, apply=True)
    (package / "observations.csv").write_text("value,value_unit\n999,kg/m3\n", encoding="utf-8")
    with pytest.raises(ScientificDataError, match="resource identity already has a different hash"):
        register_package(metadata_path, registry_root=registry)

    conflict = tmp_path / "project" / "data" / "conflicting-package"
    shutil.copytree(REGISTER_FIXTURE, conflict)
    with pytest.raises(ScientificDataError, match="conflicting record identity"):
        register_package(conflict / "dataset.json", registry_root=registry)


def test_data_register_rejects_incomplete_dataset_metadata_and_external_traversal(tmp_path):
    package, registry = _registration_fixture(tmp_path)
    metadata_path = package / "dataset.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata.pop("source")
    metadata.pop("uncertainty")
    metadata.pop("quality_state")
    (package / "observations.csv").write_text("value\n1010.2\n", encoding="utf-8")
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(ScientificDataError, match="source provenance identity"):
        register_package(metadata_path, registry_root=registry)

    outside = package.parent / "outside.csv"
    outside.write_text("value,value_unit\n1,kg/m3\n", encoding="utf-8")
    metadata["source"] = {"repository": "project", "locator": {"kind": "row", "value": "1"}}
    metadata["uncertainty"] = {"interpretation": "not reported"}
    metadata["quality_state"] = "unreviewed"
    metadata["resources"][0]["path"] = "../outside.csv"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(ScientificDataError, match="escapes the package directory"):
        register_package(metadata_path, registry_root=registry)


def test_data_register_requires_parameter_model_conventions(tmp_path):
    package, registry = _registration_fixture(tmp_path)
    metadata_path = package / "dataset.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["record_type"] = "parameter_set"
    metadata["parameter_set_id"] = "ps:registered-mea"
    metadata.pop("dataset_id")
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(ScientificDataError, match="model or reference-state"):
        register_package(metadata_path, registry_root=registry)


def test_data_register_interruption_rolls_back_both_inventories(tmp_path, monkeypatch):
    package, registry = _registration_fixture(tmp_path)
    register_package(package, registry_root=registry, apply=True)
    inventory = tmp_path / "normalized" / "registry-records.csv"
    source_files = tmp_path / "normalized" / "source-files.csv"
    original = {path: path.read_bytes() for path in (inventory, source_files)}
    second_package = tmp_path / "project" / "data" / "second-package"
    shutil.copytree(REGISTER_FIXTURE, second_package)
    second_metadata = second_package / "dataset.json"
    changed = json.loads(second_metadata.read_text(encoding="utf-8"))
    changed["dataset_id"] = "ds:second-package"
    second_metadata.write_text(json.dumps(changed), encoding="utf-8")
    real_replace = os.replace
    calls = 0

    def interrupt(source, destination):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("interrupted")
        return real_replace(source, destination)

    monkeypatch.setattr("zotero_companion.scientific_data.os.replace", interrupt)
    with pytest.raises(ScientificDataError, match="safely update registry inventories"):
        register_package(second_metadata, registry_root=registry, apply=True)

    assert {path: path.read_bytes() for path in (inventory, source_files)} == original
    assert search_registry(registry)["count"] == 1

    calls = 0

    def interrupt_keyboard(source, destination):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise KeyboardInterrupt
        return real_replace(source, destination)

    monkeypatch.setattr("zotero_companion.scientific_data.os.replace", interrupt_keyboard)
    with pytest.raises(KeyboardInterrupt):
        register_package(second_metadata, registry_root=registry, apply=True)

    assert {path: path.read_bytes() for path in (inventory, source_files)} == original
    assert search_registry(registry)["count"] == 1
