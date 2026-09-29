#!/usr/bin/env python3
"""Manage one native Quarto website of analysis pages with explicit publication membership."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ASSET_ROOT = Path(__file__).resolve().parent
CONFIG_FILES = ("_quarto.yml", "_cse-manuscript.json", "_quarto-presentation.yml")
# Plugin-owned files that re-running init on a managed root replaces with the current plugin copies.
TOOLING_FILES = ("_quarto-presentation.yml", "render.sh", "manuscript.py", ".cse-quarto-source.json")
# The shared stylesheet is installed once and then owned by the project, like the configuration.
SITE_CSS = "site.css"
REQUIRED_FILES = (*CONFIG_FILES, "index.qmd", ".cse-quarto-source.json",
                  ".gitignore", "render.sh", "manuscript.py", SITE_CSS)
REQUIRED_IGNORES = ("/.quarto/", "/_site/", "/site_libs/", "/_freeze/", "/notebook.tex")
SITE_CONFIG = {
    "project": {"type": "website", "output-dir": "_site"},
    "metadata-files": ["_cse-manuscript.json"], "website": {"title": "Analyses", "search": True, "reader-mode": True, "page-navigation": False},
    "format": {"html": {"embed-resources": True, "page-layout": "full", "theme": "cosmo", "css": SITE_CSS,
                        "fontsize": "16px", "toc": False, "notebook-links": False, "format-links": False,
                        "html-math-method": "mathjax", "self-contained-math": True}},
    "execute": {"enabled": False},
}
PRESENTATION_PRE_RENDER = "python3 manuscript.py prepare"
WATCH_INTERVAL_SECONDS = 0.25
WATCH_SETTLE_SECONDS = 0.25
IGNORED_WATCH_PARTS = {".git", ".quarto", "_site", "site_libs", "_freeze", "__pycache__", ".ipynb_checkpoints"}
IGNORED_WATCH_PARTS |= {".snakemake", ".cache", "tmp", "temp", "support"}
IGNORED_WATCH_SUFFIXES = ("_files", "_support")
# ponytail: Quarto's internal preview render-request path (the one IDE integrations use);
# preview ignores mtime-only touches and include changes. Recheck on a Quarto upgrade.
QUARTO_RENDER_REQUEST = "90B3C9E8-0DBC-4BC0-B164-AA2D5C031B28"
INCLUDE_RE = re.compile(r"\{\{<\s*include\s+([^\s>]+)")
INCLUDE_SHORTCODE_RE = re.compile(r"\{\{<\s*include\s+([^\s>]+)\s*>\}\}")
SERVICE_MARKER = "# Managed by CSE manuscript.py service; do not edit.\n"
SERVICE_PORT_RE = re.compile(r"--port (\d+)$", re.MULTILINE)
SERVICE_PORT_BASE, SERVICE_PORT_SPAN = 8800, 1000
SERVICE_READY_SECONDS = 20
UNIT_UNSAFE_RE = re.compile(r"[\s\"'\\%$]")
PREVIEW_IMPORTS = "jupyter_core, nbformat, nbclient, ipykernel, jupyter_client, jupyter_cache, yaml"


class ManuscriptError(Exception):
    """An unsupported project needing reconciliation before any original write."""


def require(condition, path: Path, reason: str) -> None:
    if not condition:
        raise ManuscriptError(f"{path}: {reason}; reconcile before retrying")


def reject_symlink(path: Path) -> None:
    for candidate in (path, *path.parents):
        require(not candidate.is_symlink(), candidate, "refusing symlink path")


def root_path(value: Path, *, must_exist: bool = True) -> Path:
    root = value.absolute()
    reject_symlink(root)
    require(not root.exists() or root.is_dir(), root, "destination is not a directory")
    require(root.is_dir() if must_exist else root.parent.is_dir(), root, "missing root or parent")
    return root.resolve()


def inside(root: Path, value: Path) -> str:
    path = value.absolute()
    reject_symlink(path)
    require(path.is_relative_to(root) and path != root and ".." not in path.parts,
            path, "path must be below manuscript root")
    return path.relative_to(root).as_posix()


def read_file(path: Path) -> bytes:
    reject_symlink(path)
    require(path.is_file(), path, "missing file or non-file collision")
    return path.read_bytes()


def json_bytes(value) -> bytes:
    return (json.dumps(value, indent=2) + "\n").encode()


def read_json(data: bytes, path: Path) -> dict:
    def unique(pairs):
        require(len(dict(pairs)) == len(pairs), path, "duplicate JSON field")
        return dict(pairs)
    try:
        value = json.loads(data, object_pairs_hook=unique)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ManuscriptError(f"{path}: reviewed conversion to JSON-compatible YAML required") from exc
    require(isinstance(value, dict), path, "configuration must be a JSON object")
    return value




def is_group(entry: dict) -> bool:
    """A group section holds page sections; a page section holds links."""
    return "section" in entry["contents"][0]


def flatten(entries: list[dict]) -> list[dict]:
    """Page sections in sidebar order, descending through (possibly nested) groups."""
    return [page for entry in entries for page in (flatten(entry["contents"]) if is_group(entry) else [entry])]


def page_sections(state: dict) -> list[dict]:
    """Home and notebook sections in sidebar order, with groups flattened."""
    return flatten(state["website"]["sidebar"]["contents"])


def notebooks(state: dict) -> list[dict]:
    """Included notebooks in sidebar order, each ``{"text": title, "href": notebook}``."""
    return [{"text": entry["section"], "href": entry["contents"][0]["href"].split("#")[0]}
            for entry in page_sections(state)[1:]]


def plain(inlines: list) -> str:
    """Text of Pandoc inline elements, keeping inline math as TeX."""
    text = []
    for item in inlines:
        kind, content = item["t"], item.get("c")
        if kind == "Str":
            text.append(content)
        elif kind in {"Space", "SoftBreak", "LineBreak"}:
            text.append(" ")
        elif kind == "Math":
            text.append(f"${content[1]}$")
        elif kind == "Code":
            text.append(content[1])
        elif kind in {"Emph", "Strong", "Strikeout", "Superscript", "Subscript", "SmallCaps", "Underline"}:
            text.append(plain(content))
        elif kind in {"Link", "Span", "Quoted", "Cite"}:
            text.append(plain(content[1]))
    return "".join(text).strip()


def sections(root: Path, page: str, text: bytes | None = None) -> list[dict]:
    """Sidebar children of a page: the page itself (so Quarto opens its section there), then each
    top-level heading outside ::: blocks at the page's highest heading level."""
    # Quarto expands includes before Pandoc assigns identifiers, so expand them the same way.
    def expand(source: str, directory: Path, depth: int = 0) -> str:
        require(depth < 10, root / page, "include nesting is too deep")
        return INCLUDE_SHORTCODE_RE.sub(
            lambda m: expand(read_file(directory / m.group(1)).decode(), (directory / m.group(1)).parent, depth + 1),
            source)

    source = expand((read_file(root / page) if text is None else text).decode(), (root / page).parent)
    # Pandoc assigns the identifiers, so the anchors match the rendered page exactly.
    result = subprocess.run(["quarto", "pandoc", "--from", "markdown", "--to", "json"],
                            input=source.encode(), capture_output=True)
    require(result.returncode == 0, root / page, f"heading inspection failed: {result.stderr.decode().strip()}")
    headers = [block["c"] for block in json.loads(result.stdout)["blocks"] if block["t"] == "Header"]
    top = min((level for level, *_ in headers), default=None)
    for level, _, inlines in headers:
        # Other shortcodes are expanded only at render time, so their heading anchors are unknown here.
        require(level != top or "{{<" not in plain(inlines), root / page,
                f"top-level heading {plain(inlines)!r} contains a shortcode; move it into the section body")
    items = [{"text": plain(inlines), "href": f"{page}#{attributes[0]}"}
             for level, attributes, inlines in headers if level == top and attributes[0] and plain(inlines)]
    return [{"text": "Overview", "href": page}, *items]


def home_section(root: Path, text: bytes | None = None) -> dict:
    # A fixed, content-neutral name: the home page's own title stays on the page.
    return {"section": "Home", "contents": sections(root, "index.qmd", text)}


def refresh_sections(root: Path, state: dict, files: dict[str, bytes] | None = None) -> None:
    """Recompute every page's sidebar links from its headings, keeping titles and groups."""
    for entry in page_sections(state):
        page = entry["contents"][0]["href"].split("#")[0]
        entry["contents"] = sections(root, page, (files or {}).get(page))


def metadata(data: bytes, path: Path) -> dict:
    state = read_json(data, path)
    require(set(state) == {"project", "website"}, path, "unsupported membership fields")
    project, website = state["project"], state["website"]
    require(isinstance(project, dict) and set(project) == {"render"}
            and isinstance(website, dict) and set(website) == {"sidebar"}, path, "invalid membership owners")
    render, sidebar = project["render"], website["sidebar"]
    require(isinstance(render, list) and all(isinstance(p, str) for p in render)
            and len(render) == len(set(render)), path, "render membership must be unique")
    require(isinstance(sidebar, dict) and set(sidebar) == {"style", "collapse-level", "contents"}
            and sidebar["style"] == "docked" and sidebar["collapse-level"] == 1
            and isinstance(sidebar["contents"], list) and sidebar["contents"],
            path, "sidebar must be docked and start with the home page")
    def section(entry) -> bool:
        return (isinstance(entry, dict) and set(entry) == {"section", "contents"}
                and isinstance(entry["section"], str) and entry["section"].strip()
                and isinstance(entry["contents"], list) and bool(entry["contents"]))

    def check(entries: list) -> None:
        for entry in entries:
            require(section(entry), path, "invalid sidebar section")
            if is_group(entry):
                require(all(section(c) for c in entry["contents"]), path, "a group holds only sections")
                check(entry["contents"])

    check(sidebar["contents"])
    require(not is_group(sidebar["contents"][0]), path, "sidebar must start with the home page")
    for entry in page_sections(state):
        require(isinstance(entry, dict) and set(entry) == {"section", "contents"}
                and isinstance(entry["section"], str) and entry["section"].strip()
                and isinstance(entry["contents"], list) and entry["contents"]
                and all(isinstance(c, dict) and set(c) == {"text", "href"}
                        and all(isinstance(v, str) and v.strip() for v in c.values()) for c in entry["contents"])
                and len({c["href"].split("#")[0] for c in entry["contents"]}) == 1,
                path, "invalid page section")
    require(sidebar["contents"][0]["contents"][0]["href"] == "index.qmd", path, "sidebar must start with the home page")
    require(render == ["index.qmd", *[n["href"] for n in notebooks(state)]], path, "ordered memberships disagree")
    return state


def check_owners(value, path: Path, *, allow_presentation_hook: bool = False) -> None:
    if isinstance(value, dict):
        forbidden = {"project", "manuscript", "website", "book", "render", "notebooks",
                     "pre-render", "post-render", "filters", "filter", "profile", "execute",
                     "metadata-files", "metadata-file", "engines", "engine", "knitr",
                     "output-file", "output-dir", "execute-dir", "keep-md",
                     "include-in-header", "include-before-body", "include-after-body"}
        if allow_presentation_hook and "project" in value:
            project = value["project"]
            require(isinstance(project, dict) and set(project) == {"pre-render"}
                    and project["pre-render"] == PRESENTATION_PRE_RENDER, path,
                    "unrecognized presentation pre-render hook")
            forbidden.remove("project")
        require(not forbidden.intersection(value), path,
                f"competing configuration owner: {sorted(forbidden.intersection(value))}")
        for name, child in value.items():
            if name != "project":
                check_owners(child, path)
    elif isinstance(value, list):
        for child in value:
            check_owners(child, path)


def check_boundary(root: Path) -> None:
    config = root / "_quarto.yml"
    if config.is_file():
        project = read_json(read_file(config), config).get("project")
        require(not (isinstance(project, dict) and project.get("type") == "manuscript"), config,
                "earlier CSE Quarto Manuscript root; rebuild it as a website by removing page-level execute: "
                "settings and nested Quarto projects, removing _quarto.yml, _quarto-presentation.yml, "
                "_cse-manuscript.json, .cse-quarto-source.json, manuscript.py, and render.sh, rerunning init "
                "with --article-source index.qmd, including each notebook again with include --group, then "
                "running render.sh and service (see references/visualize/quarto-execution.md)")
    output = root / "_site"
    reject_symlink(output)
    require(not output.exists() or output.is_dir(), output, "output is not a directory")
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [n for n in dirs if n != ".git"]
        for name in [*dirs, *files]:
            path = Path(directory) / name
            reject_symlink(path)
            if {".quarto", "_site", "_freeze"}.intersection(path.relative_to(root).parts):
                continue
            config = name.startswith(("_quarto", "_metadata", "_variables")) and path.suffix in {".yml", ".yaml"}
            allowed_variable_file = name == "_variables.yml" and Path(directory) == root
            require(not (config and not allowed_variable_file
                         and (Path(directory) != root or name not in CONFIG_FILES))
                    and not name.startswith(".env") and name != "_extensions", path, "unsupported inherited or nested configuration")


def included_files(root: Path, files: dict[str, bytes], paths: list[str]) -> dict[str, bytes]:
    found = {}
    pending = list(paths)
    while pending:
        source = pending.pop()
        data = files[source] if source in files else found[source]
        text = data.decode()
        for target in INCLUDE_RE.findall(text):
            relative = inside(root, root / Path(source).parent / target)
            require(relative in paths or "results" in Path(relative).parts,
                    root / relative, "source include must be registered or generated under results")
            if relative not in files and relative not in found:
                found[relative] = read_file(root / relative)
                pending.append(relative)
    return found


def inspect_config(root: Path, files: dict[str, bytes], state: dict) -> None:
    paths = state["project"]["render"]
    included = included_files(root, files, paths)
    files = {**files, **included}
    with tempfile.TemporaryDirectory(prefix=".cse-inspect-", dir=root.parent) as directory:
        shadow = Path(directory)
        try:
            config_files = [*CONFIG_FILES]
            if "_variables.yml" in files:
                config_files.append("_variables.yml")
            for name in [*config_files, *paths, *included]:
                target = shadow / name
                target.parent.mkdir(parents=True, exist_ok=True)
                if (root / name).is_file() and (root / name).read_bytes() == files[name]:
                    shutil.copyfile(root / name, target)
                else:
                    target.write_bytes(files[name])
            for presentation in (False, True):
                command = ["quarto", "inspect", str(shadow)] + (["--profile", "presentation"] if presentation else [])
                result = subprocess.run(command, cwd=shadow, text=True, capture_output=True)
                require(result.returncode == 0, root,
                        f"native inspection of {[str(root / p) for p in paths]} failed: {result.stderr.replace(directory, str(root))}")
                report = read_json(result.stdout.encode(), root / "_quarto.yml")
                owners = [inside(shadow, Path(p)) for p in report["files"]["config"]]
                inputs = [inside(shadow, Path(p)) for p in report["files"]["input"]]
                expected_owners = [*(CONFIG_FILES if presentation else CONFIG_FILES[:2])]
                if "_variables.yml" in files:
                    expected_owners.append("_variables.yml")
                require(owners == expected_owners, root, f"unexpected configuration paths: {owners}")
                require(sorted(inputs) == sorted(paths), root, f"unexpected native input paths: {inputs}")
                config = report["config"]
                project, execution = config["project"], config["execute"]
                require(project["type"] == "website" and project["output-dir"] == "_site"
                        and project["render"] == paths and config["website"]["sidebar"] == state["website"]["sidebar"],
                        root, "native publication contract differs")
                require(execution["enabled"] is presentation and config["format"]["html"]["embed-resources"] is not presentation
                        and (not presentation or (execution.get("cache") is True and execution.get("daemon") is False)), root, "native execution contract differs")
                for name, info in report["fileInformation"].items():
                    require(name in paths, root / name, "unsupported source include")
                    for mapping in info.get("includeMap") or []:
                        target = Path(name).parent / mapping["target"]
                        target = inside(shadow, shadow / target)
                        require(target in paths or target in included, root / target,
                                "unsupported source include")
                    check_owners(info["metadata"], root / name)
        except (KeyError, TypeError, ValueError, ManuscriptError) as exc:
            raise ManuscriptError(f"{root}: inspection refused: {str(exc).replace(directory, str(root))}") from exc


def validate_root(root: Path, pending: dict[str, bytes] | None = None) -> dict:
    check_boundary(root)
    pending = pending or {}
    files = {}
    for name in REQUIRED_FILES:
        reject_symlink(root / name)
        files[name] = pending[name] if name in pending else read_file(root / name)
    state = metadata(files["_cse-manuscript.json"], root / "_cse-manuscript.json")
    identity = read_json(files[".cse-quarto-source.json"], root / ".cse-quarto-source.json")
    require(set(identity) == {"sourceCommit", "runtimeTreeSha256"}
            and all(isinstance(v, str) and v.strip() for v in identity.values()), root / ".cse-quarto-source.json", "invalid source identity")
    require(set(REQUIRED_IGNORES) <= set(files[".gitignore"].decode().splitlines()), root / ".gitignore", "missing ignore rules")
    for name in ("_quarto.yml", "_quarto-presentation.yml"):
        config = read_json(files[name], root / name)
        execution = config.pop("execute", {})
        profile = name == "_quarto-presentation.yml"
        require(isinstance(execution, dict) and execution.get("enabled") is profile,
                root / name, "incorrect execution setting")
        require(set(execution) <= {"enabled", "daemon", "cache", "echo", "warning", "error"}
                and execution.get("error", False) is False
                and (not profile or (execution.get("daemon") is False and execution.get("cache") is True)), root / name, "unsupported execution settings")
        if not profile:
            require(config.pop("metadata-files", None) == ["_cse-manuscript.json"], root / name, "expected sole metadata include")
            project, website = config.pop("project", {}), config.pop("website", {})
            require(project == SITE_CONFIG["project"], root / name, "competing publication owner")
            require(isinstance(website, dict) and "sidebar" not in website, root / name,
                    "the sidebar is owned by _cse-manuscript.json")
            check_owners(website, root / name)
            formats = config.get("format", {})
            require(isinstance(formats, dict) and next(iter(formats), None) == "html"
                    and isinstance(formats["html"], dict) and formats["html"].get("embed-resources") is True,
                    root / name, "HTML must be the default format and embed resources")
        check_owners(config, root / name, allow_presentation_hook=profile)
    if (root / "_variables.yml").is_file():
        files["_variables.yml"] = read_file(root / "_variables.yml")
    for name in state["project"]["render"]:
        relative = inside(root, root / name)
        require(relative == name and name.endswith(".qmd") and not any(c in name for c in "*?[]!"), root / name, "expected literal relative QMD path")
        files[name] = pending[name] if name in pending else read_file(root / name)
        require(files[name].strip(), root / name, "empty publication source")
    for entry in page_sections(state):
        page = entry["contents"][0]["href"]
        require(re.fullmatch(r"[A-Za-z0-9._/-]+", page), root / page,
                "page path may contain only letters, digits, '.', '_', '-', and '/'")
        require(entry["contents"] == sections(root, page, files[page]), root / page,
                "sidebar sections no longer match the page headings; run `python3 manuscript.py sync .`")
    inspect_config(root, files, state)
    return state


def atomic_write(path: Path, data: bytes) -> None:
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".cse-manuscript-", delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def init(root: Path, article: Path, source_commit: str, runtime_tree_sha256: str) -> tuple[Path, list[str]]:
    """Create or adopt a root; on a managed root, also replace the plugin-owned TOOLING_FILES."""
    root = root_path(root, must_exist=False)
    check_boundary(root)
    managed = (root / "_cse-manuscript.json").is_file()
    replaced = []
    require(not (root / ".cse-quarto-source.json").exists() or managed,
            root / "_cse-manuscript.json", "cannot reconstruct missing managed membership")
    require(article.suffix == ".qmd", article, "article must be a populated QMD")
    files = {name: read_file(ASSET_ROOT / name) for name in ("_quarto-presentation.yml", "render.sh", "manuscript.py", SITE_CSS)}
    files.update({"_quarto.yml": json_bytes(SITE_CONFIG), "index.qmd": read_file(article.absolute()),
                  "_cse-manuscript.json": json_bytes({"project": {"render": ["index.qmd"]},
                                                           "website": {"sidebar": {"style": "docked", "collapse-level": 1,
                                                                                   "contents": [home_section(root, read_file(article.absolute()))]}}}),
                  ".cse-quarto-source.json": json_bytes({"sourceCommit": source_commit, "runtimeTreeSha256": runtime_tree_sha256}),
                  ".gitignore": ("\n".join(REQUIRED_IGNORES) + "\n").encode()})
    for name, data in files.items():
        target = root / name
        reject_symlink(target)
        if not target.exists():
            continue
        existing = read_file(target)
        if managed and name in TOOLING_FILES:
            if existing != data:
                replaced.append(name)
        elif name == ".gitignore":
            missing = [n for n in REQUIRED_IGNORES if n not in existing.decode().splitlines()]
            files[name] = existing + (("" if existing.endswith(b"\n") or not existing else "\n") + "\n".join(missing) + "\n").encode() if missing else existing
        else:
            if name == ".cse-quarto-source.json":
                require(read_json(existing, target) == read_json(data, target), target, "conflicting source identity")
            elif name not in (*CONFIG_FILES, SITE_CSS):
                require(existing == data, target, "refusing to overwrite existing file")
            files[name] = existing
    validate_root(root, files)
    with tempfile.TemporaryDirectory(prefix=".cse-init-", dir=root.parent) as directory:
        staging = Path(directory) / "payload"
        staging.mkdir()
        for name, data in files.items():
            (staging / name).write_bytes(data)
            if name in {"render.sh", "manuscript.py"}:
                (staging / name).chmod(0o755)
        if not root.exists():
            os.replace(staging, root)
        else:
            installed = []
            try:
                for name in files:
                    if name != ".gitignore" and not (root / name).exists():
                        os.replace(staging / name, root / name)
                        installed.append(root / name)
                    elif name in replaced:
                        os.replace(staging / name, root / name)
                if not (root / ".gitignore").exists() or read_file(root / ".gitignore") != files[".gitignore"]:
                    atomic_write(root / ".gitignore", files[".gitignore"])
            except OSError:
                for path in reversed(installed):
                    path.unlink()
                raise
    return root, replaced


def notebook_argument(root: Path, value: Path) -> str:
    relative = inside(root, value)
    require(relative.endswith(".qmd") and relative != "index.qmd", value, "expected analysis QMD notebook")
    # Quarto's preview render request addresses the page by its raw path, so keep it URL-safe.
    require(re.fullmatch(r"[A-Za-z0-9._/-]+", relative), value,
            "notebook path may contain only letters, digits, '.', '_', '-', and '/'")
    require(read_file(root / relative).strip(), value, "empty notebook")
    return relative


def include(root: Path, notebook: Path, title: str, group: str | None = None) -> Path:
    root = root_path(root)
    require(title.strip() and (group is None or group.strip()), notebook, "empty notebook title or group")
    relative = notebook_argument(root, notebook)
    # Read the membership directly: include is what repairs stale sidebar sections.
    state = metadata(read_file(root / "_cse-manuscript.json"), root / "_cse-manuscript.json")
    entry = {"section": title, "contents": [{"text": "Overview", "href": relative}]}
    contents = state["website"]["sidebar"]["contents"]
    def locate(entries: list) -> tuple[list, int] | None:
        for i, e in enumerate(entries):
            hit = locate(e["contents"]) if is_group(e) else (entries, i) if e["contents"][0]["href"] == relative else None
            if hit:
                return hit
        return None

    def prune(entries: list) -> list:
        kept = []
        for e in entries:
            if not e["contents"] or is_group(e):
                e["contents"] = prune(e["contents"])
            if e["contents"]:
                kept.append(e)
        return kept

    current = locate(contents)
    target = contents
    for name in [part.strip() for part in group.split("/")] if group is not None else []:
        require(name, notebook, "empty group name")
        found = next((e for e in target[1 if target is contents else 0:] if e["section"] == name and e["contents"]
                      and is_group(e)), None)
        if found is None:
            found = {"section": name, "contents": []}
            target.append(found)
        target = found["contents"]
    if current and current[0] is target:
        target[current[1]] = entry
    else:
        if current:
            del current[0][current[1]]
        target.append(entry)
    contents[1:] = prune(contents[1:])
    refresh_sections(root, state)
    state["project"]["render"] = ["index.qmd", *[n["href"] for n in notebooks(state)]]
    data = json_bytes(state)
    validate_root(root, {"_cse-manuscript.json": data})
    if data != read_file(root / "_cse-manuscript.json"):
        atomic_write(root / "_cse-manuscript.json", data)
    return root / relative


def sync(root: Path) -> dict:
    """Bring every sidebar section up to date with its page headings, then validate."""
    root = root_path(root)
    state = metadata(read_file(root / "_cse-manuscript.json"), root / "_cse-manuscript.json")
    refresh_sections(root, state)
    data = json_bytes(state)
    validate_root(root, {"_cse-manuscript.json": data})
    if data != read_file(root / "_cse-manuscript.json"):
        atomic_write(root / "_cse-manuscript.json", data)
    return state


def presentation_workflows(root: Path) -> list[Path]:
    workflows = []
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [name for name in dirs if not ignored_watch_part(name)]
        if "Snakefile" in files:
            workflows.append(Path(directory))
    return sorted(workflows)


def ignored_watch_part(name: str) -> bool:
    return name in IGNORED_WATCH_PARTS or name.endswith(IGNORED_WATCH_SUFFIXES)


def planned_rules(result: subprocess.CompletedProcess) -> set[str] | None:
    output = result.stdout or ""
    decoder = json.JSONDecoder()
    offset = 0
    while True:
        start = output.find("{", offset)
        if start < 0:
            return None
        try:
            plan, end = decoder.raw_decode(output, start)
        except json.JSONDecodeError:
            offset = start + 1
            continue
        if isinstance(plan, dict) and "nodes" in plan:
            if output[end:].strip():
                return None
            nodes = plan["nodes"]
            break
        offset = end
    if not isinstance(nodes, list):
        return None
    rules = set()
    for node in nodes:
        try:
            rule = node["value"]["rule"]
        except (KeyError, TypeError):
            return None
        if not isinstance(rule, str) or not rule:
            return None
        rules.add(rule)
    return rules


def check_presentation_plan(workflow: Path) -> int:
    result = subprocess.run(
        ["snakemake", "--cores", "1", "--dry-run", "--quiet", "--d3dag", "present"],
        cwd=workflow,
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode:
        detail = (result.stderr or "").strip()
        print(f"presentation dry-run failed in {workflow}: {detail}", file=sys.stderr)
        return result.returncode
    rules = planned_rules(result)
    if rules != {"present"}:
        extra = sorted(rules - {"present"}) if rules is not None else []
        detail = f"extra jobs refused: {', '.join(extra)}" if extra else "could not verify a present-only job plan"
        print(f"presentation refused in {workflow}; {detail}", file=sys.stderr)
        return 1
    return 0


def prepare(root: Path) -> int:
    root = root_path(root)
    workflows = presentation_workflows(root)
    requested = [Path(value) for value in os.environ.get("QUARTO_PROJECT_INPUT_FILES", "").splitlines() if value]
    requested = [path if path.is_absolute() else root / path for path in requested]
    if requested and root / "index.qmd" not in requested:
        workflows = [workflow for workflow in workflows
                     if any(path == workflow or path.is_relative_to(workflow) for path in requested)]
    for workflow in workflows:
        status = check_presentation_plan(workflow)
        if status:
            return status
        result = subprocess.run(["snakemake", "--cores", "1", "present"], cwd=workflow, check=False)
        if result.returncode:
            print(f"presentation failed in {workflow}; retained view is stale", file=sys.stderr)
            return result.returncode
    return 0


def is_watchable(path: Path, root: Path) -> bool:
    try:
        relative = path.absolute().relative_to(root)
    except ValueError:
        return False
    return not any(ignored_watch_part(part) for part in relative.parts) and not (
        # Quarto writes these render byproducts beside sources; watching them re-triggers renders.
        path.name.startswith(".") or path.name.endswith(".html")
        or path.name in {"manuscript.py", "render.sh"}
    )


def watch_snapshot(root: Path) -> dict[Path, tuple[int, int]]:
    # ponytail: bounded polling scan; use a platform watcher only if project size makes it measurable.
    snapshot = {}
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [name for name in dirs if not ignored_watch_part(name)]
        for name in files:
            path = Path(directory) / name
            if not is_watchable(path, root):
                continue
            try:
                info = path.stat()
            except FileNotFoundError:
                continue
            snapshot[path] = (info.st_mtime_ns, info.st_size)
    return snapshot


def changed_paths(before: dict[Path, tuple[int, int]], after: dict[Path, tuple[int, int]]) -> set[Path]:
    return {path for path in before.keys() | after.keys() if before.get(path) != after.get(path)}


def presentation_targets(root: Path, state: dict, changed: set[Path]) -> set[Path]:
    article = root / "index.qmd"
    pages = [root / entry["href"] for entry in notebooks(state)]
    targets = set()
    for path in changed:
        # Native preview already re-renders an edited page source.
        if not is_watchable(path, root) or path == article or path in pages:
            continue
        matched = [page for page in pages if path.is_relative_to(page.parent)]
        if matched:
            targets.update(matched)
            targets.add(article)
        elif len(path.relative_to(root).parts) == 1:
            targets.update(pages)
            targets.add(article)
    return targets


def request_renders(root: Path, targets: set[Path], host: str, port: int) -> None:
    host = "127.0.0.1" if host in {"0.0.0.0", "::", ""} else host
    for path in sorted(targets):
        if path.is_file():
            url = f"http://{host}:{port}/{QUARTO_RENDER_REQUEST}/{path.relative_to(root).as_posix()}"
            with urllib.request.urlopen(url, timeout=10) as response:
                if response.read() != b"rendered":
                    raise OSError(f"preview refused to render {path}")


def prepare_and_render(root: Path, state: dict, changed: set[Path], host: str, port: int) -> int:
    try:
        status = prepare(root)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"presentation refresh error in {root}: {exc}; retained pages remain stale", file=sys.stderr)
        return 1
    if status:
        print(f"presentation refresh failed in {root} (exit {status}); retained pages remain stale", file=sys.stderr)
        return status
    try:
        request_renders(root, presentation_targets(root, state, changed), host, port)
    except OSError as exc:
        print(f"preview render request failed in {root}: {exc}; retained pages remain stale", file=sys.stderr)
        return 1
    return 0


def workflows_running(root: Path) -> bool:
    # Snakemake removes a rule's outputs before running it, so never present mid-calculation.
    return any(any((workflow / ".snakemake" / "locks").glob("*"))
               for workflow in presentation_workflows(root))


def wait_for_server(process: subprocess.Popen, host: str, port: int) -> None:
    host = "127.0.0.1" if host in {"0.0.0.0", "::", ""} else host
    while process.poll() is None:
        with socket.socket() as probe:
            if probe.connect_ex((host, port)) == 0:
                return
        time.sleep(WATCH_INTERVAL_SECONDS)


def stop_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()


def refresh(root: Path, notebook: Path) -> int:
    root = root_path(root)
    state = sync(root)
    relative = notebook_argument(root, notebook)
    require(relative in state["project"]["render"], notebook, "not an included notebook")
    status = prepare(root)
    if status:
        return status
    for target in (relative, "index.qmd"):
        result = subprocess.run(
            ["quarto", "render", target, "--to", "html", "--profile", "presentation", "--cache-refresh"], cwd=root
        )
        if result.returncode:
            return result.returncode
    return 0


def preview(root: Path, host: str, port: int) -> int:
    root = root_path(root)
    state = sync(root)
    require(1 <= port <= 65535, root, "port must be between 1 and 65535")
    # Quarto silently picks another port when this one is busy, so render requests would miss it.
    with socket.socket() as probe:
        require(probe.connect_ex((host if host not in {"0.0.0.0", "::", ""} else "127.0.0.1", port)) != 0,
                root, f"port {port} is already in use; pass --port with a free port")
    command = ["quarto", "preview", "--to", "html", "--profile", "presentation", "--no-browser",
               "--host", host, "--port", str(port)]
    process = subprocess.Popen(command, cwd=root, start_new_session=True)
    def handle_sigterm(signum, frame):
        raise KeyboardInterrupt

    previous_sigterm = signal.signal(signal.SIGTERM, handle_sigterm)
    try:
        if not presentation_workflows(root):
            return process.wait()
        wait_for_server(process, host, port)
        snapshot = watch_snapshot(root)
        while process.poll() is None:
            time.sleep(WATCH_INTERVAL_SECONDS)
            current = watch_snapshot(root)
            pending = changed_paths(snapshot, current)
            snapshot = current
            if not pending:
                continue
            waiting = False
            while process.poll() is None:
                time.sleep(WATCH_SETTLE_SECONDS)
                current = watch_snapshot(root)
                new = changed_paths(snapshot, current)
                snapshot = current
                running = workflows_running(root)
                if running and not new and not waiting:
                    waiting = True
                    print(f"preview waiting for a Snakemake lock under {root}; if no run is active, "
                          "run `snakemake --unlock` in that analysis", file=sys.stderr)
                if not new and not running:
                    break
                pending.update(new)
            if any(path.suffix == ".qmd" for path in pending):
                try:
                    state = sync(root)
                except ManuscriptError as exc:
                    print(f"sidebar sync failed: {exc}", file=sys.stderr)
            prepare_and_render(root, state, pending, host, port)
            snapshot = watch_snapshot(root)
        return process.wait()
    except KeyboardInterrupt:
        return 130
    finally:
        signal.signal(signal.SIGTERM, previous_sigterm)
        stop_process(process)


def git_path(root: Path, *arguments: str) -> Path:
    result = subprocess.run(["git", "-C", str(root), "rev-parse", "--path-format=absolute", *arguments],
                            check=False, text=True, capture_output=True)
    require(not result.returncode, root, f"not a Git checkout: {result.stderr.strip()}")
    return Path(result.stdout.strip()).resolve()


def service_port(unit: Path) -> int | None:
    match = SERVICE_PORT_RE.search(unit.read_text()) if unit.is_file() else None
    return int(match.group(1)) if match else None


def port_free(port: int) -> bool:
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def unit_value(value: str, what: str) -> str:
    require(not UNIT_UNSAFE_RE.search(value), Path(value), f"{what} has characters unsafe in a systemd unit")
    return value


def answering(url: str) -> bool:
    deadline = time.monotonic() + SERVICE_READY_SECONDS
    while True:
        try:
            with urllib.request.urlopen(url, timeout=1):
                return True
        except OSError:
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.5)


def service(root: Path, port: int | None, dry_run: bool, python: Path = Path(sys.executable)) -> int:
    root = root_path(root)
    sync(root)
    quarto = shutil.which("quarto")
    require(quarto, root, "quarto renderer unavailable on PATH")
    repository = git_path(root, "--show-toplevel")
    require(git_path(root, "--git-dir") == git_path(root, "--git-common-dir"), root,
            "the preview service serves the main checkout; run it there, not in a worktree")
    python = python.absolute()
    path = list(dict.fromkeys([str(python.parent), str(Path(quarto).parent), "/usr/local/bin", "/usr/bin", "/bin"]))
    for value, what in ((str(repository), "repository path"), (root.relative_to(repository).as_posix(), "manuscript path"),
                        (str(python), "interpreter path"), *((entry, "PATH entry") for entry in path)):
        unit_value(value, what)
    require(python.is_file() and os.access(python, os.X_OK), python, "interpreter is not an executable file")
    imports = subprocess.run([str(python), "-c", f"import {PREVIEW_IMPORTS}"], check=False, capture_output=True, text=True)
    require(not imports.returncode, python, f"interpreter cannot import {PREVIEW_IMPORTS} for the presentation profile")
    require(not presentation_workflows(root) or shutil.which("snakemake", path=":".join(path)), python.parent,
            "snakemake is required by a presentation workflow but absent from the unit PATH")
    digest = hashlib.sha256(str(repository).encode()).hexdigest()
    units = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "systemd" / "user"
    unit = units / f"cse-preview-{re.sub(r'[^A-Za-z0-9_.-]', '-', repository.name)}-{digest[:8]}.service"
    existing = unit.read_text() if unit.is_file() else None
    require(existing is None or (existing.startswith(SERVICE_MARKER)
                                 and f"\nWorkingDirectory={repository}\n" in existing),
            unit, "refusing to overwrite a unit this command did not write for this repository")
    current = service_port(unit)
    claimed = {service_port(other) for other in units.glob("cse-preview-*.service") if other != unit}
    if port is None:
        port = current
    if port is None:
        candidates = (SERVICE_PORT_BASE + (int(digest, 16) + step) % SERVICE_PORT_SPAN for step in range(SERVICE_PORT_SPAN))
        port = next((value for value in candidates if value not in claimed and port_free(value)), None)
        require(port, unit, "no free preview port")
    require(1 <= port <= 65535 and port not in claimed and (port == current or port_free(port)),
            unit, f"port {port} is in use or claimed by another preview unit")
    text = read_file(ASSET_ROOT / "preview.service").decode().format(
        repository=repository, manuscript=root.relative_to(repository).as_posix(), port=port,
        python=python, path=":".join(path))
    url = f"http://127.0.0.1:{port}/"
    if dry_run:
        print(f"{unit}\n{text}{url}")
        return 0
    try:
        subprocess.run(["systemctl", "--user", "show-environment"], check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ManuscriptError(f"systemd user manager unavailable (systemctl --user show-environment failed: {exc})")
    if text != existing:
        unit.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(unit, text.encode())
    for action in ("daemon-reload", "enable", "restart" if text != existing else "start"):
        subprocess.run(["systemctl", "--user", action, *([] if action == "daemon-reload" else [unit.name])], check=True)
    if answering(url):
        print(f"{unit.name} serving {url}")
        return 0
    print(f"{unit.name} started, not answering at {url}; see `journalctl --user -u {unit.name}`")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(prog="manuscript.py")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "include", "validate", "sync", "refresh", "preview", "prepare", "service"):
        command = commands.add_parser(name)
        if name == "prepare":
            command.add_argument("root", type=Path, nargs="?", default=Path("."))
        else:
            command.add_argument("root", type=Path)
        if name == "init":
            command.add_argument("--article-source", type=Path, required=True)
            command.add_argument("--source-commit", required=True)
            command.add_argument("--runtime-tree-sha256", required=True)
        if name in {"include", "refresh"}:
            command.add_argument("notebook", type=Path)
        if name == "include":
            command.add_argument("--title", required=True)
            command.add_argument("--group", help="optional sidebar group; nest with '/', e.g. 'Bundle/Active formulation'")
        if name == "preview":
            command.add_argument("--host", default="127.0.0.1")
            command.add_argument("--port", type=int, default=8000)
        if name == "service":
            command.add_argument("--port", type=int)
            command.add_argument("--dry-run", action="store_true")
            command.add_argument("--python", type=Path, default=Path(sys.executable))
    args = parser.parse_args()
    try:
        if args.command == "init":
            root, replaced = init(args.root, args.article_source, args.source_commit, args.runtime_tree_sha256)
            print(root)
            for name in replaced:
                print(f"replaced: {root / name}")
        elif args.command == "include":
            print(include(args.root, args.notebook, args.title, args.group))
        elif args.command == "sync":
            sync(args.root)
            print("synced")
        elif args.command == "validate":
            validate_root(root_path(args.root))
            print("valid")
        elif args.command == "prepare":
            return prepare(args.root)
        elif args.command == "refresh":
            return refresh(args.root, args.notebook)
        elif args.command == "service":
            return service(args.root, args.port, args.dry_run, args.python)
        else:
            return preview(args.root, args.host, args.port)
        return 0
    except (ManuscriptError, OSError, ValueError, TypeError, AttributeError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"manuscript failed: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
