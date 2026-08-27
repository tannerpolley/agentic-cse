#!/usr/bin/env python3
"""Verify the installed personal CSE plugin against this source revision."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ID = "cse@personal"
REQUIRED_PATHS = (
    ".codex-plugin/plugin.json",
    "hooks/hooks.json",
    "scripts/change_accounting.py",
    "scripts/check-installed.py",
    "scripts/check_prose.py",
    "scripts/cooling_fit_benchmark.py",
    "scripts/cse-review-stop.py",
    "scripts/delete_disposable_repo.py",
    "scripts/setup_scientific_project.py",
    "evaluation/cooling-fit/benchmark.json",
    "assets/project/AGENTS.md",
    "assets/project/README.md",
    "assets/project/CONTEXT.md",
    "assets/project/formulation.tex",
    "assets/project/methods.tex",
    "assets/project/evidence.tex",
    "assets/project/adr/README.md",
    "assets/project/adr/templates/computational-architecture.md",
    "assets/project/adr/templates/evidence-admission.md",
    "assets/project/adr/templates/numerical-method.md",
    "assets/project/adr/templates/reproducibility-tooling.md",
    "assets/project/adr/templates/scientific-formulation.md",
    "assets/project/writing/STYLE.md",
    "assets/project/writing/RULES.md",
)


def fail(message: str) -> int:
    print(f"CSE installed check failed: {message}", file=sys.stderr)
    return 1


def main() -> int:
    source_manifest = json.loads((ROOT / ".codex-plugin/plugin.json").read_text())
    expected_version = source_manifest["version"]
    expected_deploy = Path(
        os.environ.get("CSE_DEPLOY_ROOT", Path.home() / ".codex/plugins/cse")
    ).resolve()

    try:
        result = subprocess.run(
            ["codex", "plugin", "list", "--json"],
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return fail(f"cannot run 'codex plugin list --json' ({exc})")
    if result.returncode != 0:
        return fail(result.stderr.strip() or "plugin listing failed")

    try:
        installed = json.loads(result.stdout)["installed"]
        record = next(item for item in installed if item.get("pluginId") == PLUGIN_ID)
    except (json.JSONDecodeError, KeyError, StopIteration, TypeError):
        return fail(f"{PLUGIN_ID} is not installed")
    if record.get("installed") is not True:
        return fail(f"{PLUGIN_ID} is not installed")
    if record.get("enabled") is not True:
        return fail(f"{PLUGIN_ID} is disabled")
    if record.get("version") != expected_version:
        return fail(
            f"{PLUGIN_ID} version is {record.get('version')!r}; expected {expected_version!r}"
        )

    source_path = record.get("source", {}).get("path")
    if not isinstance(source_path, str) or Path(source_path).resolve() != expected_deploy:
        return fail(f"{PLUGIN_ID} source is {source_path!r}; expected {str(expected_deploy)!r}")
    if not expected_deploy.is_dir():
        return fail(f"deployed source is unavailable at {expected_deploy}")

    try:
        deployed_manifest = json.loads(
            (expected_deploy / ".codex-plugin/plugin.json").read_text()
        )
    except (OSError, json.JSONDecodeError) as exc:
        return fail(f"deployed manifest is invalid ({exc})")
    if deployed_manifest.get("version") != expected_version:
        return fail("deployed manifest version does not match the source manifest")

    required = list(REQUIRED_PATHS)
    required.extend(
        str(path.relative_to(ROOT))
        for path in sorted((ROOT / "skills").glob("*/SKILL.md"))
    )
    missing = [path for path in required if not (expected_deploy / path).is_file()]
    if missing:
        return fail("deployed source is missing: " + ", ".join(missing))

    print(f"CSE installed check passed: {PLUGIN_ID} {expected_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
