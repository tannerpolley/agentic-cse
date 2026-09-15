"""Consent-aware, dry-run-first Mathpix conversion for Zotero attachments."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

from .config import CompanionConfig
from .local_api import ZoteroLocalAPI
from .source_ops import attachment_path, source_children


class MathpixOperationError(RuntimeError):
    """Raised when conversion is unsafe or unavailable."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    return values


def _run_mpx(source: Path, destination: Path) -> None:
    config = _dotenv(Path.home() / ".mpx" / "config")
    if os.environ.get("MATHPIX_OCR_API_KEY") or config.get("MATHPIX_OCR_API_KEY"):
        raise MathpixOperationError("MATHPIX_OCR_API_KEY is present; refusing API-key billing")
    if not (os.environ.get("MATHPIX_SNIP_AUTH_TOKEN") or config.get("MATHPIX_SNIP_AUTH_TOKEN")):
        raise MathpixOperationError("Mathpix Snip auth is missing; run `mpx login` in a real terminal")
    mpx = shutil.which("mpx")
    if not mpx:
        raise MathpixOperationError("mpx is unavailable on PATH")
    cli_js = Path(mpx).resolve()
    shim = (
        "const cli = process.argv.pop(); process.argv.splice(1, 0, 'mpx'); "
        "process.stdout.clearLine = process.stdout.clearLine || function() {}; "
        "process.stdout.cursorTo = process.stdout.cursorTo || function() {}; require(cli);"
    )
    subprocess.run(
        ["node", "-e", shim, "--", "convert", str(source), str(destination), str(cli_js)],
        check=True,
    )


def mathpix_conversion(
    parent_key: str,
    pdf_key: str,
    config: CompanionConfig,
    *,
    destination: Path | None = None,
    apply: bool = False,
    api: ZoteroLocalAPI | None = None,
    converter: Callable[[Path, Path], None] | None = None,
) -> dict[str, Any]:
    if not config.mathpix_library_consent:
        raise MathpixOperationError("Mathpix library consent is not recorded in CSE Zotero config")
    api = api or ZoteroLocalAPI()
    parent = api.get(f"/api/users/0/items/{parent_key}")
    data = parent.get("data", {}) if isinstance(parent, dict) else {}
    tags = {str(tag.get("tag", "")).casefold() for tag in data.get("tags", []) if isinstance(tag, dict)}
    denied_tags = tags & {tag.casefold() for tag in config.denied_tags}
    if denied_tags:
        raise MathpixOperationError(f"Mathpix denied by Zotero tag: {', '.join(sorted(denied_tags))}")
    collection_keys = {str(key).casefold() for key in data.get("collections", [])}
    collection_names = {
        str(item.get("data", {}).get("name", "")).casefold(): str(item.get("key", "")).casefold()
        for item in api.collections()
        if isinstance(item, dict)
    }
    denied_collections = {value.casefold() for value in config.denied_collections}
    denied_collection_matches = collection_keys & (
        denied_collections | {collection_names.get(value, "") for value in denied_collections}
    )
    denied_collection_names = {
        name for name, key in collection_names.items()
        if name in denied_collections and key in collection_keys
    }
    if denied_collection_matches or denied_collection_names:
        denied = sorted(denied_collection_matches | denied_collection_names)
        raise MathpixOperationError(f"Mathpix denied by Zotero collection: {', '.join(denied)}")
    children = source_children(parent_key, api=api)["items"]
    markdown = [
        item for item in children
        if Path(str(item.get("data", {}).get("filename", ""))).suffix.casefold() in {".md", ".mmd"}
    ]
    if markdown:
        raise MathpixOperationError("A usable Markdown child already exists; use it instead of reconverting")
    pdf = next((item for item in children if item.get("key") == pdf_key), None)
    if not isinstance(pdf, dict) or pdf.get("data", {}).get("contentType") != "application/pdf":
        raise MathpixOperationError(f"Confirmed PDF attachment is not a PDF child of {parent_key}: {pdf_key}")
    source = Path(attachment_path(pdf_key, api=api)["path"])
    destination = Path(destination or (config.wiki_root / "evidence" / parent_key / f"{source.stem}.mmd")).resolve()
    if destination.suffix.casefold() not in {".md", ".mmd"}:
        raise MathpixOperationError("Mathpix destination must use .md or .mmd")
    if destination.exists():
        raise MathpixOperationError(f"Mathpix destination already exists: {destination}")
    payload: dict[str, Any] = {
        "ok": True,
        "mode": "apply" if apply else "dry-run",
        "parent_key": parent_key,
        "pdf_attachment_key": pdf_key,
        "source": str(source),
        "source_sha256": _sha256(source),
        "destination": str(destination),
        "library_consent": True,
        "denied_tags": [],
        "denied_collections": [],
        "source_immutable": True,
        "zotero_mutation": False,
    }
    if apply:
        destination.parent.mkdir(parents=True, exist_ok=True)
        (converter or _run_mpx)(source, destination)
        if not destination.is_file() or not destination.stat().st_size:
            raise MathpixOperationError("Mathpix conversion did not create a nonempty companion")
        payload.update(
            {
                "written": True,
                "destination_sha256": _sha256(destination),
                "destination_bytes": destination.stat().st_size,
                "auth": "snip-token",
            }
        )
    return payload
