#!/usr/bin/env python3
"""Count CSE skill use per harness from T3 Code transcripts (read-only).

Claude Code records an explicit event for each skill use: a ``Skill`` tool call
(model-invoked) or a ``/cse:<skill>`` slash command (user-invoked). Codex has no
skill event; a skill is used by reading its ``SKILL.md``, so a Codex use is a
shell read (cat/sed/head/nl/awk/less) naming one CSE ``skills/<name>/SKILL.md``.
Bulk listings (wildcards, ls/find/wc/rg) are not uses.

Sessions count when their working directory is under ``--root`` (default: the
Engineering workspace). Run under ``nice``; files are streamed line by line.

    nice -n 19 python3 scripts/measure_skill_use.py [--since 2026-09-24] [--json]
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re

HOME = Path.home()
CLAUDE = HOME / ".t3/provider-homes/claude/projects"
CODEX = HOME / ".t3/provider-homes/codex/sessions"
SKILL_PATH = re.compile(r"(?:plugins/cache/cse/cse/[^/\s'\"]+|cse-plugin/plugin)/skills/([a-z]+)/SKILL\.md")
READ_VERB = re.compile(r"(?:^|[\s;&|(])(?:cat|sed|head|nl|awk|less|bat|tail)\s")
LISTING = re.compile(r"\*|(?:^|[\s;&|(])(?:ls|find|wc|rg|grep|fd|du)\s")
SLASH = re.compile(r"<command-name>/cse:([a-z]+)</command-name>")


def empty() -> dict:
    return {"sessions": 0, "using": 0, "uses": 0, "user_uses": 0, "errors": 0, "skills": Counter()}


def claude_file(path: Path, root: str, since: str) -> tuple[bool, int, int, int, Counter] | None:
    cwd = stamp = None
    uses = user_uses = errors = 0
    skills: Counter = Counter()
    pending: set[str] = set()
    with path.open(errors="replace") as handle:
        for line in handle:
            if cwd is None and '"cwd"' in line:
                cwd = (re.search(r'"cwd":"([^"]*)"', line) or [None, None])[1]
                stamp = (re.search(r'"timestamp":"([^"]*)"', line) or [None, ""])[1]
            if "Skill" not in line and "/cse:" not in line and "tool_use_id" not in line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            content = (record.get("message") or {}).get("content")
            if isinstance(content, str):
                for name in SLASH.findall(content):
                    user_uses += 1
                    skills[name] += 1
                continue
            for block in content or []:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use" and block.get("name") == "Skill":
                    name = str((block.get("input") or {}).get("skill", ""))
                    if name.startswith("cse:"):
                        uses += 1
                        skills[name[4:]] += 1
                        pending.add(block.get("id", ""))
                elif block.get("type") == "tool_result" and block.get("tool_use_id") in pending and block.get("is_error"):
                    errors += 1
                elif block.get("type") == "text":
                    for name in SLASH.findall(block.get("text", "")):
                        user_uses += 1
                        skills[name] += 1
    if not cwd or not cwd.startswith(root) or (stamp or "") < since:
        return None
    return bool(uses or user_uses), uses, user_uses, errors, skills


def codex_file(path: Path, root: str, since: str) -> tuple[str, bool, int, Counter] | None:
    with path.open(errors="replace") as handle:
        meta = json.loads(handle.readline()).get("payload", {})
        if not str(meta.get("cwd", "")).startswith(root) or str(meta.get("timestamp", "")) < since:
            return None
        kind = "subagent" if isinstance(meta.get("source"), dict) and "subagent" in meta["source"] else "parent"
        uses = 0
        skills: Counter = Counter()
        for line in handle:
            if "SKILL.md" not in line or '"call' not in line and "tool_call" not in line:
                continue
            payload = json.loads(line).get("payload", {})
            if payload.get("type") not in {"function_call", "custom_tool_call"}:
                continue
            command = str(payload.get("input") or payload.get("arguments") or "")
            if LISTING.search(command) or not READ_VERB.search(command):
                continue
            for name in set(SKILL_PATH.findall(command)):
                uses += 1
                skills[name] += 1
    return kind, bool(uses), uses, skills


def measure(root: str, since: str) -> dict:
    totals = {f"{h}/{k}": empty() for h in ("claude", "codex") for k in ("parent", "subagent")}
    for path in CLAUDE.glob("*/*.jsonl"):
        add(totals["claude/parent"], claude_file(path, root, since))
    for path in CLAUDE.glob("*/*/subagents/*.jsonl"):
        add(totals["claude/subagent"], claude_file(path, root, since))
    for path in CODEX.rglob("*.jsonl"):
        found = codex_file(path, root, since)
        if found:
            kind, using, uses, skills = found
            add(totals[f"codex/{kind}"], (using, uses, 0, 0, skills))
    return totals


def add(total: dict, found) -> None:
    if not found:
        return
    using, uses, user_uses, errors, skills = found
    total["sessions"] += 1
    total["using"] += using
    total["uses"] += uses
    total["user_uses"] += user_uses
    total["errors"] += errors
    total["skills"].update(skills)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=str(HOME / "Workspaces/Engineering"))
    parser.add_argument("--since", default="", help="ISO date; sessions starting earlier are skipped")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    totals = measure(args.root, args.since)
    if args.json:
        print(json.dumps({k: {**v, "skills": dict(v["skills"])} for k, v in totals.items()}, indent=1))
        return 0
    for name, t in totals.items():
        share = t["using"] / t["sessions"] if t["sessions"] else 0
        print(f"{name:16} sessions {t['sessions']:4}  using CSE {t['using']:4} ({share:5.1%})  "
              f"model uses {t['uses']:4}  user uses {t['user_uses']:3}  errors {t['errors']}")
        print(f"{'':16} skills: {', '.join(f'{k} {v}' for k, v in t['skills'].most_common())}")
    parity = [totals[f"{h}/parent"] for h in ("claude", "codex")]
    rates = [t["using"] / t["sessions"] if t["sessions"] else 0 for t in parity]
    print(f"parent-session CSE rate: claude {rates[0]:.1%} vs codex {rates[1]:.1%} -> "
          f"{'claude at or above codex' if rates[0] >= rates[1] else 'claude below codex'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
