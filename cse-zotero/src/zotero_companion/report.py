"""Pure inventory/report functions for CSE Zotero dry runs."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any


def summarize_items(items: Iterable[dict[str, Any]]) -> dict[str, Any]:
    items = list(items)
    attachments = [item for item in items if item.get("data", {}).get("itemType") == "attachment"]
    conversions = [
        item
        for item in attachments
        if Path(item.get("data", {}).get("filename", "")).suffix.lower() in {".md", ".mmd"}
    ]
    tag_counts: Counter[str] = Counter()
    automatic_tag_assignments = 0
    manual_tag_assignments = 0
    for item in items:
        for tag in item.get("data", {}).get("tags", []):
            name = tag.get("tag")
            if not name:
                continue
            tag_counts[name] += 1
            if tag.get("type") == 1:
                automatic_tag_assignments += 1
            else:
                manual_tag_assignments += 1
    return {
        "items": len(items),
        "attachments": len(attachments),
        "markdown_attachments": len(conversions),
        "markdown_extensions": dict(
            Counter(Path(item["data"]["filename"]).suffix.lower() for item in conversions)
        ),
        "distinct_tags": len(tag_counts),
        "tag_assignments": sum(tag_counts.values()),
        "automatic_tag_assignments": automatic_tag_assignments,
        "manual_tag_assignments": manual_tag_assignments,
    }


def audit_payload(api: Any) -> dict[str, Any]:
    """Build a JSON-serializable read-only audit payload from an API client."""
    items = api.items()
    return {
        "top_level_items": len(api.items(top_level=True)),
        "collections": len(api.collections()),
        "tags_endpoint_count": len(api.tags()),
        "saved_searches": len(api.searches()),
        **summarize_items(items),
    }
