#!/usr/bin/env python3
"""Verify that Codex has cse@cse installed from this repository's marketplace."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from package_inventory import ROOT, package, runtime_payload, source_root


def main() -> int:
    codex = os.environ.get("CSE_CODEX_BIN", "codex")
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
    except (OSError, RuntimeError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"CSE installed check failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"pluginId": "cse@cse", "marketplaceRoot": str(ROOT), "cache": str(cache),
                      "activeTaskLoadedState": "unverified"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
