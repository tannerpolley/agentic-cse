"""Stable JSON-facing Zotero source and attachment operations."""

from __future__ import annotations

import urllib.parse
from pathlib import Path
from typing import Any

from .local_api import LocalAPIError, ZoteroLocalAPI


def search_sources(query: str, *, limit: int = 25, api: ZoteroLocalAPI | None = None) -> dict[str, Any]:
    query = query.strip()
    if not query:
        raise ValueError("source query must not be empty")
    api = api or ZoteroLocalAPI()
    items = api.get(
        "/api/users/0/items/top",
        {"q": query, "limit": max(1, min(limit, 100))},
    )
    if not isinstance(items, list):
        raise LocalAPIError("Zotero source search returned a non-list response")
    return {"ok": True, "read_only": True, "query": query, "count": len(items), "items": items}


def source_children(parent_key: str, *, api: ZoteroLocalAPI | None = None) -> dict[str, Any]:
    parent_key = parent_key.strip()
    if not parent_key:
        raise ValueError("parent Zotero key must not be empty")
    api = api or ZoteroLocalAPI()
    path = f"/api/users/0/items/{urllib.parse.quote(parent_key, safe='')}/children"
    items = api.get(path, {"limit": 100})
    if not isinstance(items, list):
        raise LocalAPIError("Zotero child lookup returned a non-list response")
    return {"ok": True, "read_only": True, "parent_key": parent_key, "count": len(items), "items": items}


def attachment_path(attachment_key: str, *, api: ZoteroLocalAPI | None = None) -> dict[str, Any]:
    attachment_key = attachment_key.strip()
    if not attachment_key:
        raise ValueError("attachment Zotero key must not be empty")
    api = api or ZoteroLocalAPI()
    endpoint = f"/api/users/0/items/{urllib.parse.quote(attachment_key, safe='')}/file/view/url"
    value = api.get_text(endpoint).strip()
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme != "file":
        raise LocalAPIError("Zotero attachment did not resolve to a local file URL")
    path = Path(urllib.parse.unquote(parsed.path)).resolve()
    if not path.is_file():
        raise LocalAPIError(f"Zotero attachment file is unavailable: {path}")
    return {
        "ok": True,
        "read_only": True,
        "attachment_key": attachment_key,
        "path": str(path),
        "bytes": path.stat().st_size,
    }
