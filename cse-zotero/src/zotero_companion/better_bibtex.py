"""Dry-run-first Better BibTeX readiness and path-sanitized library export."""

from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass
from pathlib import Path
import tempfile
from typing import Any, Callable


class BetterBibTeXError(RuntimeError):
    """Raised when Better BibTeX cannot satisfy the requested operation."""


@dataclass(frozen=True)
class BetterBibTeXClient:
    endpoint: str = "http://127.0.0.1:23119/better-bibtex/json-rpc"
    library_export_endpoint: str = "http://127.0.0.1:23119/better-bibtex/export/library?/library.bibtex"
    timeout: float = 15.0
    opener: Callable[..., Any] | None = None

    def call(self, method: str, params: list[object] | None = None) -> object:
        body = json.dumps(
            {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}
        ).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with (self.opener or urllib.request.urlopen)(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise BetterBibTeXError(f"Better BibTeX JSON-RPC request failed: {exc}") from exc
        if payload.get("error"):
            raise BetterBibTeXError(f"Better BibTeX {method} failed: {payload['error']}")
        return payload.get("result")

    def ready(self) -> dict[str, object]:
        result = self.call("api.ready")
        if not isinstance(result, dict):
            raise BetterBibTeXError("Better BibTeX api.ready returned an invalid result")
        return result

    def export_library(self) -> str:
        body = json.dumps(
            {"config": {"preferences": {"skipFields": "file"}}}
        ).encode("utf-8")
        request = urllib.request.Request(
            self.library_export_endpoint,
            data=body,
            headers={"Accept": "text/plain", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with (self.opener or urllib.request.urlopen)(request, timeout=self.timeout) as response:
                bibliography = response.read().decode("utf-8")
        except Exception as exc:
            raise BetterBibTeXError(f"Better BibTeX library export failed: {exc}") from exc
        if not bibliography.strip() or "@" not in bibliography:
            raise BetterBibTeXError("Better BibTeX library export returned no bibliography entries")
        if any(re.match(r"\s*file\s*=", line, re.IGNORECASE) for line in bibliography.splitlines()):
            raise BetterBibTeXError("Better BibTeX library export still contains local file fields")
        return bibliography


def export_plan(destination: Path, *, mode: str = "dry-run") -> dict[str, object]:
    return {
        "ok": True,
        "mode": mode,
        "scope": "personal-library",
        "translator": "Better BibTeX",
        "destination": str(destination),
        "would_create_directory": str(destination.parent),
        "consumers_changed": False,
        "refresh_mode": "task-triggered",
        "path_sanitization": {
            "required": True,
            "status": "enforced",
            "note": "The Better BibTeX export request overrides skipFields=file and refuses leaked file fields.",
        },
    }


def configure_export(destination: Path, client: BetterBibTeXClient | None = None) -> dict[str, object]:
    destination = Path(destination).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    client = client or BetterBibTeXClient()
    ready = client.ready()
    bibliography = client.export_library()
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=destination.parent,
        prefix=f".{destination.name}.",
        delete=False,
    ) as handle:
        handle.write(bibliography)
        temporary = Path(handle.name)
    temporary.replace(destination)
    payload = export_plan(destination, mode="apply")
    payload.update(
        {
            "better_bibtex": ready,
            "written": True,
            "entry_count": sum(1 for line in bibliography.splitlines() if line.startswith("@")),
            "bytes": destination.stat().st_size,
        }
    )
    return payload
