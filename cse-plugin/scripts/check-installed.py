#!/usr/bin/env python3
"""Verify selected CSE marketplace installations against the committed payload."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from package_inventory import (
    LEGACY_NAME,
    PACKAGES,
    deploy_root,
    package,
    source_commit,
    verify,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--packages", default="cse")
    parser.add_argument("--deployed-only", action="store_true")
    parser.add_argument("--home", type=Path, default=Path.home())
    args = parser.parse_args()
    try:
        selected = list(PACKAGES) if args.all else [package(name) for name in args.packages.split(",")]
    except ValueError as exc:
        parser.error(str(exc))
    selected_names = {item["name"] for item in selected}
    if len(selected_names) != len(selected):
        parser.error("duplicate selected package")
    companions = selected_names - {"cse"}
    if companions and "cse" not in selected_names:
        parser.error(f"{', '.join(sorted(companions))} requires the core cse plugin")
    home = args.home.resolve()
    try:
        commit = source_commit()
        listed = [] if args.deployed_only else json.loads(subprocess.run(["codex", "plugin", "list", "--json"], text=True, capture_output=True, check=True).stdout).get("installed", [])
        family = [
            entry for entry in listed
            if str(entry.get("pluginId", "")).split("@", 1)[0] in {item["name"] for item in PACKAGES}
        ]
        unexpected = [
            str(entry.get("pluginId", "")) for entry in listed
            if (name := str(entry.get("pluginId", "")).split("@", 1)[0])
            and (name.startswith("cse-") or name == LEGACY_NAME)
            and name not in {item["name"] for item in PACKAGES}
        ]
        if unexpected:
            raise RuntimeError(f"unexpected CSE-family packages: {', '.join(unexpected)}")
        if not args.deployed_only:
            expected_ids = {f"{name}@personal" for name in selected_names}
            actual_ids = [str(entry.get("pluginId", "")) for entry in family]
            if {plugin_id.split("@", 1)[0] for plugin_id in actual_ids} != selected_names or any(
                plugin_id not in expected_ids for plugin_id in actual_ids
            ):
                raise RuntimeError("installed CSE-family packages do not match the selected configuration")
        verified = []
        for item in selected:
            root = deploy_root(item, home)
            if not args.deployed_only:
                matches = [entry for entry in family if entry.get("pluginId") == f"{item['name']}@personal"]
                if len(matches) != 1:
                    raise RuntimeError(f"{item['name']} is missing or duplicated in Codex plugin list")
                entry = matches[0]
                if not entry.get("installed") or not entry.get("enabled"):
                    raise RuntimeError(f"{item['name']} is not enabled")
                source = (entry.get("source") or {}).get("path")
                if not isinstance(source, str) or Path(source).resolve() != root:
                    raise RuntimeError(f"{item['name']} has an unexpected deployment root")
            verified.append(verify(item, root, commit, home))
    except (OSError, RuntimeError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"CSE installed check failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"verified": verified}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
