import json
from pathlib import Path
from urllib.parse import unquote

from zotero_companion.evidence_sync import sync_evidence
from zotero_companion.wiki import WikiSnapshot, materialize_snapshot


class CompanionAPI:
    def __init__(self, paths: dict[str, str]):
        self.paths = paths
        self.calls: list[str] = []

    def get(self, path: str):
        self.calls.append(path)
        key = unquote(path.split("/items/", 1)[1].split("/file/", 1)[0])
        return self.paths[key]


def _snapshot() -> WikiSnapshot:
    return WikiSnapshot(
        items=(
            {
                "key": "PARENT123",
                "version": 1,
                "data": {
                    "itemType": "journalArticle",
                    "title": "Companion-backed source",
                    "citationKey": "Companion2024",
                    "DOI": "10.1234/companion",
                },
            },
            {
                "key": "MD123456",
                "version": 1,
                "data": {
                    "itemType": "attachment",
                    "parentItem": "PARENT123",
                    "filename": "article.md",
                    "contentType": "text/markdown",
                },
            },
            {
                "key": "MM123456",
                "version": 1,
                "data": {
                    "itemType": "attachment",
                    "parentItem": "PARENT123",
                    "filename": "supporting-information.mmd",
                    "contentType": "text/markdown",
                },
            },
            {
                "key": "PDF123456",
                "version": 1,
                "data": {
                    "itemType": "attachment",
                    "parentItem": "PARENT123",
                    "filename": "article.pdf",
                    "contentType": "application/pdf",
                },
            },
        ),
        collections=(),
        tags=(),
        searches=(),
    )


def _materialized(tmp_path: Path):
    root = tmp_path / "wiki"
    materialize_snapshot(_snapshot(), root, apply=True)
    article = tmp_path / "article.md"
    supporting = tmp_path / "supporting-information.mmd"
    pdf = tmp_path / "article.pdf"
    article.write_bytes(b"# article\n\nEquation source.\n")
    supporting.write_bytes(b"# SI\n\nMathpix equation source.\n")
    pdf.write_bytes(b"%PDF must never be read by this sync\n")
    api = CompanionAPI(
        {
            "MD123456": article.as_uri(),
            "MM123456": supporting.as_uri(),
            "PDF123456": pdf.as_uri(),
        }
    )
    return root, api, article, supporting, pdf


def test_dry_run_discovers_only_markdown_companions(tmp_path: Path):
    root, api, article, supporting, _pdf = _materialized(tmp_path)

    result = sync_evidence(root, api=api)

    assert result["mode"] == "dry-run"
    assert result["candidate_count"] == 2
    assert result["actions"] == {"copy": 2}
    assert result["pdf_conversion"] is False
    assert not (root / "evidence").exists()
    assert all("PDF123456" not in call for call in api.calls)
    assert article.read_bytes().startswith(b"# article")
    assert supporting.read_bytes().startswith(b"# SI")


def test_apply_copies_exact_companions_and_indexes_them(tmp_path: Path):
    root, api, article, supporting, _pdf = _materialized(tmp_path)

    result = sync_evidence(root, api=api, apply=True)

    assert result["applied_count"] == 2
    assert (root / "evidence/PARENT123/article.md").read_bytes() == article.read_bytes()
    assert (
        root / "evidence/PARENT123/supporting-information.mmd"
    ).read_bytes() == supporting.read_bytes()
    manifest = json.loads(
        (root / "evidence/PARENT123/manifest.json").read_text(encoding="utf-8")
    )
    assert {entry["zotero_attachment_key"] for entry in manifest["files"]} == {
        "MD123456",
        "MM123456",
    }
    assert manifest["conversion"]["converter"] == "none"
    assert manifest["conversion"]["pdf_conversion"] == "forbidden-when-companion-exists"
    assert (root / "evidence/PARENT123/README.md").exists()
    assert result["index"]["evidence_files"] == 2
    assert (root / "sources/index.md").exists()


def test_unsafe_remote_url_is_refused_without_exposing_it(tmp_path: Path):
    root, api, _article, _supporting, _pdf = _materialized(tmp_path)
    api.paths["MD123456"] = "https://private.example/secret/article.md"

    result = sync_evidence(root, api=api)
    serialized = json.dumps(result)

    assert result["actions"] == {"copy": 1, "unavailable": 1}
    assert "private.example" not in serialized
    assert not (root / "evidence").exists()


def test_changed_companion_is_a_conflict_and_is_not_overwritten(tmp_path: Path):
    root, api, article, _supporting, _pdf = _materialized(tmp_path)
    sync_evidence(root, api=api, apply=True)
    original = (root / "evidence/PARENT123/article.md").read_bytes()
    article.write_bytes(b"# changed after first sync\n")

    result = sync_evidence(root, api=api, apply=True)

    assert result["actions"]["conflict"] == 1
    assert (root / "evidence/PARENT123/article.md").read_bytes() == original


def test_linked_file_uses_path_basename_when_filename_is_missing(tmp_path: Path):
    root = tmp_path / "wiki"
    linked = tmp_path / "linked-companion.mmd"
    linked.write_bytes(b"# linked companion\n")
    snapshot = WikiSnapshot(
        items=(
            {
                "key": "PARENT123",
                "version": 1,
                "data": {"itemType": "journalArticle", "title": "Linked source"},
            },
            {
                "key": "LINK123456",
                "version": 1,
                "data": {
                    "itemType": "attachment",
                    "parentItem": "PARENT123",
                    "linkMode": "linked_file",
                    "path": str(linked),
                    "title": linked.name,
                    "contentType": "text/markdown",
                },
            },
        ),
        collections=(),
        tags=(),
        searches=(),
    )
    materialize_snapshot(snapshot, root, apply=True)
    api = CompanionAPI({"LINK123456": linked.as_uri()})

    result = sync_evidence(root, api=api, apply=True)

    assert result["candidate_count"] == 1
    assert result["applied_count"] == 1
    record = json.loads(
        (root / "sources/PARENT123/record.json").read_text(encoding="utf-8")
    )
    assert record["attachments"][0]["filename"] == linked.name
    assert (root / "evidence/PARENT123" / linked.name).read_bytes() == linked.read_bytes()


def test_companion_linked_in_place_is_adopted_and_different_file_conflicts(tmp_path: Path):
    root, api, _article, supporting, _pdf = _materialized(tmp_path)
    bundle = root / "evidence/PARENT123"
    bundle.mkdir(parents=True)
    in_place = bundle / "article.md"
    in_place.write_bytes(b"# article linked in place\n")
    api.paths["MD123456"] = in_place.as_uri()
    (bundle / "supporting-information.mmd").write_bytes(b"# unrelated file\n")

    result = sync_evidence(root, api=api, apply=True)

    assert result["actions"] == {"adopt": 1, "conflict": 1}
    assert result["applied_attachment_keys"] == ["MD123456"]
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    assert [entry["zotero_attachment_key"] for entry in manifest["files"]] == ["MD123456"]
    assert in_place.read_bytes() == b"# article linked in place\n"
    assert (bundle / "supporting-information.mmd").read_bytes() == b"# unrelated file\n"
    assert supporting.read_bytes().startswith(b"# SI")
    assert sync_evidence(root, api=api)["actions"] == {"conflict": 1, "unchanged": 1}


def test_sync_promotes_pending_attachment_without_duplicate_entry(tmp_path):
    import hashlib
    root, api, article, supporting, _pdf = _materialized(tmp_path)
    bundle = root / 'evidence/PARENT123'
    bundle.mkdir(parents=True)
    (bundle / 'article.md').write_bytes(article.read_bytes())
    (bundle / 'manifest.json').write_text(json.dumps({
        'schema_version': 1, 'parent_zotero_key': 'PARENT123',
        'files': [{'path': 'article.md', 'status': 'pending_attachment',
                   'sha256': hashlib.sha256(article.read_bytes()).hexdigest()}],
    }))
    plan = sync_evidence(root, api=api)
    assert plan['actions'] == {'adopt': 1, 'copy': 1}
    sync_evidence(root, api=api, apply=True)
    entries = json.loads((bundle / 'manifest.json').read_text())['files']
    article_entries = [entry for entry in entries if entry['path'] == 'article.md']
    assert len(article_entries) == 1
    assert article_entries[0]['zotero_attachment_key'] == 'MD123456'
    assert 'status' not in article_entries[0]
