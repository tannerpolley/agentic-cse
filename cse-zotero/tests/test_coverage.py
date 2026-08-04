from pathlib import Path

from zotero_wiki.coverage import coverage_report
from zotero_wiki.wiki import WikiSnapshot, index_wiki, materialize_snapshot


def _snapshot() -> WikiSnapshot:
    return WikiSnapshot(
        items=(
            {
                "key": "EQ123456",
                "version": 1,
                "data": {
                    "itemType": "journalArticle",
                    "title": "Equilibrium example",
                    "collections": ["COLL001"],
                },
            },
            {
                "key": "LI123456",
                "version": 1,
                "data": {
                    "itemType": "report",
                    "title": "Lithium example",
                    "collections": ["COLL002"],
                },
            },
        ),
        collections=(
            {"key": "COLL001", "data": {"name": "ePC-SAFT Equilibrium"}},
            {"key": "COLL002", "data": {"name": "Lithium Extraction"}},
        ),
        tags=(),
        searches=(),
    )


def test_coverage_reports_gaps_without_treating_them_as_errors(tmp_path: Path):
    root = tmp_path / "wiki"
    materialize_snapshot(_snapshot(), root, apply=True)
    index_wiki(root)

    report = coverage_report(root, limit=1)

    assert report["ok"] is True
    assert report["read_only"] is True
    assert report["source_count"] == 2
    assert report["coverage"]["briefs"]["covered"] == 0
    assert report["coverage"]["briefs"]["relevant_total"] == 2
    assert report["coverage"]["briefs"]["relevant_ratio"] == 0.0
    gaps = {gap["kind"]: gap for gap in report["gaps"]}
    assert gaps["relevant_without_brief"]["count"] == 2
    assert len(gaps["relevant_without_brief"]["examples"]) == 1


def test_metadata_brief_scaffolds_remain_in_the_unbriefed_queue(tmp_path: Path):
    root = tmp_path / "wiki"
    materialize_snapshot(_snapshot(), root, apply=True)
    papers = root / "papers"
    papers.mkdir()
    (papers / "example.md").write_text(
        "# Example\n\n- brief_status: scaffold\n- Zotero key: EQ123456\n",
        encoding="utf-8",
    )
    index_wiki(root)

    report = coverage_report(root)
    triage = report["queues"]

    assert triage["brief_scaffolded"]["examples"][0]["zotero_key"] == "EQ123456"
    assert triage["unbriefed_relevant"]["examples"][0]["zotero_key"] == "EQ123456"


def test_current_coverage_is_available_for_the_full_materialized_corpus():
    report = coverage_report(Path(__file__).resolve().parents[1] / "wiki")

    assert report["source_count"] == 378
    assert report["coverage"]["typed_records"]["count"] >= 47
    assert report["coverage"]["typed_records"]["source_keys_covered"] >= 8
    assert report["coverage"]["validation"]["record_count"] == 1
