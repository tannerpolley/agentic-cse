"""Small, read-only client for Zotero Desktop's local API."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any


class LocalAPIError(RuntimeError):
    """Raised when the local Zotero API cannot satisfy a read request."""


@dataclass(frozen=True)
class ZoteroLocalAPI:
    base_url: str = "http://127.0.0.1:23119"
    timeout: float = 10.0
    opener: Callable[..., Any] | None = None

    def get(self, path: str, params: Mapping[str, str | int] | None = None) -> Any:
        """GET one local API endpoint; no mutating HTTP methods are exposed."""
        if not path.startswith("/api/"):
            raise ValueError("local API paths must start with /api/")
        query = urllib.parse.urlencode(params or {})
        url = f"{self.base_url.rstrip('/')}{path}"
        if query:
            url = f"{url}?{query}"
        request = urllib.request.Request(
            url,
            headers={"Zotero-API-Version": "3"},
            method="GET",
        )
        open_fn = self.opener or urllib.request.urlopen
        try:
            with open_fn(request, timeout=self.timeout) as response:
                if response.status < 200 or response.status >= 300:
                    raise LocalAPIError(f"GET {path} returned HTTP {response.status}")
                return json.loads(response.read().decode("utf-8"))
        except LocalAPIError:
            raise
        except Exception as exc:  # pragma: no cover - exercised by integration use
            raise LocalAPIError(f"GET {path} failed: {exc}") from exc

    def get_text(self, path: str, params: Mapping[str, str | int] | None = None) -> str:
        """GET a plain-text local API endpoint; no mutating methods are exposed."""
        if not path.startswith("/api/"):
            raise ValueError("local API paths must start with /api/")
        query = urllib.parse.urlencode(params or {})
        url = f"{self.base_url.rstrip('/')}{path}"
        if query:
            url = f"{url}?{query}"
        request = urllib.request.Request(
            url,
            headers={"Zotero-API-Version": "3"},
            method="GET",
        )
        open_fn = self.opener or urllib.request.urlopen
        try:
            with open_fn(request, timeout=self.timeout) as response:
                if response.status < 200 or response.status >= 300:
                    raise LocalAPIError(f"GET {path} returned HTTP {response.status}")
                return response.read().decode("utf-8")
        except LocalAPIError:
            raise
        except Exception as exc:  # pragma: no cover - exercised by integration use
            raise LocalAPIError(f"GET {path} failed: {exc}") from exc

    def paged(self, path: str, *, limit: int = 100) -> Iterator[dict[str, Any]]:
        """Yield every object from a paginated local API collection endpoint."""
        for start in range(0, 1_000_000, limit):
            page = self.get(path, {"limit": limit, "start": start})
            if not isinstance(page, list):
                raise LocalAPIError(f"Expected a JSON list from {path}")
            yield from page
            if len(page) < limit:
                return
        raise LocalAPIError(f"Pagination limit exceeded for {path}")

    def items(self, *, top_level: bool = False) -> list[dict[str, Any]]:
        endpoint = "/api/users/0/items/top" if top_level else "/api/users/0/items"
        return list(self.paged(endpoint))

    def collections(self) -> list[dict[str, Any]]:
        return list(self.paged("/api/users/0/collections"))

    def tags(self) -> list[dict[str, Any]]:
        return list(self.paged("/api/users/0/tags"))

    def searches(self) -> list[dict[str, Any]]:
        return list(self.paged("/api/users/0/searches"))
