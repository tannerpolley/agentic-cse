#!/usr/bin/env python3
"""Report Git change composition for CSE Review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys


CATEGORIES = ("executable", "tests", "documents", "generated", "other")
GENERATED_PARTS = {"dist", "generated", "_build", "site"}
TEST_PARTS = {"test", "tests", "testing"}
DOCUMENT_SUFFIXES = {".adoc", ".bib", ".md", ".qmd", ".rst", ".tex", ".txt"}
EXECUTABLE_SUFFIXES = {
    ".bash", ".c", ".cc", ".cpp", ".cs", ".cxx", ".f", ".f90",
    ".f95", ".fish", ".for", ".go", ".h", ".hpp", ".ipynb", ".java",
    ".jl", ".js", ".jsx", ".kt", ".kts", ".lua", ".m", ".mm", ".php",
    ".pl", ".py", ".pyi", ".pyx", ".r", ".rb", ".rs", ".scala", ".sh",
    ".sql", ".swift", ".ts", ".tsx", ".zsh",
}


class AccountingError(RuntimeError):
    pass


def git(repo: Path, *arguments: str, binary: bool = False) -> bytes | str:
    result = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        capture_output=True,
        text=not binary,
        check=False,
    )
    if result.returncode:
        message = result.stderr.decode(errors="replace") if binary else result.stderr
        raise AccountingError(message.strip() or f"git {' '.join(arguments)} failed")
    return result.stdout


def classify(path: str) -> str:
    item = PurePosixPath(path)
    parts = {part.casefold() for part in item.parts[:-1]}
    name = item.name.casefold()
    suffix = item.suffix.casefold()
    if parts & GENERATED_PARTS:
        return "generated"
    if parts & TEST_PARTS or name.startswith("test_") or name.endswith(f"_test{suffix}"):
        return "tests"
    if suffix in DOCUMENT_SUFFIXES or name.startswith("readme"):
        return "documents"
    if suffix in EXECUTABLE_SUFFIXES:
        return "executable"
    return "other"


def detect_base(repo: Path) -> str:
    candidates: list[str] = []
    symbolic = subprocess.run(
        ["git", "-C", str(repo), "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if symbolic.returncode == 0 and symbolic.stdout.strip():
        candidates.append(symbolic.stdout.strip())
    candidates.extend(("origin/main", "main", "origin/master", "master"))
    for candidate in candidates:
        exists = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", f"{candidate}^{{commit}}"],
            capture_output=True,
            check=False,
        )
        if exists.returncode == 0:
            return candidate
    raise AccountingError("no default-branch base found; provide --base REF")


def text_line_count(path: Path) -> int | None:
    if path.is_symlink():
        return 1
    lines = 0
    saw_data = False
    ended_with_newline = True
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            if b"\0" in chunk:
                return None
            saw_data = True
            lines += chunk.count(b"\n")
            ended_with_newline = chunk.endswith(b"\n")
    return lines + int(saw_data and not ended_with_newline)


def collect(repo_argument: Path, base_argument: str | None) -> dict:
    try:
        root = Path(str(git(repo_argument, "rev-parse", "--show-toplevel")).strip()).resolve()
    except AccountingError as error:
        raise AccountingError(f"not a Git repository: {repo_argument}") from error

    requested_base = base_argument or detect_base(root)
    try:
        merge_base = str(git(root, "merge-base", "HEAD", requested_base)).strip()
    except AccountingError as error:
        raise AccountingError(f"cannot resolve merge base for {requested_base}: {error}") from error

    records: dict[str, dict] = {}
    raw = git(root, "diff", "--numstat", "--no-renames", "-z", merge_base, "--", binary=True)
    assert isinstance(raw, bytes)
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        added_raw, removed_raw, path_raw = entry.split(b"\t", 2)
        path = path_raw.decode(errors="surrogateescape")
        binary = added_raw == b"-" or removed_raw == b"-"
        records[path] = {
            "path": path,
            "category": classify(path),
            "additions": None if binary else int(added_raw),
            "removals": None if binary else int(removed_raw),
            "binary": binary,
            "untracked": False,
        }

    untracked = git(root, "ls-files", "--others", "--exclude-standard", "-z", binary=True)
    assert isinstance(untracked, bytes)
    for path_raw in untracked.split(b"\0"):
        if not path_raw:
            continue
        path = path_raw.decode(errors="surrogateescape")
        count = text_line_count(root / path)
        records[path] = {
            "path": path,
            "category": classify(path),
            "additions": count,
            "removals": 0 if count is not None else None,
            "binary": count is None,
            "untracked": True,
        }

    files = [records[path] for path in sorted(records)]
    categories = {}
    for category in CATEGORIES:
        selected = [record for record in files if record["category"] == category]
        categories[category] = {
            "files": len(selected),
            "additions": sum(record["additions"] or 0 for record in selected),
            "removals": sum(record["removals"] or 0 for record in selected),
            "binary_files": sum(record["binary"] for record in selected),
        }

    return {
        "repository": str(root),
        "requested_base": requested_base,
        "merge_base": merge_base,
        "scope": "merge base through HEAD, index, working tree, and untracked files",
        "categories": categories,
        "totals": {
            "files": len(files),
            "additions": sum(record["additions"] or 0 for record in files),
            "removals": sum(record["removals"] or 0 for record in files),
            "binary_files": sum(record["binary"] for record in files),
        },
        "files": files,
    }


def render(report: dict) -> str:
    lines = [
        "CSE change accounting",
        f"repository: {report['repository']}",
        f"requested base: {report['requested_base']}",
        f"merge base: {report['merge_base']}",
        f"scope: {report['scope']}",
        "categories:",
    ]
    for category in CATEGORIES:
        values = report["categories"][category]
        lines.append(
            f"  {category}: {values['files']} files, +{values['additions']} "
            f"-{values['removals']}, {values['binary_files']} binary"
        )
    lines.append("files:")
    for record in report["files"]:
        counts = "binary" if record["binary"] else f"+{record['additions']} -{record['removals']}"
        status = " untracked" if record["untracked"] else ""
        lines.append(f"  {record['category']}: {counts}{status} {record['path']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="Git worktree to inspect")
    parser.add_argument("--base", help="base branch, tag, or commit")
    parser.add_argument("--json", action="store_true", help="emit structured JSON")
    arguments = parser.parse_args()
    try:
        report = collect(arguments.repo, arguments.base)
    except AccountingError as error:
        print(f"change-accounting: {error}", file=sys.stderr)
        return 2
    if arguments.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
