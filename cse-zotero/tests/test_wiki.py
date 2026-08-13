import hashlib
import json
import sqlite3

from zotero_companion.wiki import (
    WikiSnapshot,
    build_source_records,
    classify_source,
    context_pack,
    evidence_passages,
    freshness_status,
    index_wiki,
    materialize_snapshot,
    search_evidence_chunks,
    search_wiki,
    source_record,
    stale_report,
    triage_wiki,
    verify_wiki,
)


def snapshot() -> WikiSnapshot:
    return WikiSnapshot(
        items=(
            {
                "key": "EQ123456",
                "version": 7,
                "data": {
                    "itemType": "journalArticle",
                    "title": "Chemical potential and phase equilibrium",
                    "creators": [{"firstName": "Ada", "lastName": "Lovelace"}],
                    "date": "2024-05-01",
                    "citationKey": "lovelace2024",
                    "DOI": "10.1234/example",
                    "abstractNote": "A study of chemical potential in phase equilibrium.",
                    "tags": [{"tag": "Review", "type": 0}],
                    "collections": ["COLL001"],
                },
            },
            {
                "key": "ATT12345",
                "version": 2,
                "data": {
                    "itemType": "attachment",
                    "parentItem": "EQ123456",
                    "filename": "equilibrium-paper.pdf",
                    "contentType": "application/pdf",
                },
            },
            {
                "key": "LI123456",
                "version": 3,
                "data": {
                    "itemType": "report",
                    "title": "Lithium solvent extraction",
                    "date": "2023",
                    "abstractNote": "Selectivity and transport in lithium extraction.",
                    "tags": [{"tag": "Transport", "type": 0}],
                    "collections": ["COLL002"],
                },
            },
        ),
        collections=(
            {"key": "COLL001", "data": {"name": "ePC-SAFT Equilibrium"}},
            {"key": "COLL002", "data": {"name": "Lithium Extraction"}},
        ),
        tags=(
            {"tag": "Review", "meta": {"numItems": 1}},
            {"tag": "Transport", "meta": {"numItems": 1}},
        ),
        searches=({"key": "SEARCH1", "data": {"name": "Workflow — To Read"}},),
    )


def test_build_source_records_excludes_children_and_assigns_projects():
    records = build_source_records(snapshot())

    assert [record["zotero_key"] for record in records] == ["EQ123456", "LI123456"]
    equilibrium = records[0]
    assert equilibrium["projects"] == ["epcsaft-equilibrium"]
    assert equilibrium["attachments"][0]["key"] == "ATT12345"
    assert equilibrium["creators"] == ["Ada Lovelace"]
    assert equilibrium["year"] == "2024"


def test_materialize_search_context_and_verify(tmp_path):
    root = tmp_path / "wiki"

    dry_run = materialize_snapshot(snapshot(), root)
    assert dry_run["mode"] == "dry-run"
    assert not root.exists()

    applied = materialize_snapshot(snapshot(), root, apply=True)
    assert applied["changed"] == 2
    assert (root / "manifest.json").exists()
    assert (root / "sources/EQ123456/record.json").exists()
    source_index = (root / "sources/index.md").read_text(encoding="utf-8")
    assert "Chemical potential and phase equilibrium" in source_index
    assert "EQ123456/source.md" in source_index
    assert (root / "index.sqlite").exists()

    repeat = materialize_snapshot(snapshot(), root, apply=True)
    assert repeat["changed"] == 0
    assert repeat["unchanged"] == 2

    results = search_wiki(root, query="chemical potential", project="epcsaft-equilibrium")
    assert [result["zotero_key"] for result in results] == ["EQ123456"]
    source = source_record(root, "EQ123456")
    assert source["doi"] == "10.1234/example"
    assert source["wiki"]["brief"] is None
    assert source["wiki"]["evidence"]["available"] is False
    assert "text" not in source["wiki"]

    context = context_pack(root, project="epcsaft-equilibrium")
    assert context["sources"][0]["zotero_key"] == "EQ123456"
    assert any("Project scaffold is missing" in warning for warning in context["warnings"])

    checked = verify_wiki(root)
    assert checked["ok"] is True
    assert checked["uncited_claim_count"] == 0


def test_manifest_is_deterministic_and_stale_report_uses_top_level_versions(tmp_path):
    root = tmp_path / "wiki"
    materialize_snapshot(snapshot(), root, apply=True)
    first_manifest = (root / "manifest.json").read_text(encoding="utf-8")
    materialize_snapshot(snapshot(), root, apply=True)
    assert (root / "manifest.json").read_text(encoding="utf-8") == first_manifest

    class FakeAPI:
        def items(self):
            return [
                {"key": "EQ123456", "version": 8, "data": {"itemType": "journalArticle"}},
                {"key": "NEW12345", "version": 1, "data": {"itemType": "book"}},
                {
                    "key": "ATT12345",
                    "version": 99,
                    "data": {"itemType": "attachment", "parentItem": "EQ123456"},
                },
            ]

    stale = stale_report(root, FakeAPI())
    assert stale["stale"] is True
    assert stale["changed"] == ["EQ123456"]
    assert stale["added"] == ["NEW12345"]
    assert stale["removed"] == ["LI123456"]


def test_manifest_and_source_record_are_json_objects(tmp_path):
    root = tmp_path / "wiki"
    materialize_snapshot(snapshot(), root, apply=True)
    assert isinstance(json.loads((root / "manifest.json").read_text(encoding="utf-8")), dict)
    assert isinstance(json.loads((root / "sources/EQ123456/record.json").read_text(encoding="utf-8")), dict)


def test_evidence_passages_search_declared_companions_and_skip_pdfs(tmp_path):
    root = tmp_path / "wiki"
    materialize_snapshot(snapshot(), root, apply=True)
    bundle = root / "evidence/EQ123456"
    bundle.mkdir(parents=True)
    companion = """# Test paper

## Born term

The fitted Born diameter controls the solvation contribution.
The companion remains the source evidence for this passage.
"""
    (bundle / "paper.md").write_text(companion, encoding="utf-8")
    (bundle / "paper.pdf").write_bytes(b"%PDF-test-placeholder")
    manifest = {
        "schema_version": 1,
        "parent_zotero_key": "EQ123456",
        "citation_key": "test2024",
        "doi": "10.1234/example",
        "conversion": {"mode": "existing-zotero-companions"},
        "files": [
            {
                "role": "main_article",
                "zotero_attachment_key": "MD123456",
                "source_filename": "paper.md",
                "path": "paper.md",
                "format": "markdown",
                "sha256": hashlib.sha256(companion.encode()).hexdigest(),
            },
            {
                "role": "pdf",
                "zotero_attachment_key": "PDF12345",
                "source_filename": "paper.pdf",
                "path": "paper.pdf",
                "format": "pdf",
                "sha256": hashlib.sha256(b"%PDF-test-placeholder").hexdigest(),
            },
        ],
    }
    (bundle / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    indexed = index_wiki(root)
    assert indexed["evidence_files"] == 1
    assert indexed["evidence_chunks"] >= 1
    with sqlite3.connect(root / "index.sqlite") as connection:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(evidence_chunks)")
        }
        assert {
            "zotero_attachment_key",
            "path",
            "role",
            "content_sha256",
            "line_start",
            "line_end",
            "section",
            "text",
        } <= columns
        assert connection.execute(
            "SELECT COUNT(*) FROM evidence_chunks WHERE zotero_key = ?",
            ("EQ123456",),
        ).fetchone()[0] >= 1

    result = evidence_passages(root, "EQ123456", query="Born diameter", limit=4)

    assert result["conversion"]["mode"] == "existing-zotero-companions"
    assert result["passages"][0]["zotero_attachment_key"] == "MD123456"
    assert result["passages"][0]["section"] == "Born term"
    assert result["passages"][0]["line_start"] <= result["passages"][0]["line_end"]
    markdown_file = next(file for file in result["files"] if file["format"] == "markdown")
    pdf_file = next(file for file in result["files"] if file["format"] == "pdf")
    assert markdown_file["hash_matches"] is True
    assert markdown_file["searchable"] is True
    assert pdf_file["searchable"] is False
    assert pdf_file["passages"] == []

    hits = search_evidence_chunks(
        root,
        source_keys=["EQ123456"],
        query="Born diameter",
        limit=4,
    )
    assert hits
    assert hits[0]["zotero_attachment_key"] == "MD123456"
    assert hits[0]["hash_matches"] is True
    assert hits[0]["locator"].startswith("wiki/evidence/EQ123456/paper.md:L")

    context = context_pack(
        root,
        project="epcsaft-equilibrium",
        query="Born diameter",
        limit=4,
    )
    assert context["evidence_hits"][0]["zotero_key"] == "EQ123456"
    assert context["evidence_hits"][0]["hash_matches"] is True
    assert context["evidence_coverage"]["matched_source_count"] == 1
    assert context["evidence_coverage"]["sources_with_indexed_evidence"] == 1
    assert context["evidence_coverage"]["coverage_ratio"] == 1.0
    assert context["evidence_coverage"]["query_hit_count"] >= 1


def test_freshness_status_requires_explicit_live_comparison(tmp_path):
    root = tmp_path / "wiki"
    materialize_snapshot(snapshot(), root, apply=True)

    unchecked = freshness_status(root)
    assert unchecked["stale"] is None
    assert unchecked["live_check"]["reason"] == "not_requested"

    class FakeAPI:
        def items(self):
            return [
                {"key": "EQ123456", "version": 8, "data": {"itemType": "journalArticle"}},
                {"key": "LI123456", "version": 3, "data": {"itemType": "report"}},
            ]

    checked = freshness_status(root, FakeAPI())
    assert checked["stale"] is True
    assert checked["refresh_required"] is True
    assert checked["live_check"]["checked"] is True
    assert checked["live_check"]["changed"] == ["EQ123456"]


def _test_graph(claim_target: str) -> dict:
    titles = ["Killer Application", "Why It's Needed", "Solution", "Results", "Conclusion"]
    nodes = []
    for index, title in enumerate(titles, start=1):
        links = []
        if index == 1:
            links.append({"type": "internal", "target": claim_target, "label": "claim"})
        nodes.append(
            {
                "id": f"node_{index:03d}",
                "template": "main_topic",
                "title": title,
                "content": title,
                "children": [],
                "links": links,
                "position": {"x": 0, "y": (index - 1) * 300},
                "childrenExpanded": True,
            }
        )
    return {
        "version": "1.0.0",
        "title": "Test paper graph",
        "created": "2026-07-31T00:00:00Z",
        "modified": "2026-07-31T00:00:00Z",
        "nodes": nodes,
        "edges": [
            {
                "id": f"edge_{index:03d}",
                "source": f"node_{index:03d}",
                "target": f"node_{index + 1:03d}",
                "type": "arrow",
                "label": "next",
            }
            for index in range(1, 5)
        ],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
    }


def test_context_pack_surfaces_curated_layers_and_open_questions(tmp_path):
    root = tmp_path / "wiki"
    materialize_snapshot(snapshot(), root, apply=True)
    (root / "claims").mkdir()
    (root / "evidence/EQ123456").mkdir(parents=True)
    (root / "graphs").mkdir()
    (root / "evidence/EQ123456/README.md").write_text("# Evidence\n", encoding="utf-8")
    (root / "claims/born.md").write_text(
        """# Born term claim

- claim_id: `born-term`
- project: `epcsaft-equilibrium`
- status: source-backed
- confidence: high
- claim_type: model-equation
- zotero_key: `EQ123456`
- derived_from: `sources/EQ123456/record.json`
- locator: source abstract
- implementation_ref: `Engineering/ePC-SAFT-project/ePC-SAFT-eos/docs/designs/born.md`

## Claim

The Born term controls the modeled ion solvation contribution.

## Evidence and limits

The source discusses the Born term.

## Implementation mapping

Keep the equation tied to its model convention.
""",
        encoding="utf-8",
    )
    (root / "claims/question.md").write_text(
        """# Born interpretation question

- claim_id: `born-question`
- project: `epcsaft-equilibrium`
- status: open
- confidence: medium
- claim_type: open-question
- zotero_key: `EQ123456`
- derived_from: `sources/EQ123456/record.json`
- locator: source abstract

## Claim

Can the fitted Born quantity be interpreted physically?

## Evidence and limits

The source does not settle the question.
""",
        encoding="utf-8",
    )
    (root / "graphs/test.nodegraph.json").write_text(
        json.dumps(_test_graph("../claims/born.md")),
        encoding="utf-8",
    )

    context = context_pack(
        root,
        project="epcsaft-equilibrium",
        query="Born",
        limit=8,
    )

    assert [claim["claim_id"] for claim in context["claims"]] == [
        "born-term",
        "born-question",
    ]
    assert context["graphs"][0]["path"] == "wiki/graphs/test.nodegraph.json"
    assert context["evidence"][0]["zotero_key"] == "EQ123456"
    assert context["implementation"][0]["ref"].endswith("/docs/designs/born.md")
    assert {question["claim_id"] for question in context["open_questions"] if question["kind"] == "claim"} == {
        "born-question"
    }
    assert verify_wiki(root)["ok"] is True


def test_triage_index_keeps_all_sources_and_exposes_unbriefed_relevant_queue(tmp_path):
    root = tmp_path / "wiki"
    materialize_snapshot(snapshot(), root, apply=True)
    (root / "papers").mkdir()
    (root / "papers/EQ123456.md").write_text(
        "# Test brief\n\n- Zotero key: EQ123456\n",
        encoding="utf-8",
    )

    index_wiki(root)

    all_entries = triage_wiki(root, limit=10)
    assert all_entries["total"] == 2
    by_key = {entry["zotero_key"]: entry for entry in all_entries["entries"]}
    assert by_key["EQ123456"]["status"] == "briefed"
    assert by_key["LI123456"]["status"] == "candidate"
    assert all_entries["queue_counts"]["unbriefed_relevant"] == 1

    queue = triage_wiki(root, queue="unbriefed_relevant", limit=10)
    assert queue["total"] == 1
    assert queue["entries"][0]["zotero_key"] == "LI123456"
    assert queue["entries"][0]["queue_reason"]


def test_classification_layer_separates_suggestions_from_reviewable_assignments(tmp_path):
    root = tmp_path / "wiki"
    materialize_snapshot(snapshot(), root, apply=True)

    triage = triage_wiki(root, domain="epcsaft", limit=10)
    suggested = {entry["zotero_key"]: entry for entry in triage["entries"]}
    assert suggested["EQ123456"]["classification"]["state"] == "unassigned"
    assert "epcsaft" in suggested["EQ123456"]["suggested_domains"]
    assert suggested["EQ123456"]["domains"] == []
    needs_classification = triage_wiki(root, queue="needs_classification", limit=10)
    assert "EQ123456" in {
        entry["zotero_key"] for entry in needs_classification["entries"]
    }

    dry_run = classify_source(
        root,
        "EQ123456",
        relevance="relevant",
        domains=["epcsaft"],
        research_threads=["phase-and-chemical-equilibrium"],
        reason="The source is directly relevant to the ePC-SAFT equilibrium view.",
        state="accepted",
        reviewer="test",
    )
    assert dry_run["mode"] == "dry-run"
    assert not (root / "curation/source-assignments.json").exists()

    applied = classify_source(
        root,
        "EQ123456",
        relevance="relevant",
        domains=["epcsaft"],
        research_threads=["phase-and-chemical-equilibrium"],
        reason="The source is directly relevant to the ePC-SAFT equilibrium view.",
        state="accepted",
        reviewer="test",
        apply=True,
    )
    assert applied["mode"] == "apply"
    assert applied["zotero_mutation"] is False

    assigned = triage_wiki(
        root,
        domain="epcsaft",
        assigned_only=True,
        classification_state="accepted",
        limit=10,
    )
    assert [entry["zotero_key"] for entry in assigned["entries"]] == ["EQ123456"]
    assert assigned["entries"][0]["classification"]["domains"] == ["epcsaft"]
    assert assigned["entries"][0]["relevance_basis"] == "curated-assignment"
    assert assigned["queue_counts"]["needs_classification"] == 1


def test_verify_rejects_malformed_claim_and_nodegraph(tmp_path):
    root = tmp_path / "wiki"
    materialize_snapshot(snapshot(), root, apply=True)
    (root / "claims").mkdir()
    (root / "claims/broken.md").write_text(
        "# Broken claim\n\n## Claim\n\nMissing provenance metadata.\n",
        encoding="utf-8",
    )
    (root / "graphs").mkdir()
    (root / "graphs/broken.nodegraph.json").write_text(
        json.dumps({"version": "1.0.0", "title": "Broken", "nodes": [], "edges": []}),
        encoding="utf-8",
    )

    checked = verify_wiki(root)

    assert checked["ok"] is False
    assert checked["uncited_claim_count"] == 1
    assert any("missing required metadata" in error for error in checked["errors"])
    assert any("exactly five main_topic" in error for error in checked["errors"])
