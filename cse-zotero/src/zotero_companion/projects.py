"""Project libraries: registered Zotero collections rendered as wiki project pages.

The registry (``projects.json`` beside the Companion configuration) owns the
binding from a project slug to one Zotero collection. The collection tree in
Zotero owns the organization; ``project-sync`` renders it below the curated
notes of ``wiki/projects/<slug>.md``.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from .config import default_config_path

REGISTRY_VERSION = 1
SLUG = re.compile(r"[a-z0-9][a-z0-9-]*")
COLLECTION_KEY = re.compile(r"[A-Z0-9]{8}")
GENERATED_MARKER = (
    "<!-- cse-zotero project-sync: everything below is generated from Zotero. "
    "Edit notes above this line; reorganize papers in Zotero. -->"
)
INDEX_NAME = "README.md"


class ProjectError(RuntimeError):
    """Raised when the project registry or a project operation is invalid."""


def default_registry_path() -> Path:
    return default_config_path().parent / "projects.json"


def _empty_registry() -> dict[str, Any]:
    return {"version": REGISTRY_VERSION, "root_collection": "", "sync_command": [], "projects": {}}


def validate_registry(registry: Any) -> dict[str, Any]:
    if not isinstance(registry, dict) or registry.get("version") != REGISTRY_VERSION:
        raise ProjectError(f"project registry must be an object with version {REGISTRY_VERSION}")
    root = registry.get("root_collection", "")
    if root and not COLLECTION_KEY.fullmatch(str(root)):
        raise ProjectError(f"invalid root collection key: {root!r}")
    command = registry.get("sync_command", [])
    if not isinstance(command, list) or not all(isinstance(part, str) for part in command):
        raise ProjectError("sync_command must be an array of strings")
    projects = registry.get("projects", {})
    if not isinstance(projects, dict):
        raise ProjectError("projects must be an object keyed by slug")
    seen: dict[str, str] = {}
    for slug, entry in projects.items():
        if not SLUG.fullmatch(slug):
            raise ProjectError(f"invalid project slug: {slug!r}")
        if not isinstance(entry, dict) or not COLLECTION_KEY.fullmatch(str(entry.get("collection", ""))):
            raise ProjectError(f"project {slug} needs an 8-character Zotero collection key")
        if not isinstance(entry.get("repository", ""), str):
            raise ProjectError(f"project {slug} repository must be a path string")
        if entry["collection"] in seen:
            raise ProjectError(f"projects {seen[entry['collection']]} and {slug} share collection {entry['collection']}")
        seen[entry["collection"]] = slug
    return registry


def load_registry(path: Path | None = None) -> dict[str, Any]:
    path = Path(path or default_registry_path())
    if not path.exists():
        return _empty_registry()
    try:
        return validate_registry(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectError(f"Could not read project registry {path}: {exc}") from exc


def write_registry(registry: dict[str, Any], path: Path | None = None) -> None:
    path = Path(path or default_registry_path())
    validate_registry(registry)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def project_collections(registry: Mapping[str, Any]) -> dict[str, str]:
    """Return slug -> collection key for every registered project."""

    return {slug: entry["collection"] for slug, entry in registry.get("projects", {}).items()}


def default_sync_command() -> list[str]:
    """The command the Zotero add-on runs; it appends ``--slug <slug>``."""

    executable = shutil.which("cse-zotero") or shutil.which("zotero-companion")
    prefix = [executable] if executable else [sys.executable, "-m", "zotero_companion.cli"]
    return [*prefix, "project-sync", "--apply", "--json"]


# --- Collection trees -------------------------------------------------------


def _data(obj: Mapping[str, Any]) -> Mapping[str, Any]:
    value = obj.get("data", obj)
    return value if isinstance(value, Mapping) else {}


def collection_table(collections: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, str]]:
    """Key -> {name, parent} from local API collection objects."""

    table = {}
    for collection in collections:
        data = _data(collection)
        key = str(collection.get("key") or data.get("key") or "")
        if key:
            table[key] = {"name": str(data.get("name", "")), "parent": str(data.get("parentCollection") or "")}
    return table


def descendants(table: Mapping[str, Mapping[str, str]], root: str) -> list[str]:
    """``root`` and every collection nested below it."""

    children: dict[str, list[str]] = defaultdict(list)
    for key, entry in table.items():
        children[entry["parent"]].append(key)
    found, pending = [], [root]
    while pending:
        key = pending.pop()
        found.append(key)
        pending.extend(children.get(key, []))
    return found


def is_within(table: Mapping[str, Mapping[str, str]], key: str, ancestor: str) -> bool:
    seen = set()
    while key and key not in seen:
        if key == ancestor:
            return True
        seen.add(key)
        key = table.get(key, {}).get("parent", "")
    return False


def memberships(
    collection_keys: Iterable[str],
    table: Mapping[str, Mapping[str, str]],
    projects: Mapping[str, str],
) -> list[str]:
    """Project slugs whose collection tree contains any of ``collection_keys``."""

    return sorted(
        slug
        for slug, root in projects.items()
        if any(is_within(table, key, root) for key in collection_keys)
    )


# --- Page rendering ---------------------------------------------------------


def _year(value: Any) -> str:
    match = re.search(r"\b(\d{4})\b", str(value or ""))
    return match.group(1) if match else "n.d."


def _authors(creators: Any) -> str:
    names = [
        str(creator.get("lastName") or creator.get("name") or "").strip()
        for creator in creators or []
        if isinstance(creator, Mapping) and creator.get("creatorType", "author") == "author"
    ]
    names = [name for name in names if name]
    if not names:
        return "Unknown author"
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return f"{names[0]} et al."


def _one_line(value: Any) -> str:
    return " ".join(str(value or "").split()).replace("|", "\\|")


def paper_routes(wiki_root: Path) -> dict[str, dict[str, str]]:
    """Zotero key -> {brief, brief_status} from curated paper briefs."""

    routes: dict[str, dict[str, str]] = {}
    for path in sorted((wiki_root / "papers").glob("*.md")):
        if path.name.casefold() == "readme.md":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        key = re.search(r"^\s*-\s*(?:Zotero key|zotero_key)\s*:\s*`?([A-Za-z0-9]+)", text, re.MULTILINE)
        if key:
            status = re.search(r"^\s*-\s*brief_status\s*:\s*(\S+)", text, re.MULTILINE | re.IGNORECASE)
            routes[key.group(1)] = {
                "brief": f"../papers/{path.name}",
                "brief_status": status.group(1).casefold() if status else "briefed",
            }
    return routes


def _has_markdown_text(wiki_root: Path, key: str) -> bool:
    try:
        manifest = json.loads((wiki_root / "evidence" / key / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    files = manifest.get("files", []) if isinstance(manifest, Mapping) else []
    return any(
        isinstance(entry, Mapping) and entry.get("format") in {"markdown", "mmd", "mathpix-markdown"}
        for entry in files
    )


def _paper_line(item: Mapping[str, Any], wiki_root: Path, routes: Mapping[str, Mapping[str, str]]) -> str:
    data = _data(item)
    key = str(item.get("key") or data.get("key"))
    title = _one_line(data.get("title") or "Untitled")
    parts = [f"- {_authors(data.get('creators'))} ({_year(data.get('date'))}). *{title}*."]
    links = []
    if (wiki_root / "sources" / key / "source.md").exists():
        links.append(f"[source](../sources/{key}/source.md)")
    else:
        links.append(f"source `{key}` not materialized yet")
    route = routes.get(key)
    if route:
        links.append(f"[brief]({route['brief']}) ({route['brief_status']})")
    if _has_markdown_text(wiki_root, key):
        links.append("Markdown text")
    return " ".join(parts) + " " + " · ".join(links)


def _sort_key(item: Mapping[str, Any]) -> tuple[str, str, str]:
    data = _data(item)
    return (_authors(data.get("creators")).casefold(), _year(data.get("date")), str(item.get("key", "")))


def render_library(
    slug: str,
    entry: Mapping[str, Any],
    table: Mapping[str, Mapping[str, str]],
    items: Iterable[Mapping[str, Any]],
    wiki_root: Path,
) -> str:
    """Render the generated part of a project page from the live tree."""

    root = entry["collection"]
    tree = set(descendants(table, root))
    by_collection: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    papers = set()
    for item in items:
        data = _data(item)
        if data.get("itemType") in {"attachment", "note", "annotation"} or data.get("parentItem"):
            continue
        for key in data.get("collections", []) or []:
            if key in tree:
                by_collection[key].append(item)
                papers.add(str(item.get("key") or data.get("key")))
    children: dict[str, list[str]] = defaultdict(list)
    for key in tree:
        if key != root:
            children[table[key]["parent"]].append(key)
    routes = paper_routes(wiki_root)
    lines = [
        GENERATED_MARKER,
        "",
        "## Zotero library",
        "",
        f"Collection **{_one_line(table[root]['name'])}** (`{root}`)"
        + (f" · repository `{entry['repository']}`" if entry.get("repository") else "")
        + f" · {len(papers)} paper{'' if len(papers) == 1 else 's'}",
        "",
    ]

    def emit(key: str, depth: int) -> None:
        members = sorted(by_collection.get(key, []), key=_sort_key)
        if key != root:
            count = len({str(item.get("key")) for sub in descendants(table, key) for item in by_collection.get(sub, [])})
            lines.extend([f"{'#' * min(depth, 6)} {_one_line(table[key]['name'])} ({count})", ""])
        lines.extend(_paper_line(item, wiki_root, routes) for item in members)
        if members:
            lines.append("")
        for child in sorted(children.get(key, []), key=lambda value: (table[value]["name"].casefold(), value)):
            emit(child, depth + 1)

    emit(root, 2)
    return "\n".join(lines).rstrip() + "\n"


def curated_part(text: str | None, *, title: str, slug: str) -> str:
    """Curated notes above the marker; an unmarked page is entirely curated."""

    if text is None:
        return f"# {title}\n\nSlug: `{slug}`\n\nAdd curated project notes here.\n"
    curated = text.split(GENERATED_MARKER, 1)[0]
    return curated.rstrip() + "\n"


def render_page(existing: str | None, slug: str, generated: str, title: str) -> str:
    return curated_part(existing, title=title, slug=slug) + "\n" + generated


def render_index(existing: str | None, registry: Mapping[str, Any], table: Mapping[str, Mapping[str, str]]) -> str:
    lines = [GENERATED_MARKER, "", "## Registered project libraries", ""]
    for slug, entry in sorted(registry.get("projects", {}).items()):
        name = table.get(entry["collection"], {}).get("name", "missing collection")
        lines.append(f"- [{slug}]({slug}.md) — Zotero collection **{_one_line(name)}** (`{entry['collection']}`)")
    curated = curated_part(existing, title="Project libraries", slug="projects") if existing else "# Project libraries\n"
    return curated + "\n" + "\n".join(lines) + "\n"


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def sync_projects(
    registry: Mapping[str, Any],
    wiki_root: Path,
    *,
    collections: Iterable[Mapping[str, Any]],
    items: Iterable[Mapping[str, Any]],
    slug: str | None = None,
    apply: bool = False,
) -> dict[str, Any]:
    """Render registered project pages; report which ones differ (are stale)."""

    projects = registry.get("projects", {})
    if slug is not None and slug not in projects:
        raise ProjectError(f"project {slug!r} is not registered")
    table = collection_table(collections)
    items = list(items)
    directory = Path(wiki_root) / "projects"
    selected = [slug] if slug else sorted(projects)
    pages = []
    writes: list[tuple[Path, str]] = []
    for name in selected:
        entry = projects[name]
        path = directory / f"{name}.md"
        if entry["collection"] not in table:
            # Trashed or deleted in Zotero: keep the page, report it, sync the rest.
            pages.append({"slug": name, "path": str(path), "stale": False, "missing_collection": entry["collection"]})
            continue
        existing = _read(path)
        generated = render_library(name, entry, table, items, Path(wiki_root))
        page = render_page(existing, name, generated, table[entry["collection"]]["name"])
        changed = page != existing
        pages.append({"slug": name, "path": str(path), "stale": changed})
        if changed:
            writes.append((path, page))
    index_path = directory / INDEX_NAME
    index_existing = _read(index_path)
    index = render_index(index_existing, registry, table) if projects else index_existing
    if index != index_existing:
        writes.append((index_path, index))
    if apply:
        directory.mkdir(parents=True, exist_ok=True)
        for path, text in writes:
            # Per-process name: the add-on and the CLI may sync at the same time.
            temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
            temporary.write_text(text, encoding="utf-8")
            os.replace(temporary, path)
    return {
        "mode": "apply" if apply else "dry-run",
        "wiki_root": str(wiki_root),
        "pages": pages,
        "stale": [page["slug"] for page in pages if page["stale"]],
        "missing": [page["slug"] for page in pages if "missing_collection" in page],
        "written": [str(path) for path, _ in writes] if apply else [],
    }


# --- Registration -----------------------------------------------------------


def plan_registration(
    registry: Mapping[str, Any],
    *,
    slug: str,
    collection: str,
    repository: str,
    collections: Iterable[Mapping[str, Any]],
    root: str | None = None,
) -> dict[str, Any]:
    """Return the registry after binding ``slug`` to ``collection``."""

    if not SLUG.fullmatch(slug):
        raise ProjectError(f"invalid project slug: {slug!r}")
    proposed = json.loads(json.dumps(registry))
    if root:
        proposed["root_collection"] = root
    table = collection_table(collections)
    root = proposed.get("root_collection", "")
    if not root:
        raise ProjectError("set the top-level project collection first with --root <collection key>")
    if root not in table:
        raise ProjectError(f"root collection {root} is not in the Zotero library")
    if collection not in table or collection == root or not is_within(table, collection, root):
        raise ProjectError(f"collection {collection} must be inside the project root collection {root}")
    for other, entry in proposed["projects"].items():
        if other != slug and (
            is_within(table, collection, entry["collection"]) or is_within(table, entry["collection"], collection)
        ):
            raise ProjectError(f"collection {collection} overlaps project {other} ({entry['collection']})")
    proposed["projects"][slug] = {"collection": collection, "repository": repository}
    proposed["sync_command"] = default_sync_command()
    return validate_registry(proposed)


__all__ = [
    "GENERATED_MARKER",
    "ProjectError",
    "collection_table",
    "default_registry_path",
    "descendants",
    "load_registry",
    "memberships",
    "plan_registration",
    "project_collections",
    "sync_projects",
    "write_registry",
]
