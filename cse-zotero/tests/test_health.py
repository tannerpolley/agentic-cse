from zotero_companion.health import health_report
from corpus_paths import REGISTRY_ROOT, WIKI_ROOT


def test_health_propagates_stale_source_to_linked_records_without_writes():
    report = health_report(
        WIKI_ROOT,
        stale_source_keys=["28NPJ5H6"],
        registry_root=REGISTRY_ROOT,
    )

    assert report["read_only"] is True
    assert report["ok"] is True
    assert report["review_queue_total"] >= 3
    queue_ids = {entry["record_id"] for entry in report["review_queue"]}
    assert "paper:hamer-1972" in queue_ids
    assert "dataset:hamer-1972-aqueous-coefficients" in queue_ids
    assert any(entry["impact"] == "direct" for entry in report["review_queue"])


def test_health_matches_registry_ids_and_reports_attention_records():
    report = health_report(
        WIKI_ROOT,
        changed_registry_ids=["registry:figiel2025-table1-water-relative-dielectric-constant"],
        registry_root=REGISTRY_ROOT,
    )

    queue = {entry["record_id"]: entry for entry in report["review_queue"]}
    assert queue["dataset:figiel-water-dielectric-table1"]["impact"] == "direct"
    assert report["attention_queue_total"] >= 1
    assert any(item["status"] == "needs-review" for item in report["attention_queue"])


def test_health_flags_missing_evidence_in_a_temporary_record(tmp_path):
    root = tmp_path / "wiki"
    record_path = root / "records/papers/example.json"
    record_path.parent.mkdir(parents=True)
    record_path.write_text(
        """{
          "schema_version": 1,
          "record_type": "paper_brief",
          "record_id": "paper:example",
          "title": "Example",
          "status": "needs-review",
          "confidence": "low",
          "summary": "Example record.",
          "provenance": {
            "derivation_kind": "source-reported",
            "sources": [{
              "zotero_key": "ABCD1234",
              "locator": {"kind": "page", "value": "1"},
              "evidence_path": "wiki/evidence/ABCD1234/missing.md"
            }],
            "derived_from": []
          }
        }""",
        encoding="utf-8",
    )
    (root / "relations.json").write_text('{"schema_version": 1, "relations": []}', encoding="utf-8")

    report = health_report(root)

    assert report["ok"] is False
    assert report["orphaned_total"] == 1
    assert "missing evidence path" in report["orphaned"][0]["reasons"][0]
    assert report["review_queue"][0]["record_id"] == "paper:example"
