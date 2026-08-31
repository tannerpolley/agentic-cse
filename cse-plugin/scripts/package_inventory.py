#!/usr/bin/env python3
"""Canonical CSE package inventory, staging, and runtime identity helpers."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
COMPATIBILITY = {"cse": "2.0.0", "cse-sources": "1.0.0", "cse-visualize": "1.0.0"}
PACKAGES = (
    {
        "name": "cse",
        "root": ".",
        "skills": ("setup", "research", "diagnose", "design", "build", "analyze", "review", "summarize", "write"),
        "include": (
            ".codex-plugin", "AGENTS.md", "BANNED.md", "CHANGELOG.md", "LICENSE", "README.md",
            "assets", "hooks", "references", "skills", "scripts/change_accounting.py",
            "scripts/check_prose.py", "scripts/cse-review-stop.py", "scripts/setup_scientific_project.py",
        ),
    },
    {
        "name": "cse-sources",
        "root": "extensions/cse-sources",
        "skills": ("zotero", "mathpix", "data", "digitize"),
        "include": (".codex-plugin", "README.md", "references", "scripts", "skills"),
    },
    {
        "name": "cse-visualize",
        "root": "extensions/cse-visualize",
        "skills": ("plot", "tikz", "pgfplots", "latex", "quarto", "revealjs", "beamer"),
        "include": (".codex-plugin", "README.md", "assets", "references", "scripts", "skills"),
    },
)
LEGACY_NAME = "scientific-codex"
IDENTITY_PATH = Path(".codex-plugin/installed.json")


def package(name: str) -> dict:
    try:
        return next(item for item in PACKAGES if item["name"] == name)
    except StopIteration as exc:
        raise ValueError(f"unknown CSE package: {name}") from exc


def source_root(item: dict) -> Path:
    return (ROOT / item["root"]).resolve()


def deploy_root(item: dict, home: Path | None = None) -> Path:
    return ((home or Path.home()) / ".codex" / "plugins" / item["name"]).resolve()


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
        if relative == IDENTITY_PATH or "__pycache__" in relative.parts or path.suffix == ".pyc":
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


def stage(item: dict, destination: Path, commit: str, home: Path | None = None) -> dict:
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
            shutil.copytree(origin, target)
        else:
            shutil.copy2(origin, target)
    manifest = json.loads((destination / ".codex-plugin/plugin.json").read_text())
    if manifest.get("name") != item["name"] or manifest.get("version") != COMPATIBILITY[item["name"]]:
        raise RuntimeError(f"{item['name']} manifest disagrees with the package inventory")
    skills = sorted(path.name for path in (destination / "skills").iterdir() if path.is_dir())
    if skills != sorted(item["skills"]):
        raise RuntimeError(f"{item['name']} staged skills are {skills}; expected {sorted(item['skills'])}")
    identity = {
        "pluginId": item["name"],
        "version": manifest["version"],
        "sourceCommit": commit,
        "deploymentRoot": str(deploy_root(item, home)),
        "runtimeTreeSha256": runtime_tree_hash(destination),
        "payloadSkills": list(item["skills"]),
        "compatibility": COMPATIBILITY,
    }
    identity_path = destination / IDENTITY_PATH
    identity_path.write_text(json.dumps(identity, indent=2, sort_keys=True) + "\n")
    return identity


def checkpoint(name: str) -> None:
    if os.environ.get("CSE_FAIL_AT") == name:
        raise RuntimeError(f"injected failure at {name}")


def verify(item: dict, root: Path, commit: str, home: Path | None = None) -> dict:
    manifest_path = root / ".codex-plugin/plugin.json"
    identity_path = root / IDENTITY_PATH
    if not manifest_path.is_file() or not identity_path.is_file():
        raise RuntimeError(f"{item['name']} is missing its manifest or installed identity")
    manifest = json.loads(manifest_path.read_text())
    identity = json.loads(identity_path.read_text())
    expected = {
        "pluginId": item["name"],
        "version": COMPATIBILITY[item["name"]],
        "sourceCommit": commit,
        "deploymentRoot": str(deploy_root(item, home)),
        "runtimeTreeSha256": runtime_tree_hash(root),
        "payloadSkills": list(item["skills"]),
        "compatibility": COMPATIBILITY,
    }
    if manifest.get("name") != expected["pluginId"] or manifest.get("version") != expected["version"]:
        raise RuntimeError(f"{item['name']} manifest disagrees with its inventory")
    if identity != expected:
        raise RuntimeError(f"{item['name']} installed identity is stale, altered, or incompatible")
    skills = sorted(path.name for path in (root / "skills").iterdir() if path.is_dir())
    if skills != sorted(item["skills"]):
        raise RuntimeError(f"{item['name']} runtime skills are {skills}; expected {sorted(item['skills'])}")
    return identity


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("inventory")
    subparsers.add_parser("list")
    stage_parser = subparsers.add_parser("stage")
    stage_parser.add_argument("package")
    stage_parser.add_argument("destination", type=Path)
    stage_parser.add_argument("--commit")
    stage_parser.add_argument("--home", type=Path)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("package")
    verify_parser.add_argument("root", type=Path)
    verify_parser.add_argument("--commit")
    verify_parser.add_argument("--home", type=Path)
    args = parser.parse_args()
    if args.command == "inventory":
        print(json.dumps({"compatibility": COMPATIBILITY, "packages": PACKAGES}, indent=2))
        return 0
    if args.command == "list":
        for item in PACKAGES:
            print(f"{item['name']}\t{source_root(item)}\t{deploy_root(item)}")
        return 0
    try:
        item = package(args.package)
        if args.command == "stage":
            identity = stage(item, args.destination.resolve(), args.commit or source_commit(), args.home)
        else:
            identity = verify(item, args.root.resolve(), args.commit or source_commit(), args.home)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"CSE package staging failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(identity, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
