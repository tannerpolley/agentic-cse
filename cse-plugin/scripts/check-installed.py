#!/usr/bin/env python3
"""Verify that Codex and Claude Code have cse@cse installed from this repository's marketplace.

With --refresh-claude, first refresh each Claude Code copy from this checkout.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from package_inventory import ROOT, package, runtime_payload, source_root


def claude_config_dirs() -> list[Path]:
    """Claude Code config homes in use; CSE_CLAUDE_CONFIG_DIRS (os.pathsep-separated) overrides."""
    value = os.environ.get("CSE_CLAUDE_CONFIG_DIRS")
    homes = value.split(os.pathsep) if value else [Path.home() / ".claude", Path.home() / ".t3/provider-homes/claude"]
    seen, result = set(), []
    for home in map(Path, homes):
        # Homes that share one plugins directory hold one copy.
        if home.is_dir() and (home / "plugins").resolve() not in seen:
            seen.add((home / "plugins").resolve())
            result.append(home)
    return result


def claude_copies(claude: str, refresh: bool) -> list[dict]:
    def run(home: Path, *args: str, cwd: Path = ROOT) -> str:
        return subprocess.run([claude, "plugin", *args], cwd=cwd, env=os.environ | {"CLAUDE_CONFIG_DIR": str(home)},
                              text=True, capture_output=True, check=True).stdout

    source = runtime_payload(source_root(package("cse")))
    report = []
    for home in claude_config_dirs():
        marketplaces = [item for item in json.loads(run(home, "marketplace", "list", "--json")) if item.get("name") == "cse"]
        if not marketplaces:
            report.append({"configDir": str(home), "state": "cse marketplace not registered; skipped"})
            continue
        root = Path(marketplaces[0].get("path") or marketplaces[0].get("installLocation") or "").resolve()
        if root != ROOT:
            raise RuntimeError(f"Claude marketplace 'cse' in {home} is rooted at {root}, not {ROOT}")
        if refresh:
            run(home, "marketplace", "update", "cse")
        for entry in [item for item in json.loads(run(home, "list", "--json")) if item.get("id") == "cse@cse"]:
            project = Path(entry.get("projectPath") or ROOT)
            if not project.is_dir():
                report.append({"configDir": str(home), "scope": entry.get("scope"), "state": f"project {project} missing; skipped"})
                continue
            if refresh:
                run(home, "update", "cse@cse", "--scope", entry["scope"], "--json", cwd=project)
            installed = runtime_payload(Path(entry["installPath"]))
            # Claude Code leaves this marker in a cache it refreshes in place; it is not plugin content.
            installed.pop(".orphaned_at", None)
            if installed != source:
                raise RuntimeError(f"Claude copy {entry['installPath']} ({home}, {entry['scope']}) differs from the source payload")
            report.append({"configDir": str(home), "scope": entry["scope"], "installPath": entry["installPath"], "matchesSource": True})
    return report


def main() -> int:
    refresh = sys.argv[1:] == ["--refresh-claude"]
    if sys.argv[1:] and not refresh:
        print("Usage: check-installed.py [--refresh-claude]", file=sys.stderr)
        return 2
    codex = os.environ.get("CSE_CODEX_BIN", "codex")
    claude = os.environ.get("CSE_CLAUDE_BIN", "claude")
    cache = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "plugins/cache/cse/cse/local"
    try:
        listed = json.loads(subprocess.run(
            [codex, "plugin", "list", "--json"], text=True, capture_output=True, check=True,
        ).stdout).get("installed", [])
        ids = [str(entry.get("pluginId", "")) for entry in listed]
        cse_ids = [plugin_id for plugin_id in ids if plugin_id.split("@", 1)[0] == "cse"]
        if cse_ids != ["cse@cse"]:
            raise RuntimeError(f"expected only cse@cse installed, found {cse_ids or 'none'}")
        entry = listed[ids.index("cse@cse")]
        if not entry.get("installed") or not entry.get("enabled"):
            raise RuntimeError("cse@cse is not installed and enabled")
        marketplace = (entry.get("marketplaceSource") or {}).get("source")
        if not marketplace or Path(marketplace).resolve() != ROOT:
            raise RuntimeError(f"cse@cse comes from {marketplace}, not {ROOT}")
        if runtime_payload(cache) != runtime_payload(source_root(package("cse"))):
            raise RuntimeError(f"{cache} differs from the source payload; run `codex plugin add cse@cse`")
        claude_report = (claude_copies(claude, refresh) if shutil.which(claude)
                         else "Claude Code CLI absent; Claude copy not checked")
    except (OSError, RuntimeError, KeyError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        detail = f"{exc}: {exc.stderr.strip()}" if isinstance(exc, subprocess.CalledProcessError) and exc.stderr else exc
        print(f"CSE installed check failed: {detail}", file=sys.stderr)
        return 1
    print(json.dumps({"pluginId": "cse@cse", "marketplaceRoot": str(ROOT), "cache": str(cache),
                      "claude": claude_report, "activeTaskLoadedState": "unverified"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
