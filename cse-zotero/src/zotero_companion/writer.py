"""Dry-run-first authenticated writer for Zotero Desktop's local API.

The read-only client in :mod:`zotero_companion.local_api` deliberately remains
unchanged.  This module owns the separate write credential, the local API
server-ID precondition, and the explicit organization operations.
"""

from __future__ import annotations

import json
import os
import re
import stat
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.error import HTTPError

DEFAULT_BASE_URL = "http://127.0.0.1:23119"
DEFAULT_KEY_PATH = Path.home() / ".config" / "zotero-companion" / "local-api-key"
API_VERSION = "3"
WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

MANUAL_TAG_MAPPINGS: tuple[tuple[str, str], ...] = (
    ("★", "priority:key"),
    ("Review", "role:review"),
    ("Presentation", "role:presentation"),
    ("Machine Learning", "method:machine-learning"),
    ("Uncertainty Quantification", "method:uncertainty-quantification"),
    ("Simulation", "method:simulation"),
    ("Thermodynamics", "topic:thermodynamics"),
    ("Transport", "topic:transport"),
)

WORKFLOW_SEARCHES: tuple[tuple[str, str], ...] = (
    ("Workflow — To Read", "status:to-read"),
    ("Workflow — Reading", "status:reading"),
    ("Workflow — Reviewed", "status:reviewed"),
    ("Priority — Key", "priority:key"),
)


class WriterError(RuntimeError):
    """Raised when an authenticated local API operation cannot proceed."""


class KeyFileError(WriterError):
    """Raised when the local API key file is missing, unsafe, or invalid."""


class WriterHTTPError(WriterError):
    """Raised for a non-successful local API response without exposing secrets."""

    def __init__(self, method: str, path: str, status: int, detail: str = ""):
        self.method = method
        self.path = path
        self.status = status
        detail = detail.replace("\n", " ").strip()[:240]
        suffix = f": {detail}" if detail else ""
        super().__init__(f"{method} {path} returned HTTP {status}{suffix}")


@dataclass(frozen=True)
class _HTTPResponse:
    status: int
    headers: Any
    body: bytes


def load_local_api_key(path: Path = DEFAULT_KEY_PATH) -> str:
    """Read and validate a remembered Zotero local API key.

    The key is intentionally returned only to the request layer.  Error
    messages contain the file path and validation reason, never file contents.
    """

    key_path = Path(path)
    try:
        metadata = key_path.stat()
    except OSError as exc:
        raise KeyFileError(f"Unable to read local API key file {key_path}: {exc.strerror or exc}") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise KeyFileError(f"Local API key path is not a regular file: {key_path}")
    if os.name != "nt" and stat.S_IMODE(metadata.st_mode) & 0o077:
        raise KeyFileError(f"Local API key file must not be group/world accessible: {key_path}")
    try:
        key = key_path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError) as exc:
        raise KeyFileError(f"Unable to read local API key file {key_path}: {exc}") from exc
    if not key:
        raise KeyFileError(f"Local API key file is empty: {key_path}")
    if any(character.isspace() for character in key):
        raise KeyFileError(f"Local API key file contains unexpected whitespace: {key_path}")
    if re.fullmatch(r"[A-Za-z0-9]{32}", key) is None:
        raise KeyFileError(f"Local API key must be a 32-character token: {key_path}")
    return key


def _header(headers: Any, name: str) -> str | None:
    if headers is None:
        return None
    value = headers.get(name) if hasattr(headers, "get") else None
    if value is not None:
        return str(value)
    if hasattr(headers, "items"):
        wanted = name.lower()
        for header_name, header_value in headers.items():
            if str(header_name).lower() == wanted:
                return str(header_value)
    return None


def _json_body(body: bytes) -> Any:
    if not body:
        return None
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WriterError("Zotero local API returned invalid JSON") from exc


def _response_detail(body: bytes, secret: str | None = None) -> str:
    detail = body.decode("utf-8", errors="replace")
    if secret:
        detail = detail.replace(secret, "[redacted]")
    return detail


def _tag_objects(tags: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for tag in tags:
        name = str(tag.get("tag", ""))
        if not name:
            continue
        try:
            tag_type = int(tag.get("type", 0) or 0)
        except (TypeError, ValueError):
            tag_type = 0
        normalized.append({"tag": name, "type": 1 if tag_type == 1 else 0})
    return normalized


def build_tag_plan(items: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Build item PATCH descriptions without performing any HTTP writes.

    Only manual assignments (tag type 0) are mapped.  Existing automatic tags
    and unrelated manual tags are preserved exactly in the resulting tag list.
    """

    mapping = dict(MANUAL_TAG_MAPPINGS)
    operations: list[dict[str, Any]] = []
    for item in items:
        data = item.get("data", item)
        raw_tags = data.get("tags", [])
        if not isinstance(raw_tags, Sequence) or isinstance(raw_tags, (str, bytes)):
            raise WriterError("Zotero item contained an invalid tags value")
        current = _tag_objects(raw_tags)
        present_names = {tag["tag"] for tag in current}
        removed: list[str] = []
        added: list[str] = []
        updated: list[dict[str, Any]] = []
        for tag in current:
            name = tag["tag"]
            if tag["type"] == 0 and name in mapping:
                replacement = mapping[name]
                removed.append(name)
                if replacement not in present_names and replacement not in added:
                    added.append(replacement)
                continue
            updated.append(tag)
        updated.extend({"tag": name, "type": 0} for name in added)
        if updated == current:
            continue
        key = item.get("key") or data.get("key")
        if not key:
            raise WriterError("Zotero item requiring a tag update had no item key")
        raw_version = item.get("version", data.get("version"))
        try:
            version = int(raw_version)
            if version < 0:
                raise ValueError
        except (TypeError, ValueError):
            version = None
        operations.append(
            {
                "key": str(key),
                "version": version,
                "blocked_reason": (
                    None if version is not None else "missing_or_invalid_item_version"
                ),
                "removed": removed,
                "added": added,
                "tags": updated,
            }
        )
    return operations


def build_search_plan(searches: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Build missing workflow saved-search definitions without writing."""

    existing_names = {
        str(search.get("data", search).get("name", ""))
        for search in searches
    }
    plan: list[dict[str, Any]] = []
    for name, tag in WORKFLOW_SEARCHES:
        if name in existing_names:
            continue
        plan.append(
            {
                "name": name,
                "tag": tag,
                "conditions": [
                    {"condition": "tag", "operator": "is", "value": tag},
                    {"condition": "noChildren", "operator": "true", "value": ""},
                ],
            }
        )
    return plan


def _tag_summary(
    items_considered: int,
    operations: Sequence[Mapping[str, Any]],
    mode: str,
    *,
    library_version: int | None = None,
) -> dict[str, Any]:
    blocked = [
        {"key": operation["key"], "reason": operation["blocked_reason"]}
        for operation in operations
        if operation.get("blocked_reason")
    ]
    return {
        "mode": mode,
        "items_considered": items_considered,
        "items_changed": len(operations),
        "assignments_removed": sum(len(operation["removed"]) for operation in operations),
        "assignments_added": sum(len(operation["added"]) for operation in operations),
        "blocked_items": blocked,
        "changes": [
            {
                "key": operation["key"],
                "version": operation["version"],
                "precondition": (
                    {"item_version": operation["version"]}
                    if operation["version"] is not None
                    else (
                        {"library_version": library_version}
                        if library_version is not None
                        else None
                    )
                ),
                "blocked_reason": operation.get("blocked_reason"),
                "removed": operation["removed"],
                "added": operation["added"],
            }
            for operation in operations
        ],
    }


@dataclass
class ZoteroLocalAPIWriter:
    """Authenticated local API writer with an in-process server-ID cache."""

    base_url: str = DEFAULT_BASE_URL
    key_path: Path = DEFAULT_KEY_PATH
    timeout: float = 10.0
    opener: Callable[..., Any] | None = None
    _api_key: str | None = field(default=None, init=False, repr=False)
    _server_id: str | None = field(default=None, init=False, repr=False)

    def _ensure_api_key(self) -> None:
        if self._api_key is None:
            self._api_key = load_local_api_key(self.key_path)

    @property
    def api_key(self) -> str:
        self._ensure_api_key()
        assert self._api_key is not None
        return self._api_key

    @property
    def server_id(self) -> str:
        if self._server_id is None:
            self._discover_server_id()
        assert self._server_id is not None
        return self._server_id

    def _open(self, request: urllib.request.Request) -> _HTTPResponse:
        open_fn = self.opener or urllib.request.urlopen
        try:
            with open_fn(request, timeout=self.timeout) as response:
                return _HTTPResponse(response.status, response.headers, response.read())
        except HTTPError as exc:
            return _HTTPResponse(exc.code, exc.headers, exc.read())
        except Exception as exc:  # pragma: no cover - exercised by integration use
            raise WriterError(f"{request.method} request failed: {exc}") from exc

    def _request(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: Any = None,
        authenticate: bool = False,
        if_unmodified_version: int | None = None,
        write_token: str | None = None,
    ) -> _HTTPResponse:
        if not path.startswith("/api/"):
            raise ValueError("local API paths must start with /api/")
        method = method.upper()
        if method in WRITE_METHODS and not authenticate:
            authenticate = True
        headers = {
            "Accept": "application/json",
            "Zotero-API-Version": API_VERSION,
        }
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        else:
            body = None
        if authenticate:
            headers["Zotero-API-Key"] = self.api_key
            headers["Zotero-Server-ID"] = self.server_id
        if if_unmodified_version is not None:
            headers["If-Unmodified-Since-Version"] = str(if_unmodified_version)
        if write_token is not None:
            headers["Zotero-Write-Token"] = write_token
        url = f"{self.base_url.rstrip('/')}{path}"
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        response = self._open(request)
        discovered = _header(response.headers, "Zotero-Server-ID")
        if discovered:
            self._server_id = discovered
        if response.status < 200 or response.status >= 300:
            raise WriterHTTPError(
                method,
                urllib.parse.urlsplit(url).path,
                response.status,
                _response_detail(response.body, self._api_key),
            )
        return response

    def _discover_server_id(self) -> str:
        response = self._request("/api/", method="GET")
        discovered = _header(response.headers, "Zotero-Server-ID")
        if not discovered:
            raise WriterError("Zotero local API response did not include Zotero-Server-ID")
        self._server_id = discovered
        return discovered

    def status(self) -> dict[str, Any]:
        """Check API readiness and key-file readability without mutating Zotero."""

        self._ensure_api_key()
        response = self._request("/api/", method="GET")
        return {
            "base_url": self.base_url,
            "key_file": str(self.key_path),
            "key_loaded": True,
            "api_version": _header(response.headers, "Zotero-API-Version"),
            "schema_version": _header(response.headers, "Zotero-Schema-Version"),
            "server_id": self.server_id,
        }

    def patch_item_tags(
        self,
        key: str,
        tags: Sequence[Mapping[str, Any]],
        *,
        version: int | None,
        if_unmodified_version: int | None = None,
    ) -> None:
        """Apply one version-checked item tag update."""

        if not key:
            raise ValueError("item key must not be empty")
        payload: dict[str, Any] = {"tags": list(tags)}
        if version is not None:
            payload["version"] = version
        elif if_unmodified_version is None:
            raise WriterError(f"Refusing to update item {key} without a version precondition")
        self._request(
            f"/api/users/0/items/{urllib.parse.quote(key, safe='')}",
            method="PATCH",
            payload=payload,
            authenticate=True,
            if_unmodified_version=if_unmodified_version,
            write_token=uuid.uuid4().hex,
        )

    def patch_item_collections(
        self,
        key: str,
        collection_keys: Sequence[str],
        *,
        version: int | None,
        if_unmodified_version: int | None = None,
    ) -> None:
        """Apply one version-checked item collection assignment."""

        if not key:
            raise ValueError("item key must not be empty")
        collections = [str(collection) for collection in collection_keys if str(collection)]
        payload: dict[str, Any] = {"collections": collections}
        if version is not None:
            payload["version"] = version
        elif if_unmodified_version is None:
            raise WriterError(f"Refusing to update item {key} without a version precondition")
        self._request(
            f"/api/users/0/items/{urllib.parse.quote(key, safe='')}",
            method="PATCH",
            payload=payload,
            authenticate=True,
            if_unmodified_version=if_unmodified_version,
            write_token=uuid.uuid4().hex,
        )

    def create_searches(
        self,
        plan: Sequence[Mapping[str, Any]],
        *,
        if_unmodified_version: int | None,
    ) -> None:
        """Create a batch of unkeyed searches after an explicit apply request."""

        if not plan:
            return
        if if_unmodified_version is None:
            raise WriterError("Refusing to create searches without a library version precondition")
        payload = [
            {"name": search["name"], "conditions": list(search["conditions"])}
            for search in plan
        ]
        self._request(
            "/api/users/0/searches",
            method="POST",
            payload=payload,
            authenticate=True,
            if_unmodified_version=if_unmodified_version,
            write_token=uuid.uuid4().hex,
        )

    def linked_attachment(
        self,
        parent_key: str,
        companion: Path,
        *,
        apply: bool = False,
    ) -> dict[str, Any]:
        """Plan or create one linked Markdown child attachment."""
        parent_key = parent_key.strip()
        companion = Path(companion).expanduser().resolve()
        if not parent_key:
            raise WriterError("parent Zotero key must not be empty")
        if companion.suffix.casefold() not in {".md", ".mmd"} or not companion.is_file():
            raise WriterError(f"Companion must be an existing .md or .mmd file: {companion}")
        response = self._request(
            f"/api/users/0/items/{urllib.parse.quote(parent_key, safe='')}",
            method="GET",
        )
        parent = _json_body(response.body)
        if not isinstance(parent, dict) or str(parent.get("key", "")) != parent_key:
            raise WriterError(f"Zotero parent item is unavailable: {parent_key}")
        version_raw = _header(response.headers, "Last-Modified-Version")
        try:
            library_version = int(version_raw) if version_raw is not None else None
        except ValueError:
            library_version = None
        if library_version is None:
            raise WriterError("Refusing attachment creation without a library version precondition")
        payload = {
            "itemType": "attachment",
            "parentItem": parent_key,
            "linkMode": "linked_file",
            "contentType": "text/markdown",
            "path": str(companion),
            "title": companion.name,
            "tags": [],
            "note": "",
            "relations": {},
        }
        result: dict[str, Any] = {
            "ok": True,
            "mode": "apply" if apply else "dry-run",
            "parent_key": parent_key,
            "companion": str(companion),
            "content_type": "text/markdown",
            "link_mode": "linked_file",
            "precondition": {"library_version": library_version},
            "would_create": payload,
        }
        if apply:
            created = self._request(
                "/api/users/0/items",
                method="POST",
                payload=[payload],
                authenticate=True,
                if_unmodified_version=library_version,
                write_token=uuid.uuid4().hex,
            )
            response_payload = _json_body(created.body)
            successful = response_payload.get("successful", {}) if isinstance(response_payload, dict) else {}
            first = successful.get("0", successful.get(0, {})) if isinstance(successful, dict) else {}
            key = str(first.get("key", "")) if isinstance(first, dict) else ""
            if not key:
                raise WriterError("Zotero did not return a child key for the linked companion")
            result.update({"written": True, "attachment_key": key})
        return result

    def tag_cleanup(self, *, apply: bool = False) -> dict[str, Any]:
        """Plan or explicitly apply the approved manual-tag mapping."""

        # A single bounded local read gives us both the complete local item
        # list and the library Last-Modified-Version header.  The latter is a
        # safe fallback for local records that expose an empty item version.
        response = self._request(
            "/api/users/0/items?limit=100000&start=0",
            method="GET",
        )
        items = _json_body(response.body)
        if not isinstance(items, list):
            raise WriterError("Zotero local API returned a non-list item response")
        library_version_raw = _header(response.headers, "Last-Modified-Version")
        try:
            library_version = int(library_version_raw) if library_version_raw is not None else None
        except ValueError:
            library_version = None
        operations = build_tag_plan(items)
        if library_version is not None:
            for operation in operations:
                if operation.get("blocked_reason") == "missing_or_invalid_item_version":
                    operation["blocked_reason"] = None
        if not apply:
            return _tag_summary(
                len(items), operations, "dry-run", library_version=library_version
            )
        # Load the key before the first mutation, even if the plan is empty.
        self._ensure_api_key()
        blocked = [operation for operation in operations if operation.get("blocked_reason")]
        if blocked:
            keys = ", ".join(operation["key"] for operation in blocked[:5])
            suffix = "" if len(blocked) <= 5 else " …"
            raise WriterError(
                "Refusing to apply tag updates without a valid item or library "
                f"version precondition ({len(blocked)} blocked; {keys}{suffix})"
            )
        for operation in operations:
            self.patch_item_tags(
                operation["key"],
                operation["tags"],
                version=operation["version"],
                if_unmodified_version=(
                    library_version if operation["version"] is None else None
                ),
            )
        return _tag_summary(
            len(items), operations, "apply", library_version=library_version
        )

    def saved_searches(self, *, apply: bool = False) -> dict[str, Any]:
        """Plan or explicitly create the missing workflow saved searches."""

        response = self._request(
            "/api/users/0/searches?limit=100000&start=0",
            method="GET",
        )
        searches = _json_body(response.body)
        if not isinstance(searches, list):
            raise WriterError("Zotero local API returned a non-list search response")
        library_version_raw = _header(response.headers, "Last-Modified-Version")
        try:
            library_version = int(library_version_raw) if library_version_raw is not None else None
        except ValueError:
            library_version = None
        plan = build_search_plan(searches)
        result = {
            "mode": "apply" if apply else "dry-run",
            "searches_considered": len(searches),
            "searches_to_create": len(plan),
            "precondition": (
                {"library_version": library_version}
                if library_version is not None
                else None
            ),
            "changes": plan,
        }
        if apply:
            self._ensure_api_key()
            self.create_searches(plan, if_unmodified_version=library_version)
        return result


__all__ = [
    "DEFAULT_KEY_PATH",
    "MANUAL_TAG_MAPPINGS",
    "WORKFLOW_SEARCHES",
    "KeyFileError",
    "WriterError",
    "WriterHTTPError",
    "ZoteroLocalAPIWriter",
    "build_search_plan",
    "build_tag_plan",
    "load_local_api_key",
]
