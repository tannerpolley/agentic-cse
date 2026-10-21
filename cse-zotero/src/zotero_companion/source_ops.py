"""Stable JSON-facing Zotero source and attachment operations."""

from __future__ import annotations

import urllib.parse
import re
from pathlib import Path
from typing import Any

from .local_api import LocalAPIError, ZoteroLocalAPI


_DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", flags=re.IGNORECASE)


def _normalize_doi(value: str) -> str | None:
    """Return a canonical DOI for search, or ``None`` for ordinary text."""
    candidate = value.strip().strip("<>")
    candidate = re.sub(r"^doi:\s*", "", candidate, flags=re.IGNORECASE)
    candidate = re.sub(
        r"^https?://(?:dx\.)?doi\.org/",
        "",
        candidate,
        flags=re.IGNORECASE,
    )
    candidate = candidate.rstrip(".,;:)]}")
    return candidate.casefold() if _DOI_RE.fullmatch(candidate) else None


def _doi_matches(item: Any, normalized_doi: str) -> bool:
    if not isinstance(item, dict):
        return False
    data = item.get("data", item)
    if not isinstance(data, dict):
        return False
    item_doi = _normalize_doi(str(data.get("DOI") or data.get("doi") or ""))
    return item_doi == normalized_doi


def search_sources(query: str, *, limit: int = 25, api: ZoteroLocalAPI | None = None) -> dict[str, Any]:
    query = query.strip()
    if not query:
        raise ValueError("source query must not be empty")
    api = api or ZoteroLocalAPI()
    normalized_doi = _normalize_doi(query)
    search_query = normalized_doi or query
    items = api.get(
        "/api/users/0/items/top",
        {"q": search_query, "limit": max(1, min(limit, 100))},
    )
    if not isinstance(items, list):
        raise LocalAPIError("Zotero source search returned a non-list response")
    if items or normalized_doi is None:
        return {
            "ok": True,
            "read_only": True,
            "query": query,
            "count": len(items),
            "items": items,
            **({"strategy": "zotero-q", "queries_tried": [search_query]} if normalized_doi is None else {
                "normalized_query": normalized_doi,
                "strategy": "zotero-q-normalized",
                "queries_tried": [search_query],
            }),
        }

    exact_matches = [item for item in api.items(top_level=True) if _doi_matches(item, normalized_doi)]
    return {
        "ok": True,
        "read_only": True,
        "query": query,
        "normalized_query": normalized_doi,
        "count": len(exact_matches),
        "items": exact_matches[: max(1, min(limit, 100))],
        "strategy": "exact-doi-field",
        "queries_tried": [search_query, "top-level DOI field"],
    }


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
