from zotero_companion.records import validate_record
import json
from pathlib import Path

from zotero_companion.templates import paper_brief_template, record_template


def test_record_template_is_read_only_and_structurally_valid():
    output = record_template(
        "equation",
        record_id="equation:example",
        title="Example equation",
        zotero_key="ABCD1234",
    )

    assert output["read_only"] is True
    assert output["zotero_mutation"] is False
    record = output["record"]
    assert validate_record(record) == []
    assert record["provenance"]["sources"][0]["zotero_key"] == "ABCD1234"
    assert "expression" in output["template"]["fill_before_review"]


def test_registry_template_keeps_unresolved_registry_work_explicit():
    record = record_template("dataset_reference")["record"]

    assert validate_record(record) == []
    assert record["status"] == "proposed"
    assert record["registry_refs"][0]["registry_id"].startswith("TODO:")


def test_paper_brief_template_is_metadata_only_and_does_not_write(tmp_path: Path):
    wiki = tmp_path / "wiki"
    source_dir = wiki / "sources" / "ABCD1234"
    source_dir.mkdir(parents=True)
    (source_dir / "record.json").write_text(
        json.dumps(
            {
                "zotero_key": "ABCD1234",
                "title": "Example source",
                "citation_key": "Example2024",
                "doi": "10.1234/example",
                "year": "2024",
                "creators": ["Ada Lovelace"],
                "projects": ["epcsaft-equilibrium"],
            }
        ),
        encoding="utf-8",
    )

    output = paper_brief_template(wiki, "ABCD1234")

    assert output["read_only"] is True
    assert output["suggested_path"] == "wiki/papers/Example2024.md"
    assert "brief_status: scaffold" in output["markdown"]
    assert "10.1234/example" in output["markdown"]
    assert not (wiki / "papers").exists()
