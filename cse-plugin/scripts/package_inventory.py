#!/usr/bin/env python3
"""Canonical CSE package inventory, staging, and payload identity helpers."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PACKAGES = (
    {
        "name": "cse",
        "root": "plugin",
        "skills": (
            "audit", "setup", "research", "diagnose", "design", "build",
            "analyze", "summarize", "review", "write", "prose", "zotero", "data",
            "digitize", "plot", "tikz", "latex", "quarto", "beamer",
        ),
        "include": (
            ".codex-plugin", ".claude-plugin", "BANNED.md", "LICENSE", "README.md",
            "assets", "references", "scripts", "skills",
        ),
    },
)


def package(name: str) -> dict:
    try:
        return next(item for item in PACKAGES if item["name"] == name)
    except StopIteration as exc:
        raise ValueError(f"unknown CSE package: {name}") from exc


def source_root(item: dict) -> Path:
    return (ROOT / item["root"]).resolve()


def check_source(item: dict) -> None:
    root = source_root(item)
    for manifest_path in (root / ".codex-plugin/plugin.json", root / ".claude-plugin/plugin.json"):
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("name") != item["name"] or not manifest.get("description"):
            raise RuntimeError(f"{item['name']} requires its package name and description")
        if "version" in manifest:
            raise RuntimeError("CSE packages use source commits, not release numbers")
    for relative in item["include"]:
        if not (root / relative).exists():
            raise RuntimeError(f"{item['name']} payload is missing: {relative}")
    if sorted(path.name for path in (root / "skills").iterdir() if path.is_dir()) != sorted(item["skills"]):
        raise RuntimeError(f"{item['name']} skills disagree with the package inventory")


def source_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=False
    )
    if result.returncode != 0 or len(result.stdout.strip()) != 40:
        raise RuntimeError("cannot resolve the CSE source commit")
    return result.stdout.strip()


def runtime_payload(root: Path) -> dict[str, str]:
    payload: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if "__pycache__" in relative.parts or path.suffix == ".pyc":
            continue
        payload[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return payload


def runtime_tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for relative, value in runtime_payload(root).items():
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(value.encode())
        digest.update(b"\n")
    return digest.hexdigest()


def stage(item: dict, destination: Path, commit: str) -> dict:
    check_source(item)
    source = source_root(item)
    if destination.exists():
        raise RuntimeError(f"staging destination already exists: {destination}")
    destination.mkdir(parents=True)
    for relative in item["include"]:
        origin = source / relative
        if not origin.exists():
            raise RuntimeError(f"{item['name']} payload owner is missing: {relative}")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if origin.is_dir():
            shutil.copytree(origin, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))
        else:
            shutil.copy2(origin, target)
    manifest = json.loads((destination / ".codex-plugin/plugin.json").read_text())
    if manifest.get("name") != item["name"]:
        raise RuntimeError(f"{item['name']} manifest disagrees with the package inventory")
    skills = sorted(path.name for path in (destination / "skills").iterdir() if path.is_dir())
    if skills != sorted(item["skills"]):
        raise RuntimeError(f"{item['name']} staged skills are {skills}; expected {sorted(item['skills'])}")
    identity = {
        "pluginId": item["name"],
        "sourceCommit": commit,
        "runtimeTreeSha256": runtime_tree_hash(destination),
        "payloadSkills": list(item["skills"]),
    }
    return identity


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("inventory")
    subparsers.add_parser("list")
    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("package")
    stage_parser = subparsers.add_parser("stage")
    stage_parser.add_argument("package")
    stage_parser.add_argument("destination", type=Path)
    stage_parser.add_argument("--commit")
    args = parser.parse_args()
    if args.command == "inventory":
        print(json.dumps({"packages": PACKAGES}, indent=2))
        return 0
    if args.command == "list":
        for item in PACKAGES:
            print(f"{item['name']}\t{source_root(item)}")
        return 0
    try:
        item = package(args.package)
        if args.command == "check":
            check_source(item)
            print(f"{item['name']} source inventory checked")
            return 0
        identity = stage(item, args.destination.resolve(), args.commit or source_commit())
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"CSE package operation failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(identity, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
