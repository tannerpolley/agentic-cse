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

    def items(self, *, top_level=False):
        self.calls.append(("items", {"top_level": top_level}))
        return []


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


class DoiFallbackAPI(FakeAPI):
    def get(self, path, params=None):
        self.calls.append((path, params))
        return []

    def items(self, *, top_level=False):
        self.calls.append(("items", {"top_level": top_level}))
        return [
            {
                "key": "PARENT1",
                "data": {
                    "DOI": "10.1017/S0305004100023197",
                    "title": "A practical method",
                },
            }
        ]


def test_doi_search_normalizes_common_forms_and_uses_exact_field_fallback(tmp_path):
    for query in (
        "https://doi.org/10.1017/S0305004100023197.",
        "doi:10.1017/S0305004100023197",
        "<10.1017/S0305004100023197>",
    ):
        api = DoiFallbackAPI(tmp_path / "paper.pdf")

        searched = search_sources(query, api=api)

        assert searched["normalized_query"] == "10.1017/s0305004100023197"
        assert searched["strategy"] == "exact-doi-field"
        assert searched["items"][0]["key"] == "PARENT1"
        assert searched["read_only"] is True
        assert api.calls[0][1]["q"] == "10.1017/s0305004100023197"
        assert api.calls[-1] == ("items", {"top_level": True})


def test_title_search_keeps_the_normal_zotero_query_strategy(tmp_path):
    api = FakeAPI(tmp_path / "paper.pdf")

    searched = search_sources("Crank", api=api)

    assert searched["strategy"] == "zotero-q"
    assert searched["queries_tried"] == ["Crank"]
    assert all(call[0] != "items" for call in api.calls)
