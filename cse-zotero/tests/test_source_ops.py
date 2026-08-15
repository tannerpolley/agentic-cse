from __future__ import annotations

from pathlib import Path

from zotero_companion.source_ops import attachment_path, search_sources, source_children


class FakeAPI:
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.calls = []

    def get(self, path, params=None):
        self.calls.append((path, params))
        if path.endswith("/children"):
            return [{"key": "PDF123", "data": {"contentType": "application/pdf"}}]
        return [{"key": "PARENT1", "data": {"title": "Crank Nicolson"}}]

    def get_text(self, path, params=None):
        self.calls.append((path, params))
        return self.file_path.as_uri()


def test_live_source_commands_are_read_only_and_keyed(tmp_path):
    attachment = tmp_path / "paper.pdf"
    attachment.write_bytes(b"%PDF-test")
    api = FakeAPI(attachment)

    searched = search_sources("Crank", api=api)
    children = source_children("PARENT1", api=api)
    resolved = attachment_path("PDF123", api=api)

    assert searched["read_only"] is True
    assert searched["items"][0]["key"] == "PARENT1"
    assert children["parent_key"] == "PARENT1"
    assert resolved["attachment_key"] == "PDF123"
    assert resolved["path"] == str(attachment.resolve())
