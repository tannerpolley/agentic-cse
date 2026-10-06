"""Shared CSE hook project discovery."""

from pathlib import Path
import re
from typing import TypedDict


CONTEXT = Path("docs/scientific/CONTEXT.md")
ROLE_VALUES = {"analysis", "tool"}
ROLE_DECLARATION = re.compile(r"(?im)^[ \t]*repository[ \t]+role[ \t]*:[ \t]*([^\r\n]*?)[ \t]*$")
LEGACY_DECLARATION = re.compile(r"(?im)^[ \t]*default[ \t]+deliverable[ \t]*:[ \t]*([^\r\n]*?)[ \t]*$")
DECLARATION_LINE = re.compile(
    r"(?im)^[ \t]*(?:repository[ \t]+role|default[ \t]+deliverable)"
    r"[ \t]*:[ \t]*[^\r\n]*(?:\r?\n|$)"
)


class RoleState(TypedDict):
    role: str | None
    roles: list[str]
    legacy: list[str]


def role_state(text: str) -> RoleState:
    roles = [match.group(1) for match in ROLE_DECLARATION.finditer(text)]
    legacy = [match.group(1) for match in LEGACY_DECLARATION.finditer(text)]
    role = roles[0] if len(roles) == 1 and roles[0] in ROLE_VALUES and not legacy else None
    return {"role": role, "roles": roles, "legacy": legacy}


def repository_role(context: Path) -> str | None:
    """Return the sole confirmed repository role, or None if unresolved."""
    return role_state(context.read_text(encoding="utf-8"))["role"]


def nearest_context(start: Path, boundary: Path) -> Path | None:
    """Return the nearest CSE context at or above start, stopping at boundary."""
    start = start.resolve()
    boundary = boundary.resolve()
    try:
        start.relative_to(boundary)
    except ValueError:
        return None
    for directory in (start, *start.parents):
        candidate = directory / CONTEXT
        if candidate.is_file():
            return candidate
        if directory == boundary:
            break
    return None


AGENT_ROLE_DECLARATION = re.compile(r"(?im)^[ \t]*agent[ \t]+role[ \t]*:[ \t]*([^\r\n]*?)[ \t]*$")
HEADING = re.compile(r"(?m)^#{1,6}[ \t]")


class AgentRoleState(TypedDict):
    role: str | None
    roles: list[str]
    responsibilities: str


def agent_role_state(text: str) -> AgentRoleState:
    """Return the sole declared agent role and the paragraph(s) that follow it."""
    matches = list(AGENT_ROLE_DECLARATION.finditer(text))
    roles = [match.group(1) for match in matches if match.group(1)]
    role = roles[0] if len(roles) == 1 and len(matches) == 1 else None
    responsibilities = ""
    if role:
        rest = text[matches[0].end():]
        heading = HEADING.search(rest)
        responsibilities = (rest[:heading.start()] if heading else rest).strip()
    return {"role": role, "roles": roles, "responsibilities": responsibilities}


def agent_role(context: Path) -> str | None:
    """Return the sole confirmed agent role, or None if unresolved."""
    return agent_role_state(context.read_text(encoding="utf-8"))["role"]


def glossary_paths(root: Path) -> list[Path]:
    """Read the root vocabulary and every local glossary linked by its map."""
    root = root.resolve()
    paths = [root / "GLOSSARY.md"] if (root / "GLOSSARY.md").is_file() else []
    mapping = root / "GLOSSARY-MAP.md"
    if mapping.is_file():
        for link in re.findall(r"\[[^\]]+\]\(([^)]+)\)", mapping.read_text(encoding="utf-8")):
            path = root / link
            if path.name != "GLOSSARY.md":
                continue
            if not path.resolve().is_relative_to(root):
                raise ValueError(f"glossary path escapes the repository: {link}")
            if not path.is_file():
                continue  # Matt creates each vocabulary file lazily.
            if path not in paths:
                paths.append(path)
    return paths


def split_scope(value: str, default: str = "*") -> list[str]:
    return [part.strip().strip("`") for part in value.split(";") if part.strip()] or [default]


def split_table_row(line: str) -> list[str]:
    text = line.strip()
    text = text[1:] if text.startswith("|") else text
    text = text[:-1] if text.endswith("|") and not text.endswith(r"\|") else text
    return [cell.strip().replace(r"\|", "|") for cell in re.split(r"(?<!\\)\|", text)]


def markdown_tables(text: str) -> list[dict]:
    """Keep original row text and positions so migration removes only selected rows."""
    lines = text.splitlines(keepends=True)
    tables = []
    section = ""
    heading = None
    fence = None
    index = 0
    while index < len(lines) - 1:
        marker = re.match(r"^\s*(`{3,}|~{3,})", lines[index])
        if marker:
            fence = None if fence == marker[1][0] else (fence or marker[1][0])
        if marker or fence:
            index += 1
            continue
        if match := re.match(r"^## ([^\n]+)", lines[index]):
            section, heading = match[1].strip(), index
        elif lines[index].startswith("# "):
            section, heading = "", None
        if (lines[index].lstrip().startswith("|") and lines[index + 1].lstrip().startswith("|")
                and all(re.fullmatch(r":?-+:?", cell) for cell in split_table_row(lines[index + 1]))):
            table = {"section": section, "heading": heading, "start": index,
                     "headers": split_table_row(lines[index]), "raw_header": "".join(lines[index:index + 2]), "rows": []}
            index += 2
            while index < len(lines) and lines[index].lstrip().startswith("|"):
                table["rows"].append({"index": index, "text": lines[index], "cells": split_table_row(lines[index])})
                index += 1
            tables.append(table)
        else:
            index += 1
    return tables


def glossary_entries(text: str, locator: str, default_scope: str = "*") -> list[dict]:
    """Read Language entries with zero-based, end-exclusive line spans."""
    lines = text.splitlines()
    entries = []
    current = None
    language = False
    for number, line in enumerate(lines, 1):
        heading = re.match(r"^#{1,6} ", line)
        match = re.match(r"^\*\*(.+?)\*\*:\s*(.*)$", line) if language else None
        if current is not None and (heading or match):
            current["span"][1] = number - 1
        if heading:
            if len(heading[0].strip()) <= 2:
                language = line.strip() == "## Language"
            current = None
        elif match:
            current = {"term": match[1], "meaning": match[2], "avoid": [], "span": [number - 1, len(lines)],
                       "source": "sourceless", "scope": [default_scope], "locator": f"{locator}:{number}"}
            entries.append(current)
        elif current is not None:
            if line.startswith("_Avoid_:"):
                current["avoid"].extend(term.strip() for term in line.split(":", 1)[1].split(",") if term.strip())
            elif line.startswith("Source:"):
                current["source"] = line.split(":", 1)[1].strip() or "sourceless"
            elif line.startswith("Scope:"):
                current["scope"] = split_scope(line.split(":", 1)[1], default_scope)
            elif line.strip():
                current["meaning"] = (current["meaning"] + " " + line.strip()).strip()
    return entries


def has_source(entry: dict) -> bool:
    source = entry["source"].casefold()
    return bool(entry["meaning"] and source and not source.startswith("sourceless")
                and source not in {"none", "unknown", "-", "n/a"} and set(source) - {"-", ":"})


def read_glossaries(root: Path) -> list[dict]:
    root = root.resolve()
    entries = []
    for path in glossary_paths(root):
        default_scope = "*" if path.parent == root else f"{path.parent.relative_to(root).as_posix()}/*"
        entries.extend(glossary_entries(path.read_text(encoding="utf-8"), str(path), default_scope))
    return entries
