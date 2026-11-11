#!/usr/bin/env python3
"""Report local CSE tool readiness without installing tools or using paid APIs."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[2]


def doctor_status(executable: str | None) -> tuple[dict | None, str]:
    if executable is None:
        return None, "cse-zotero is not on PATH"
    try:
        result = subprocess.run(
            [executable, "doctor", "--json"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"cse-zotero doctor failed: {exc}"
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        detail = result.stderr.strip() or "doctor did not return JSON"
        return None, f"cse-zotero doctor failed: {detail}"
    if not isinstance(payload, dict) or not isinstance(payload.get("readiness"), dict):
        return None, "cse-zotero doctor returned no readiness report"
    return payload, ""


def readiness_line(readiness: dict | None, key: str) -> str:
    entry = readiness.get(key) if readiness else None
    if not isinstance(entry, dict):
        return "not reported"
    return "ready" if entry.get("ready") is True else "not ready"


def tier_state(values: list[bool]) -> str:
    if all(values):
        return "ready"
    return "partial" if any(values) else "unavailable"


def latex_check() -> str:
    checker = PLUGIN_ROOT / "scripts/visualize/check-latex-toolchain.sh"
    try:
        result = subprocess.run(
            ["bash", str(checker)], capture_output=True, text=True, timeout=30, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"check could not run ({exc})"
    if result.returncode == 0:
        return "ready (CSE TinyTeX toolchain)"
    first_line = next((line.strip() for line in result.stderr.splitlines() if line.strip()), "check failed")
    return first_line.removeprefix("CSE LaTeX toolchain check failed: ")


def report() -> str:
    git = shutil.which("git")
    python_ready = sys.version_info >= (3, 11)
    python_version = ".".join(map(str, sys.version_info[:3]))
    core_ready = git is not None and python_ready

    quarto = shutil.which("quarto")
    lualatex = shutil.which("lualatex")
    latexmk = shutil.which("latexmk")
    snakemake = shutil.which("snakemake")
    zotero, doctor_error = doctor_status(shutil.which("cse-zotero"))
    readiness = zotero.get("readiness") if zotero else None
    zotero_identified = bool(zotero and zotero.get("identity", {}).get("package", {}).get("name") == "cse-zotero")
    zotero_ready = bool(
        zotero_identified
        and any(readiness_line(readiness, key) == "ready"
                for key in ("zotero_local_api", "retained_corpus", "data"))
    )
    mathpix_entry = readiness.get("mathpix", {}) if isinstance(readiness, dict) else {}
    mathpix_ready = bool(zotero_identified and isinstance(mathpix_entry, dict) and mathpix_entry.get("ready") is True)
    latex_status = latex_check()
    documents_state = tier_state([quarto is not None, lualatex is not None and latexmk is not None
                                 and latex_status.startswith("ready "), snakemake is not None])
    sources_state = tier_state([zotero_ready, mathpix_ready])

    lines = [
        "CSE readiness (read-only)",
        f"Core — {'ready' if core_ready else 'incomplete'}",
        f"  Git: {'present' if git else 'missing'}",
        f"  Python: {python_version} ({'supported' if python_ready else 'Python 3.11 or newer required'})",
        "  Skills: cse:setup, cse:design, cse:build, cse:analyze, cse:summarize, cse:review",
        "  Numerical runs also need the repository's selected solver and dependencies.",
        f"Documents — {documents_state}",
        f"  Quarto: {'present' if quarto else 'missing'}; used by cse:quarto and manuscript rendering",
        f"  LuaLaTeX: {'present' if lualatex else 'missing'}",
        f"  latexmk: {'present' if latexmk else 'missing'}",
        f"  LaTeX toolchain check: {latex_status}",
        f"  Snakemake: {'present' if snakemake else 'missing'}; used by optional Snakemake workflows in cse:setup and cse:analyze",
        "  LaTeX document skills: cse:latex, cse:beamer, cse:tikz",
        f"Sources — {sources_state}",
    ]
    if zotero is None:
        lines.append(f"  Zotero companion: unavailable ({doctor_error})")
        lines.append("  Source skills: cse:research, cse:zotero, cse:data")
        lines.append("  Mathpix: not checked; cse:zotero")
    else:
        if not zotero_identified:
            lines.append("  Zotero companion: doctor response did not identify cse-zotero")
        else:
            lines.append("  Zotero companion: installed; read-only doctor completed")
        for key, label in (("zotero_local_api", "Zotero local API"), ("retained_corpus", "Retained corpus"), ("data", "Retained data")):
            lines.append(f"  {label}: {readiness_line(readiness, key)}")
        lines.append("  Source skills: cse:research, cse:zotero, cse:data")
        if isinstance(mathpix_entry, dict) and mathpix_entry.get("ready") is True:
            mathpix_state = "ready (local mpx command and recorded consent)"
        elif isinstance(mathpix_entry, dict) and isinstance(mathpix_entry.get("reason"), str):
            mathpix_state = f"not ready ({mathpix_entry['reason']})"
        else:
            mathpix_state = "not reported"
        lines.append(f"  Mathpix: {mathpix_state}; used by cse:zotero (no conversion is run by this check)")
    return "\n".join(lines)


if __name__ == "__main__":
    print(report())
