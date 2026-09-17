#!/usr/bin/env python3
"""Manage one native Quarto Manuscript with explicit publication membership."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

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


def check_owners(value, path: Path) -> None:
    if isinstance(value, dict):
        forbidden = {"project", "manuscript", "website", "book", "render", "notebooks",
                     "pre-render", "post-render", "filters", "filter", "profile", "execute",
                     "metadata-files", "metadata-file", "engines", "engine", "knitr",
                     "output-file", "output-dir", "execute-dir", "keep-md",
                     "include-in-header", "include-before-body", "include-after-body"}
        require(not forbidden.intersection(value), path,
                f"competing configuration owner: {sorted(forbidden.intersection(value))}")
        for child in value.values():
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
            require(not (config and (Path(directory) != root or name not in CONFIG_FILES))
                    and not name.startswith(".env") and name != "_extensions", path, "unsupported inherited or nested configuration")


def inspect_config(root: Path, files: dict[str, bytes], state: dict) -> None:
    paths = state["project"]["render"]
    with tempfile.TemporaryDirectory(prefix=".cse-inspect-", dir=root.parent) as directory:
        shadow = Path(directory)
        try:
            for name in [*CONFIG_FILES, *paths]:
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
                require(owners == list(CONFIG_FILES if presentation else CONFIG_FILES[:2]), root, f"unexpected configuration paths: {owners}")
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
                    require(name in paths and not info["includeMap"], root / name, "unsupported source include")
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
        check_owners(config, root / name)
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


def refresh(root: Path, notebook: Path, external_results_changed: bool = False) -> int:
    root = root_path(root)
    state = validate_root(root)
    relative = notebook_argument(root, notebook)
    require(relative in state["project"]["render"], notebook, "not an included notebook")
    command = ["quarto", "render", relative, "--profile", "presentation"]
    return subprocess.run(command + (["--cache-refresh"] if external_results_changed else []), cwd=root).returncode


def preview(root: Path, host: str, port: int) -> int:
    root = root_path(root)
    validate_root(root)
    require(1 <= port <= 65535, root, "port must be between 1 and 65535")
    os.chdir(root)
    os.execvp("quarto", ["quarto", "preview", "--profile", "presentation", "--no-browser",
                           "--host", host, "--port", str(port)])
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(prog="manuscript.py")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "include", "validate", "refresh", "preview"):
        command = commands.add_parser(name)
        command.add_argument("root", type=Path)
        if name == "init":
            command.add_argument("--article-source", type=Path, required=True)
            command.add_argument("--source-commit", required=True)
            command.add_argument("--runtime-tree-sha256", required=True)
        if name in {"include", "refresh"}:
            command.add_argument("notebook", type=Path)
        if name == "include":
            command.add_argument("--title", required=True)
        if name == "refresh":
            command.add_argument("--external-results-changed", action="store_true")
        if name == "preview":
            command.add_argument("--host", default="127.0.0.1")
            command.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    try:
        if args.command == "init":
            print(init(args.root, args.article_source, args.source_commit, args.runtime_tree_sha256))
        elif args.command == "include":
            print(include(args.root, args.notebook, args.title))
        elif args.command == "validate":
            validate_root(root_path(args.root))
            print("valid")
        elif args.command == "refresh":
            return refresh(args.root, args.notebook, args.external_results_changed)
        else:
            return preview(args.root, args.host, args.port)
        return 0
    except (ManuscriptError, OSError, ValueError, TypeError, AttributeError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"manuscript failed: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
