from zotero_companion.report import summarize_items


def item(item_type, filename="", tags=()):
    return {
        "data": {
            "itemType": item_type,
            "filename": filename,
            "tags": [{"tag": tag, "type": tag_type} for tag, tag_type in tags],
        }
    }


def test_summarize_items_separates_markdown_and_tag_types():
    payload = summarize_items(
        [
            item("journalArticle", tags=[("status:to-read", 0)]),
            item("attachment", "paper.mmd", tags=[("publisher-keyword", 1)]),
            item("attachment", "paper.md"),
            item("attachment", "paper.pdf"),
        ]
    )

    assert payload["items"] == 4
    assert payload["attachments"] == 3
    assert payload["markdown_attachments"] == 2
    assert payload["markdown_extensions"] == {".mmd": 1, ".md": 1}
    assert payload["automatic_tag_assignments"] == 1
    assert payload["manual_tag_assignments"] == 1

