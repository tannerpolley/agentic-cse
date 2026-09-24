#!/usr/bin/env python3
"""Manage one native Quarto Manuscript with explicit publication membership."""
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
REQUIRED_FILES = (*CONFIG_FILES, "index.qmd", ".cse-quarto-source.json",
                  ".gitignore", "render.sh", "manuscript.py")
REQUIRED_IGNORES = ("/.quarto/", "/_site/", "/_freeze/", "/notebook.tex")
MANUSCRIPT_CONFIG = {
    "project": {"type": "manuscript", "output-dir": "_site"},
    "metadata-files": ["_cse-manuscript.json"], "manuscript": {"article": "index.qmd"},
    "format": {"html": {"embed-resources": True}}, "execute": {"enabled": False},
    "keep-md": True,
}
PRESENTATION_PRE_RENDER = "python3 manuscript.py prepare"
WATCH_INTERVAL_SECONDS = 0.25
WATCH_SETTLE_SECONDS = 0.25
IGNORED_WATCH_PARTS = {".git", ".quarto", "_site", "_freeze", "__pycache__", ".ipynb_checkpoints"}
IGNORED_WATCH_PARTS |= {".snakemake", ".cache", "tmp", "temp", "support"}
IGNORED_WATCH_SUFFIXES = ("_files", "_support")
INCLUDE_RE = re.compile(r"\{\{<\s*include\s+([^\s>]+)")
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


def metadata(data: bytes, path: Path) -> dict:
    state = read_json(data, path)
    require(set(state) == {"project", "manuscript"}, path, "unsupported membership fields")
    project, manuscript = state["project"], state["manuscript"]
    require(isinstance(project, dict) and set(project) == {"render"}
            and isinstance(manuscript, dict) and set(manuscript) == {"notebooks"}, path, "invalid membership owners")
    render, notebooks = project["render"], manuscript["notebooks"]
    require(isinstance(render, list) and all(isinstance(p, str) for p in render)
            and len(render) == len(set(render)), path, "render membership must be unique")
    require(isinstance(notebooks, list), path, "notebooks must be a list")
    for entry in notebooks:
        require(isinstance(entry, dict) and set(entry) == {"notebook", "title"}
                and all(isinstance(v, str) and v.strip() for v in entry.values()), path, "invalid notebook path/title")
    require(render == ["index.qmd", *[n["notebook"] for n in notebooks]], path, "ordered memberships disagree")
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
                project, manuscript, execution = config["project"], config["manuscript"], config["execute"]
                require(project["type"] == "manuscript" and project["output-dir"] == "_site"
                        and manuscript["article"] == "index.qmd" and sorted(project["render"]) == sorted(paths)
                        and sorted(manuscript["notebooks"], key=lambda n: n["notebook"])
                        == sorted(state["manuscript"]["notebooks"], key=lambda n: n["notebook"]), root, "native publication contract differs")
                require(execution["enabled"] is presentation and config["format"]["html"]["embed-resources"] is True
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
            require(config.pop("keep-md", None) is True, root / name,
                    "keep-md must preserve native embedded notebook outputs")
            require(config.pop("metadata-files", None) == ["_cse-manuscript.json"], root / name, "expected sole metadata include")
            project, manuscript = config.pop("project", {}), config.pop("manuscript", {})
            require(project == MANUSCRIPT_CONFIG["project"] and manuscript == MANUSCRIPT_CONFIG["manuscript"], root / name, "competing publication owner")
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


def init(root: Path, article: Path, source_commit: str, runtime_tree_sha256: str) -> Path:
    root = root_path(root, must_exist=False)
    check_boundary(root)
    require(not (root / ".cse-quarto-source.json").exists() or (root / "_cse-manuscript.json").is_file(),
            root / "_cse-manuscript.json", "cannot reconstruct missing managed membership")
    require(article.suffix == ".qmd", article, "article must be a populated QMD")
    files = {name: read_file(ASSET_ROOT / name) for name in ("_quarto-presentation.yml", "render.sh", "manuscript.py")}
    files.update({"_quarto.yml": json_bytes(MANUSCRIPT_CONFIG), "index.qmd": read_file(article.absolute()),
                  "_cse-manuscript.json": json_bytes({"project": {"render": ["index.qmd"]}, "manuscript": {"notebooks": []}}),
                  ".cse-quarto-source.json": json_bytes({"sourceCommit": source_commit, "runtimeTreeSha256": runtime_tree_sha256}),
                  ".gitignore": ("\n".join(REQUIRED_IGNORES) + "\n").encode()})
    for name, data in files.items():
        target = root / name
        reject_symlink(target)
        if not target.exists():
            continue
        existing = read_file(target)
        if name == ".gitignore":
            missing = [n for n in REQUIRED_IGNORES if n not in existing.decode().splitlines()]
            files[name] = existing + (("" if existing.endswith(b"\n") or not existing else "\n") + "\n".join(missing) + "\n").encode() if missing else existing
        else:
            if name == ".cse-quarto-source.json":
                require(read_json(existing, target) == read_json(data, target), target, "conflicting source identity")
            elif name not in CONFIG_FILES:
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
                if not (root / ".gitignore").exists() or read_file(root / ".gitignore") != files[".gitignore"]:
                    atomic_write(root / ".gitignore", files[".gitignore"])
            except OSError:
                for path in reversed(installed):
                    path.unlink()
                raise
    return root


def notebook_argument(root: Path, value: Path) -> str:
    relative = inside(root, value)
    require(relative.endswith(".qmd") and relative != "index.qmd", value, "expected analysis QMD notebook")
    require(read_file(root / relative).strip(), value, "empty notebook")
    return relative


def include(root: Path, notebook: Path, title: str) -> Path:
    root = root_path(root)
    require(title.strip(), notebook, "empty notebook title")
    relative = notebook_argument(root, notebook)
    state = validate_root(root)
    entries = state["manuscript"]["notebooks"]
    found = next((n for n in entries if n["notebook"] == relative), None)
    if found and found["title"] == title:
        return root / relative
    if found:
        found["title"] = title
    else:
        entries.append({"notebook": relative, "title": title})
        state["project"]["render"].append(relative)
    data = json_bytes(state)
    validate_root(root, {"_cse-manuscript.json": data})
    atomic_write(root / "_cse-manuscript.json", data)
    return root / relative


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
        path.name.startswith(".") or path.name.endswith(".html.md")
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
    notebooks = [root / entry["notebook"] for entry in state["manuscript"]["notebooks"]]
    targets = set()
    for path in changed:
        if not is_watchable(path, root) or path == article:
            continue
        if path in notebooks:
            targets.add(article)
            continue
        matched = [notebook for notebook in notebooks if path.is_relative_to(notebook.parent)]
        if matched:
            targets.update(matched)
            targets.add(article)
        elif len(path.relative_to(root).parts) == 1:
            targets.update(notebooks)
            targets.add(article)
    return targets


def touch_targets(targets: set[Path]) -> None:
    for path in targets:
        if path.is_file():
            os.utime(path, None)


def prepare_and_touch(root: Path, state: dict, changed: set[Path]) -> int:
    try:
        status = prepare(root)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"presentation refresh error in {root}: {exc}; retained pages remain stale", file=sys.stderr)
        return 1
    if status:
        print(f"presentation refresh failed in {root} (exit {status}); retained pages remain stale", file=sys.stderr)
        return status
    touch_targets(presentation_targets(root, state, changed))
    return 0


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
    state = validate_root(root)
    relative = notebook_argument(root, notebook)
    require(relative in state["project"]["render"], notebook, "not an included notebook")
    status = prepare(root)
    if status:
        return status
    for target in (relative, "index.qmd"):
        result = subprocess.run(
            ["quarto", "render", target, "--profile", "presentation", "--cache-refresh"], cwd=root
        )
        if result.returncode:
            return result.returncode
    return 0


def preview(root: Path, host: str, port: int) -> int:
    root = root_path(root)
    state = validate_root(root)
    require(1 <= port <= 65535, root, "port must be between 1 and 65535")
    command = ["quarto", "preview", "--profile", "presentation", "--no-browser",
               "--host", host, "--port", str(port)]
    process = subprocess.Popen(command, cwd=root, start_new_session=True)
    def handle_sigterm(signum, frame):
        raise KeyboardInterrupt

    previous_sigterm = signal.signal(signal.SIGTERM, handle_sigterm)
    try:
        if not presentation_workflows(root):
            return process.wait()
        snapshot = watch_snapshot(root)
        while process.poll() is None:
            time.sleep(WATCH_INTERVAL_SECONDS)
            current = watch_snapshot(root)
            pending = changed_paths(snapshot, current)
            snapshot = current
            if not pending:
                continue
            while process.poll() is None:
                time.sleep(WATCH_SETTLE_SECONDS)
                current = watch_snapshot(root)
                new = changed_paths(snapshot, current)
                snapshot = current
                if not new:
                    break
                pending.update(new)
            prepare_and_touch(root, state, pending)
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
    validate_root(root)
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
    for name in ("init", "include", "validate", "refresh", "preview", "prepare", "service"):
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
            print(init(args.root, args.article_source, args.source_commit, args.runtime_tree_sha256))
        elif args.command == "include":
            print(include(args.root, args.notebook, args.title))
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
