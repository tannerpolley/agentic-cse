#!/usr/bin/env python3
"""Verify selected CSE marketplace installations against the committed payload."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from package_inventory import COMPATIBILITY, PACKAGES, deploy_root, package, verify


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--deployed-only", action="store_true")
    parser.add_argument("--home", type=Path, default=Path.home())
    args = parser.parse_args()
    selected = list(PACKAGES) if args.all else [package("cse")]
    home = args.home.resolve()
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
        listed = [] if args.deployed_only else json.loads(subprocess.run(["codex", "plugin", "list", "--json"], text=True, capture_output=True, check=True).stdout).get("installed", [])
        verified = []
        for item in selected:
            root = deploy_root(item, home)
            if not args.deployed_only:
                matches = [entry for entry in listed if entry.get("pluginId") == f"{item['name']}@personal"]
                if len(matches) != 1:
                    raise RuntimeError(f"{item['name']} is missing or duplicated in Codex plugin list")
                entry = matches[0]
                if not entry.get("installed") or not entry.get("enabled"):
                    raise RuntimeError(f"{item['name']} is not enabled")
                if str(entry.get("version")) != COMPATIBILITY[item["name"]]:
                    raise RuntimeError(f"{item['name']} version does not match {COMPATIBILITY[item['name']]}")
                source = (entry.get("source") or {}).get("path")
                if source and Path(source).resolve() != root:
                    raise RuntimeError(f"{item['name']} has an unexpected deployment root")
            verified.append(verify(item, root, commit, home))
    except (OSError, RuntimeError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"CSE installed check failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"verified": verified}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
