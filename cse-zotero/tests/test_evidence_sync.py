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
