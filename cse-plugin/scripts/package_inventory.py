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
import tempfile


ROOT = Path(__file__).resolve().parents[1]
PACKAGES = (
    {
        "name": "cse",
        "root": ".",
        "skills": (
            "audit", "workflow", "setup", "research", "diagnose", "design", "build",
            "analyze", "summarize", "review", "write",
        ),
        "include": (
            ".codex-plugin", ".claude-plugin", "AGENTS.md", "BANNED.md", "CHANGELOG.md", "LICENSE", "README.md",
            "assets", "references", "skills", "scripts/change_accounting.py",
            "scripts/check_prose.py", "scripts/cse-test-gate.py", "scripts/cse_hook_common.py",
            "scripts/install_cse_hooks.py",
            "scripts/setup_scientific_project.py",
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
        "skills": ("plot", "tikz", "pgfplots", "latex", "quarto", "beamer"),
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


def check_source(item: dict) -> None:
    root = source_root(item)
    manifest = json.loads((root / ".codex-plugin/plugin.json").read_text())
    if manifest.get("name") != item["name"] or not manifest.get("description"):
        raise RuntimeError(f"{item['name']} requires its package name and description")
    if "version" in manifest:
        raise RuntimeError("CSE packages use source commits, not release numbers")
    for relative in item["include"]:
        if not (root / relative).exists():
            raise RuntimeError(f"{item['name']} payload is missing: {relative}")
    if sorted(path.name for path in (root / "skills").iterdir() if path.is_dir()) != sorted(item["skills"]):
        raise RuntimeError(f"{item['name']} skills disagree with the package inventory")


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
            shutil.copytree(origin, target)
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
        "deploymentRoot": str(deploy_root(item, home)),
        "runtimeTreeSha256": runtime_tree_hash(destination),
        "payloadSkills": list(item["skills"]),
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
        "sourceCommit": commit,
        "deploymentRoot": str(deploy_root(item, home)),
        "runtimeTreeSha256": runtime_tree_hash(root),
        "payloadSkills": list(item["skills"]),
    }
    if manifest.get("name") != expected["pluginId"]:
        raise RuntimeError(f"{item['name']} manifest disagrees with its inventory")
    problems = []
    if identity.get("runtimeTreeSha256") != expected["runtimeTreeSha256"]:
        problems.append("payload altered: on-disk hash differs from the recorded installed hash")
    if identity.get("sourceCommit") != commit:
        problems.append(f"source revision differs: deployed {identity.get('sourceCommit')}, requested {commit}; an older revision is not evidence of breakage")
    fields = sorted(key for key in set(identity) | set(expected)
                    if key not in {"sourceCommit", "runtimeTreeSha256"}
                    and identity.get(key) != expected.get(key))
    if fields:
        problems.append(f"identity format or metadata differs: {', '.join(fields)}; regenerate through an explicitly authorized source sync, not by editing installed.json")
    if problems:
        raise RuntimeError(f"{item['name']}: " + "; ".join(problems))
    with tempfile.TemporaryDirectory() as directory:
        staged = Path(directory) / item["name"]
        stage(item, staged, commit, home)
        if runtime_payload(root) != runtime_payload(staged):
            raise RuntimeError(f"{item['name']} runtime payload does not match the committed source")
    skills = sorted(path.name for path in (root / "skills").iterdir() if path.is_dir())
    if skills != sorted(item["skills"]):
        raise RuntimeError(f"{item['name']} runtime skills are {skills}; expected {sorted(item['skills'])}")
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
    stage_parser.add_argument("--home", type=Path)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("package")
    verify_parser.add_argument("root", type=Path)
    verify_parser.add_argument("--commit")
    verify_parser.add_argument("--home", type=Path)
    args = parser.parse_args()
    if args.command == "inventory":
        print(json.dumps({"packages": PACKAGES}, indent=2))
        return 0
    if args.command == "list":
        for item in PACKAGES:
            print(f"{item['name']}\t{source_root(item)}\t{deploy_root(item)}")
        return 0
    try:
        item = package(args.package)
        if args.command == "check":
            check_source(item)
            print(f"{item['name']} source inventory checked")
            return 0
        if args.command == "stage":
            identity = stage(item, args.destination.resolve(), args.commit or source_commit(), args.home)
        else:
            identity = verify(item, args.root.resolve(), args.commit or source_commit(), args.home)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"CSE package operation failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(identity, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
