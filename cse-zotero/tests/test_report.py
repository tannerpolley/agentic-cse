from __future__ import annotations

import hashlib
import csv
import json
from pathlib import Path
import shutil
import sys

import pytest

from zotero_companion.config import CompanionConfig, write_config
from zotero_companion.report import doctor_payload, summarize_items
from zotero_companion.scientific_data import register_package, search_registry
from zotero_companion.wiki import index_wiki


def item(item_type, filename="", tags=()):
    return {
        "data": {
            "itemType": item_type,
            "filename": filename,
            "tags": [{"tag": tag, "type": tag_type} for tag, tag_type in tags],
        }
    }


def test_summarize_items_separates_markdown_and_tag_types():
    payload = summarize_items(
        [
            item("journalArticle", tags=[("status:to-read", 0)]),
            item("attachment", "paper.mmd", tags=[("publisher-keyword", 1)]),
            item("attachment", "paper.md"),
            item("attachment", "paper.pdf"),
        ]
    )

    assert payload["items"] == 4
    assert payload["attachments"] == 3
    assert payload["markdown_attachments"] == 2
    assert payload["markdown_extensions"] == {".mmd": 1, ".md": 1}
    assert payload["automatic_tag_assignments"] == 1
    assert payload["manual_tag_assignments"] == 1


def _ready_fixture(tmp_path):
    corpus = tmp_path / "corpus"
    config = CompanionConfig(
        corpus_root=corpus,
        zotero_data_dir=tmp_path / "Zotero",
        bibliography_export=tmp_path / "Zotero" / "exports" / "references.bib",
        mathpix_library_consent=False,
    )
    config_path = tmp_path / "config.toml"
    write_config(config, config_path)
    wiki = config.wiki_root
    (wiki / "manifest.json").write_text(
        json.dumps({"schema_version": 1, "item_count": 0, "records": []}),
        encoding="utf-8",
    )
    (wiki / "catalog.json").write_text(json.dumps({"items": []}), encoding="utf-8")
    (wiki / "projects").mkdir()
    evidence = wiki / "evidence" / "ABCD1234"
    evidence.mkdir(parents=True)
    companion = evidence / "notes.md"
    companion.write_text("# Evidence\n\nA retained passage.\n", encoding="utf-8")
    (evidence / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "files": [
                    {
                        "path": companion.name,
                        "format": "markdown",
                        "sha256": hashlib.sha256(companion.read_bytes()).hexdigest(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    index_wiki(wiki, records=[])
    table = config.data_root / "observations.csv"
    table.write_text("value\n1\n", encoding="utf-8")
    (config.data_root / "inventory.json").write_text(
        json.dumps(
            {
                "files": [
                    {
                        "path": table.name,
                        "sha256": hashlib.sha256(table.read_bytes()).hexdigest(),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    config.bibliography_export.parent.mkdir(parents=True)
    config.bibliography_export.write_text("@article{retained, title={Retained}}\n", encoding="utf-8")
    return config, config_path, companion, table


def _doctor(config, config_path, *, zotero_ok=False, better_bibtex_ok=False):
    return doctor_payload(
        config_path,
        config=config,
        zotero={"ok": zotero_ok, "error": "connection refused" if not zotero_ok else ""},
        better_bibtex={
            "ok": better_bibtex_ok,
            "error": "service unavailable" if not better_bibtex_ok else "",
        },
        mathpix={"mpx_on_path": False},
    )


def _registered_fixture(tmp_path, config, *, domain="thermophysical", root_pack=False):
    package = tmp_path / "external" / domain
    shutil.copytree(Path(__file__).resolve().parents[1] / "examples/data-register/package", package)
    pack = config.data_root if root_pack else config.data_root / "domains" / domain
    registry = pack / "source/registry"
    registry.mkdir(parents=True)
    register_package(package, registry_root=registry, apply=True)
    return pack, registry, package


@pytest.mark.parametrize("root_pack", [False, True])
def test_doctor_preserves_nested_audit_discrepancies_and_current_bytes(tmp_path, root_pack):
    config, config_path, _, _ = _ready_fixture(tmp_path)
    pack, registry, package = _registered_fixture(tmp_path, config, root_pack=root_pack)
    archive = registry / "archive"
    archive.mkdir()
    retired = archive / "retired.csv"
    retired.write_text("value\n2\n")
    audit = archive / "manifest.json"
    audit.write_text(json.dumps({"files": [
        {"path": "absent.csv", "sha256": "0" * 64},
        {"path": "retired.csv", "sha256": "0" * 64},
    ]}))
    inputs = [path for root in (pack, package) for path in root.rglob("*") if path.is_file()]
    before = {path: path.read_bytes() for path in inputs}

    current = _doctor(config, config_path)["readiness"]["data"]

    assert current["ready"] is True
    assert current["errors"] == []
    expected_audit = {
        "inventory": str(audit),
        "errors": ["inventory file is missing: absent.csv", "data hash mismatch for retired.csv"],
    }
    assert expected_audit in current["non_authoritative_inventories"]
    assert search_registry(registry)["results"][0]["integrity"]["verified"] is True
    assert {path: path.read_bytes() for path in inputs} == before

    source_files = pack / "normalized/source-files.csv"
    with source_files.open(newline="") as stream:
        fields = csv.DictReader(stream).fieldnames
    with source_files.open("a", newline="") as stream:
        csv.DictWriter(stream, fieldnames=fields).writerow({
            "source_path": str(audit.relative_to(registry)),
            "sha256": hashlib.sha256(audit.read_bytes()).hexdigest(),
        })
    audit.write_text(audit.read_text() + "\n")
    changed = _doctor(config, config_path)["readiness"]["data"]
    assert changed["ready"] is False
    assert any("Inventory SHA-256" in error and str(audit) in error for error in changed["errors"])
    assert expected_audit in changed["non_authoritative_inventories"]


@pytest.mark.parametrize("target", ["observations.csv", "dataset.json"])
@pytest.mark.parametrize("damage", ["changed", "missing"])
def test_doctor_refuses_damaged_external_current_files(tmp_path, target, damage):
    config, config_path, _, _ = _ready_fixture(tmp_path)
    _, registry, package = _registered_fixture(tmp_path, config)
    path = package / target
    if damage == "missing":
        path.unlink()
    else:
        path.write_text(path.read_text() + "\n")

    data = _doctor(config, config_path)["readiness"]["data"]

    assert data["ready"] is False
    if damage == "missing" and target == "dataset.json":
        assert any("Could not read registry metadata" in error and str(path) in error for error in data["errors"])
    else:
        assert any("missing" in error if damage == "missing" else "SHA-256" in error for error in data["errors"])
    search = search_registry(registry)
    assert search["warnings"] or not search["results"][0]["integrity"]["verified"]


@pytest.mark.parametrize("damage", ["missing-pair", "missing-source", "malformed-header", "relative-escape"])
def test_doctor_requires_every_declared_pack_and_standalone_inventory(tmp_path, damage):
    config, config_path, _, _ = _ready_fixture(tmp_path)
    _registered_fixture(tmp_path, config)
    other, registry, _ = _registered_fixture(tmp_path, config, domain="other")
    source_files = other / "normalized/source-files.csv"
    original_source_files = source_files.read_bytes()
    if damage == "missing-pair":
        (other / "normalized/source-files.csv").unlink()
    elif damage == "missing-source":
        registry.rmdir()
    elif damage == "malformed-header":
        (other / "normalized/registry-records.csv").write_text("unexpected\nvalue\n")
    else:
        (other / "normalized/source-files.csv").write_text("source_path,sha256\n../escape.csv," + "0" * 64 + "\n")

    data = _doctor(config, config_path)["readiness"]["data"]

    assert data["ready"] is False
    assert any(str(other) in error or "escapes registry root" in error for error in data["errors"])

    if damage == "relative-escape":
        # Standalone authority outside packs still gates the combined result.
        source_files.write_bytes(original_source_files)
        assert _doctor(config, config_path)["readiness"]["data"]["ready"] is True
        (config.data_root / "inventory.json").write_text(json.dumps({
            "files": [{"path": "observations.csv", "sha256": "0" * 64}]
        }))
        assert any("data hash mismatch" in error for error in _doctor(config, config_path)["readiness"]["data"]["errors"])


def test_doctor_checks_damage_after_the_default_search_limit(tmp_path):
    config, config_path, _, _ = _ready_fixture(tmp_path)
    _, registry, package = _registered_fixture(tmp_path, config)
    metadata = package / "dataset.json"
    value = json.loads(metadata.read_text())
    for number in range(1, 22):
        extra = tmp_path / "external" / f"package-{number:02d}"
        shutil.copytree(package, extra)
        changed = {**value, "dataset_id": f"ds:package-{number:02d}"}
        (extra / "dataset.json").write_text(json.dumps(changed))
        register_package(extra, registry_root=registry, apply=True)
    (extra / "observations.csv").unlink()

    assert len(search_registry(registry)["results"]) == 20
    data = _doctor(config, config_path)["readiness"]["data"]
    assert data["ready"] is False
    assert any(str(extra) in error and "missing" in error for error in data["errors"])


@pytest.mark.parametrize("record_type,quality_state,requires_resources", [
    ("species", "identity", False),
    ("mixture", "identity", False),
    ("reaction-constant", "unreviewed", False),
    ("observation", "unreviewed", False),
    ("dataset", "unreviewed", True),
    ("parameter_set", "unreviewed", True),
])
def test_doctor_verifies_inline_metadata_and_refuses_packages_without_resources(
    tmp_path, record_type, quality_state, requires_resources
):
    config, config_path, _, _ = _ready_fixture(tmp_path)
    pack, registry, package = _registered_fixture(tmp_path, config)
    metadata = package / "dataset.json"
    value = json.loads(metadata.read_text())
    value.pop("resources")
    value.pop("dataset_id")
    value.update(record_type=record_type, record_id="inline:example", quality_state=quality_state)
    metadata.write_text(json.dumps(value))
    inventory = pack / "normalized/registry-records.csv"
    with inventory.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    rows[0].update(
        record_type=record_type, record_id="inline:example",
        sha256=hashlib.sha256(metadata.read_bytes()).hexdigest(),
    )
    with inventory.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    current = _doctor(config, config_path)["readiness"]["data"]
    packet = search_registry(registry)["results"][0]

    assert current["ready"] is not requires_resources
    assert packet["integrity"]["verified"] is not requires_resources
    if requires_resources:
        assert "resources must be a nonempty array" in packet["integrity"]["errors"]
    else:
        metadata.write_text(metadata.read_text() + "\n")
        assert _doctor(config, config_path)["readiness"]["data"]["ready"] is False
        assert search_registry(registry)["results"][0]["metadata_hash_matches"] is False


def test_doctor_keeps_offline_readiness_separate_from_live_services(tmp_path):
    config, config_path, _, _ = _ready_fixture(tmp_path)

    absent_library = _doctor(config, config_path, better_bibtex_ok=True)
    absent_better_bibtex = _doctor(config, config_path, zotero_ok=True)

    assert absent_library["ok"] is False
    assert absent_library["readiness"]["zotero_local_api"]["ready"] is False
    assert absent_library["readiness"]["better_bibtex"]["ready"] is True
    assert absent_library["readiness"]["retained_corpus"]["ready"] is True
    assert absent_library["readiness"]["project_views"]["ready"] is True
    assert absent_library["readiness"]["project_views"]["projects"] == []
    assert absent_library["readiness"]["data"]["ready"] is True
    assert absent_library["readiness"]["bibliography_export"]["ready"] is True

    assert absent_better_bibtex["readiness"]["zotero_local_api"]["ready"] is True
    assert absent_better_bibtex["readiness"]["better_bibtex"]["ready"] is False
    assert absent_better_bibtex["readiness"]["retained_corpus"]["ready"] is True


def test_doctor_does_not_infer_current_authority_from_a_bare_table(tmp_path):
    config, config_path, _, _ = _ready_fixture(tmp_path)
    (config.data_root / "inventory.json").unlink()

    data = _doctor(config, config_path)["readiness"]["data"]

    assert data["ready"] is False
    assert data["inventories"] == []
    assert "no current inventory" in data["reason"]


def test_doctor_distinguishes_unconfigured_and_damaged_retained_state(tmp_path):
    config, config_path, companion, table = _ready_fixture(tmp_path)

    companion.write_text("changed evidence\n", encoding="utf-8")
    damaged_evidence = _doctor(config, config_path)
    assert damaged_evidence["readiness"]["retained_corpus"]["ready"] is False
    assert "hash mismatch" in damaged_evidence["readiness"]["retained_corpus"]["reason"]

    companion.write_text("# Evidence\n\nA retained passage.\n", encoding="utf-8")
    table.write_text("value\n2\n", encoding="utf-8")
    damaged_data = _doctor(config, config_path)
    assert damaged_data["readiness"]["retained_corpus"]["ready"] is True
    assert damaged_data["readiness"]["data"]["ready"] is False
    assert "data hash mismatch" in damaged_data["readiness"]["data"]["reason"]


def test_doctor_does_not_verify_supported_but_unconfigured_state(tmp_path):
    config_path = tmp_path / "missing.toml"
    payload = doctor_payload(
        config_path,
        config=None,
        configuration_error="",
        zotero={"ok": False, "error": "unavailable"},
        better_bibtex={"ok": False, "error": "unavailable"},
        mathpix={"mpx_on_path": True},
    )

    assert payload["readiness"]["configuration"]["supported"] is True
    assert payload["readiness"]["configuration"]["ready"] is False
    assert payload["readiness"]["mathpix"]["supported"] is True
    assert payload["readiness"]["mathpix"]["ready"] is False
    assert payload["readiness"]["mathpix"]["consent"]["recorded"] is False


def test_doctor_reports_invalid_configuration_as_json(monkeypatch, capsys, tmp_path):
    from zotero_companion import cli

    class UnavailableZotero:
        def get(self, *_args, **_kwargs):
            raise cli.LocalAPIError("unavailable")

    class UnavailableBetterBibTeX:
        def ready(self):
            raise cli.BetterBibTeXError("unavailable")

    config_path = tmp_path / "invalid.toml"
    config_path.write_text("[paths\n", encoding="utf-8")
    monkeypatch.setattr(cli, "ZoteroLocalAPI", UnavailableZotero)
    monkeypatch.setattr(cli, "BetterBibTeXClient", UnavailableBetterBibTeX)
    monkeypatch.setattr(sys, "argv", ["cse-zotero", "doctor", "--config", str(config_path), "--json"])

    assert cli.main() == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["configuration_valid"] is False
    assert payload["readiness"]["configuration"]["ready"] is False
    assert "Expected ']'" in payload["readiness"]["configuration"]["reason"]
