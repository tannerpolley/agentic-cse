import hashlib
import json
from pathlib import Path
from urllib.parse import unquote

from zotero_companion.local_api import LocalAPIError
from zotero_companion.maintenance import _overlap_lock, maintain_wiki
from zotero_companion.wiki import WikiSnapshot, materialize_snapshot, search_evidence_chunks


def _snapshot(*, version: int = 1, title: str = "Source", attachments=()) -> WikiSnapshot:
    items = [
        {
            "key": "PARENT123",
            "version": version,
            "data": {
                "itemType": "journalArticle",
                "title": title,
                "citationKey": "source2024",
            },
        }
    ]
    items.extend(
        {
            "key": key,
            "version": 1,
            "data": {
                "itemType": "attachment",
                "parentItem": "PARENT123",
                "filename": filename,
                "contentType": content_type,
            },
        }
        for key, filename, content_type in attachments
    )
    return WikiSnapshot(
        items=tuple(items),
        collections=(),
        tags=(),
        searches=(),
    )


class MaintenanceAPI:
    def __init__(self, snapshot: WikiSnapshot, paths: dict[str, Path] | None = None):
        self.snapshot = snapshot
        self.paths = paths or {}
        self.calls: list[str] = []

    def items(self, *, top_level=False):
        self.calls.append("items:top" if top_level else "items:all")
        return list(self.snapshot.items)

    def collections(self):
        return list(self.snapshot.collections)

    def tags(self):
        return list(self.snapshot.tags)

    def searches(self):
        return list(self.snapshot.searches)

    def get_text(self, path: str):
        key = unquote(path.split("/items/", 1)[1].split("/file/", 1)[0])
        self.calls.append(f"attachment:{key}")
        return self.paths[key].as_uri()


class UnavailableAPI:
    def items(self, **_kwargs):
        raise LocalAPIError("Zotero local API is unavailable")


def test_changed_source_refresh_reports_counts(tmp_path: Path):
    root = tmp_path / "wiki"
    materialize_snapshot(_snapshot(), root, apply=True)
    api = MaintenanceAPI(_snapshot(version=2, title="Updated source"))

    first = maintain_wiki(root, api=api, apply=True)

    assert first["ok"] is True
    assert first["refresh"]["changed"] == 1
    assert set(first) == {"ok", "status", "mode", "refresh", "evidence", "verify", "projects", "errors"}
    assert api.calls.count("items:all") == 1

    repeat = maintain_wiki(root, api=api, apply=True)

    assert repeat["ok"] is True
    assert repeat["refresh"]["changed"] == 0


def test_new_existing_markdown_attachment_is_resolved_and_indexed(tmp_path: Path):
    root = tmp_path / "wiki"
    materialize_snapshot(_snapshot(), root, apply=True)
    companion = tmp_path / "article.md"
    companion.write_text("# Evidence\n\nFresh companion text.\n", encoding="utf-8")
    api = MaintenanceAPI(
        _snapshot(
            version=2,
            attachments=(("MD123456", "article.md", "text/markdown"),),
        ),
        {"MD123456": companion},
    )

    result = maintain_wiki(root, api=api, apply=True)

    assert result["ok"] is True
    assert result["evidence"]["candidate_count"] == 1
    assert result["evidence"]["applied_count"] == 1
    assert result["evidence"]["issues"] == []
    assert "candidates" not in result["evidence"]
    assert (root / "evidence/PARENT123/article.md").read_text(encoding="utf-8") == companion.read_text(
        encoding="utf-8"
    )
    hits = search_evidence_chunks(root, source_keys=["PARENT123"], query="Fresh companion")
    assert hits[0]["zotero_attachment_key"] == "MD123456"
    assert "attachment:MD123456" in api.calls


def test_attachment_only_change_is_reported_as_stale(tmp_path: Path):
    root = tmp_path / "wiki"
    materialize_snapshot(_snapshot(), root, apply=True)
    companion = tmp_path / "article.md"
    companion.write_text("# Evidence\n", encoding="utf-8")
    api = MaintenanceAPI(
        _snapshot(attachments=(("MD123456", "article.md", "text/markdown"),)),
        {"MD123456": companion},
    )

    result = maintain_wiki(root, api=api, apply=True)

    assert result["refresh"]["changed"] == 1


def test_conflicting_evidence_is_reported_and_not_overwritten(tmp_path: Path):
    root = tmp_path / "wiki"
    companion = tmp_path / "article.md"
    companion.write_text("# Original\n", encoding="utf-8")
    api = MaintenanceAPI(
        _snapshot(attachments=(("MD123456", "article.md", "text/markdown"),)),
        {"MD123456": companion},
    )
    maintain_wiki(root, api=api, apply=True)
    companion.write_text("# Changed outside the wiki\n", encoding="utf-8")

    result = maintain_wiki(root, api=api, apply=True)

    assert result["ok"] is False
    assert result["evidence"]["issues"][0]["action"] == "conflict"
    assert result["evidence"]["issues"][0]["zotero_attachment_key"] == "MD123456"
    assert any("Evidence conflict for MD123456" in error for error in result["errors"])


def test_unavailable_zotero_returns_nonzero_safe_result(tmp_path: Path):
    root = tmp_path / "wiki"
    materialize_snapshot(_snapshot(), root, apply=True)
    before = (root / "sources/PARENT123/record.json").read_bytes()

    result = maintain_wiki(root, api=UnavailableAPI(), apply=True)

    assert result["ok"] is False
    assert result["status"] == "unavailable"
    assert result["reason"] == "zotero_unavailable"
    assert (root / "sources/PARENT123/record.json").read_bytes() == before


def test_overlap_is_nonblocking_and_does_not_call_zotero(tmp_path: Path):
    root = tmp_path / "wiki"
    api = UnavailableAPI()

    with _overlap_lock(root) as acquired:
        assert acquired is True
        result = maintain_wiki(root, api=api, apply=True)

    assert result["ok"] is True
    assert result["status"] == "skipped_overlap"


def test_removed_source_dir_and_evidence_survive_repeated_maintenance(tmp_path: Path):
    root = tmp_path / "wiki"
    initial = _snapshot()
    secondary = {
        "key": "REMOVED123",
        "version": 1,
        "data": {
            "itemType": "book",
            "title": "Removed source",
        },
    }
    initial = WikiSnapshot(
        items=initial.items + (secondary,),
        collections=initial.collections,
        tags=initial.tags,
        searches=initial.searches,
    )
    materialize_snapshot(initial, root, apply=True)
    bundle = root / "evidence/REMOVED123"
    bundle.mkdir(parents=True)
    evidence_text = "# Retained evidence\n\nEvidence from the removed source.\n"
    (bundle / "paper.md").write_text(evidence_text, encoding="utf-8")
    (bundle / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "parent_zotero_key": "REMOVED123",
                "files": [
                    {
                        "path": "paper.md",
                        "format": "markdown",
                        "role": "main_article",
                        "zotero_attachment_key": "MD123456",
                        "source_filename": "paper.md",
                        "sha256": hashlib.sha256(evidence_text.encode()).hexdigest(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    api = MaintenanceAPI(_snapshot())

    first = maintain_wiki(root, api=api, apply=True)
    repeat = maintain_wiki(root, api=api, apply=True)

    assert first["verify"]["ok"] is True
    assert repeat["verify"]["ok"] is True
    assert repeat["status"] == "ok"
    assert (root / "sources/REMOVED123/record.json").exists()
    assert search_evidence_chunks(
        root,
        source_keys=["REMOVED123"],
        query="removed source",
    )
