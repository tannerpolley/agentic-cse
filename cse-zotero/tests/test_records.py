import json
from pathlib import Path

from zotero_wiki.records import lineage, lint_records, record_lookup, search_records


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_current_typed_records_and_lineage_are_auditable():
    root = REPO_ROOT / "wiki"
    checked = lint_records(
        root,
        registry_root=REPO_ROOT.parent / "thermophysical-data-registry",
    )

    assert checked["ok"] is True
    assert checked["record_count"] == 13
    assert checked["relation_count"] == 11
    assert checked["record_types"]["equation"] == 3

    record = record_lookup(root, "equation:figiel-born-solvation-shell")
    assert record["provenance"]["sources"][0]["zotero_key"] == "YEENX35P"
    assert record["provenance"]["sources"][0]["attachment_key"] == "2M74BKJG"

    trace = lineage(
        root,
        "dataset:hamer-1972-aqueous-coefficients",
        registry_root=REPO_ROOT.parent / "thermophysical-data-registry",
    )
    upstream_ids = {entry["record_id"] for entry in trace["upstream"]}
    assert "paper:hamer-1972" in upstream_ids
    assert "equation:hamer-excess-gibbs-bridge" in upstream_ids
    assert trace["read_only"] is True


def test_hamer_companion_is_exactly_the_declared_existing_zotero_file():
    manifest = json.loads(
        (REPO_ROOT / "wiki/evidence/28NPJ5H6/manifest.json").read_text(encoding="utf-8")
    )
    companion = REPO_ROOT / "wiki/evidence/28NPJ5H6/Hamer1972.md"
    import hashlib

    assert manifest["conversion"]["converter"] == "none"
    assert manifest["files"][0]["zotero_attachment_key"] == "VYE43TLN"
    assert hashlib.sha256(companion.read_bytes()).hexdigest() == manifest["files"][0]["sha256"]


def test_record_lint_rejects_missing_provenance_and_unresolved_relation(tmp_path):
    root = tmp_path / "wiki"
    (root / "records/ideas").mkdir(parents=True)
    (root / "records/ideas/broken.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "record_type": "idea",
                "record_id": "idea:broken",
                "title": "Broken",
                "status": "proposed",
                "confidence": "low",
                "summary": "No provenance.",
                "provenance": {
                    "derivation_kind": "inferred",
                    "sources": [],
                    "derived_from": [],
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "relations.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "relations": [
                    {
                        "relation_id": "rel:broken",
                        "relation_type": "supports",
                        "source": "idea:broken",
                        "target": "equation:missing",
                        "rationale": "Missing target.",
                        "status": "proposed",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    checked = lint_records(root)

    assert checked["ok"] is False
    assert any("provenance needs sources or derived_from" in error for error in checked["errors"])
    assert any("unresolved relation endpoint" in error for error in checked["errors"])


def test_record_search_is_deterministic():
    matches = search_records(REPO_ROOT / "wiki", query="Born-provider", limit=10)
    assert [record["record_id"] for record in matches] == [
        "implementation:epcsaft-born-provider",
    ]
