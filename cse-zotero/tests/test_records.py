import json
import hashlib
from pathlib import Path

from zotero_companion.records import (
    global_context,
    lineage,
    lint_records,
    load_records,
    record_lookup,
    search_records,
)
from zotero_companion.wiki import source_record
from corpus_paths import REGISTRY_ROOT, WIKI_ROOT


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_context_registry_paths_resolve_from_corpus_not_cwd(tmp_path, monkeypatch):
    from test_scientific_data import _registry_fixture
    from test_wiki import snapshot
    from zotero_companion.wiki import context_pack, materialize_snapshot

    registry, _ = _registry_fixture(tmp_path)
    wiki = tmp_path / "wiki"
    materialize_snapshot(snapshot(), wiki, apply=True)
    elsewhere = tmp_path / "unrelated"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    for result in [
        global_context(wiki, query="MEA", registry_root="source/registry"),
        context_pack(wiki, project="epcsaft-equilibrium", query="MEA", registry_root="source/registry"),
    ]:
        assert result["data"]["registry_root"] == str(registry.resolve())
        assert result["data"]["count"] == 1


def test_explicit_corpus_cli_does_not_load_another_corpus_config(tmp_path, monkeypatch, capsys):
    from test_wiki import snapshot
    from zotero_companion import cli
    from zotero_companion.wiki import materialize_snapshot

    wiki = tmp_path / "wiki"
    materialize_snapshot(snapshot(), wiki, apply=True)
    def unexpected_config():
        raise AssertionError("Explicit wiki must not load the user's other corpus")
    monkeypatch.setattr(cli, "load_config", unexpected_config)
    monkeypatch.setattr(cli, "ZoteroLocalAPI", lambda: object())
    monkeypatch.setattr("sys.argv", ["cse-zotero", "wiki-context", "--global",
                                  "--wiki-root", str(wiki), "--query", "MEA", "--json"])
    assert cli.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert str(tmp_path / "data") in result["data"]["warnings"][0]


def test_current_typed_records_and_lineage_are_auditable():
    root = WIKI_ROOT
    checked = lint_records(
        root,
        registry_root=REGISTRY_ROOT,
    )

    assert checked["ok"] is True
    assert checked["record_count"] >= 47
    assert checked["relation_count"] >= 42
    assert checked["record_types"]["equation"] >= 12

    record = record_lookup(root, "equation:figiel-born-solvation-shell")
    assert record["provenance"]["sources"][0]["zotero_key"] == "YEENX35P"
    assert record["provenance"]["sources"][0]["attachment_key"] == "2M74BKJG"

    held = record_lookup(root, "paper:held-2014")
    assert held["provenance"]["sources"][0]["zotero_key"] == "3DIW87Q5"
    assert record_lookup(root, "workflow:ascani-distributed-ion-flash")["record_type"] == "workflow"

    trace = lineage(
        root,
        "dataset:hamer-1972-aqueous-coefficients",
        registry_root=REGISTRY_ROOT,
    )
    upstream_ids = {entry["record_id"] for entry in trace["upstream"]}
    assert "paper:hamer-1972" in upstream_ids
    assert "equation:hamer-excess-gibbs-bridge" in upstream_ids
    assert trace["read_only"] is True

    downstream = lineage(
        root,
        "paper:hamer-1972",
        direction="downstream",
        registry_root=REGISTRY_ROOT,
    )
    assert "dataset:hamer-1972-aqueous-coefficients" in {
        entry["record_id"] for entry in downstream["downstream"]
    }


def test_global_agent_context_exposes_the_whole_corpus_and_curated_matches():
    context = global_context(
        WIKI_ROOT,
        query="Born",
        limit=5,
        registry_root=REGISTRY_ROOT,
    )

    assert context["scope"] == "global"
    assert context["read_only"] is True
    assert context["source_inventory"]["source_count"] >= 378
    assert context["source_inventory"]["evidence_file_count"] >= 97
    assert context["source_inventory"]["evidence_chunk_count"] >= 5256
    assert any(
        record["record_id"] == "equation:figiel-born-solvation-shell"
        for record in context["records"]["matches"]
    )
    assert "YEENX35P" in context["matched_source_keys"]
    assert context["briefs"]
    assert context["evidence_hits"]
    assert context["evidence_coverage"]["sources_with_indexed_evidence"] >= 1
    assert context["evidence_coverage"]["coverage_ratio"] > 0
    assert all(hit["hash_matches"] is True for hit in context["evidence_hits"])
    assert context["coverage"]["read_only"] is True
    assert context["health"]["read_only"] is True


def test_global_context_searches_evidence_when_metadata_does_not_match(tmp_path):
    root = tmp_path / "wiki"
    from test_wiki import snapshot

    from zotero_companion.wiki import index_wiki, materialize_snapshot

    materialize_snapshot(snapshot(), root, apply=True)
    bundle = root / "evidence/EQ123456"
    bundle.mkdir(parents=True)
    companion = "# Evidence\n\nThe only-evidence phrase appears here.\n"
    (bundle / "paper.md").write_text(companion, encoding="utf-8")
    (bundle / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "parent_zotero_key": "EQ123456",
                "files": [
                    {
                        "role": "main_article",
                        "zotero_attachment_key": "MD123456",
                        "source_filename": "paper.md",
                        "path": "paper.md",
                        "format": "markdown",
                        "sha256": hashlib.sha256(companion.encode()).hexdigest(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    index_wiki(root)

    context = global_context(root, query="only-evidence phrase", limit=2)

    assert context["evidence_hits"][0]["zotero_key"] == "EQ123456"
    assert "EQ123456" in context["matched_source_keys"]


def test_global_context_accepts_an_explicit_read_only_freshness_probe():
    class FakeAPI:
        def items(self):
            return []

    context = global_context(WIKI_ROOT, query="Born", api=FakeAPI())

    assert context["freshness"]["live_check"]["checked"] is True
    assert context["freshness"]["live_check"]["available"] is True
    assert "readiness" not in context
    assert context["read_only"] is True


def test_global_context_exposes_resolved_registry_packets():
    context = global_context(
        WIKI_ROOT,
        query="MEA",
        limit=8,
        registry_root=REGISTRY_ROOT,
    )

    assert context["data"]["read_only"] is True
    assert context["data"]["count"] == 8
    assert all(
        result["resources"][0]["path"].startswith(str(REGISTRY_ROOT.resolve()))
        for result in context["data"]["results"]
    )


def test_hamer_companion_is_exactly_the_declared_existing_zotero_file():
    manifest = json.loads(
        (WIKI_ROOT / "evidence/28NPJ5H6/manifest.json").read_text(encoding="utf-8")
    )
    companion = WIKI_ROOT / "evidence/28NPJ5H6/Hamer1972.md"
    import hashlib

    assert manifest["conversion"]["converter"] == "none"
    assert manifest["files"][0]["zotero_attachment_key"] == "VYE43TLN"
    assert hashlib.sha256(companion.read_bytes()).hexdigest() == manifest["files"][0]["sha256"]


def test_source_lookup_exposes_brief_and_companion_routes_without_pdf_text():
    source = source_record(WIKI_ROOT, "YEENX35P")
    metadata = source["wiki"]

    assert metadata["brief"]["path"] == "wiki/papers/Figiel2025.md"
    assert metadata["evidence"]["available"] is True
    assert set(metadata["evidence"]["companion_attachment_keys"]) == {
        "2M74BKJG",
        "D5NILP7Y",
    }
    assert all("text" not in item for item in metadata["evidence"]["files"])
    assert all(item["searchable"] for item in metadata["evidence"]["files"])


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
    matches = search_records(WIKI_ROOT, query="Born-provider", limit=10)
    assert [record["record_id"] for record in matches] == [
        "implementation:epcsaft-born-provider",
    ]


def test_agent_task_contract_is_bounded_and_explicit():
    tasks = json.loads((REPO_ROOT / "benchmarks/agent_tasks.json").read_text(encoding="utf-8"))

    assert len(tasks) >= 20
    assert all(task["source_keys"] for task in tasks)
    assert all(task["expected_record_id"] for task in tasks)
    assert all(task["min_evidence_hits"] >= 1 for task in tasks)


def test_priority_model_records_resolve_to_typed_records():
    priority = json.loads(
        (WIKI_ROOT / "curation/model-driving-records.json").read_text(
            encoding="utf-8"
        )
    )
    record_ids = {record["record_id"] for record in load_records(WIKI_ROOT)}

    assert len(priority["records"]) >= 12
    assert all(item["record_id"] in record_ids for item in priority["records"])
    assert all(item["source_keys"] and item["why"] for item in priority["records"])
