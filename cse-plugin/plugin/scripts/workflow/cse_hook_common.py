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
                raise ValueError(f"mapped glossary is missing: {link}")
            if path not in paths:
                paths.append(path)
    return paths


def glossary_entries(text: str, locator: str) -> list[dict]:
    """Read Matt's Language entries and CSE's source and optional path scope."""
    entries = []
    current = None
    language = False
    for number, line in enumerate(text.splitlines(), 1):
        if re.match(r"^#{1,2} ", line):
            language = line.strip() == "## Language"
            current = None
        elif re.match(r"^#{3,6} ", line):
            current = None
        elif language and (match := re.match(r"^\*\*(.+?)\*\*:\s*(.*)$", line)):
            current = {"term": match[1], "meaning": match[2], "avoid": [],
                       "source": "sourceless", "scope": ["*"], "locator": f"{locator}:{number}"}
            entries.append(current)
        elif current is not None:
            if line.startswith("_Avoid_:"):
                current["avoid"] = [term.strip() for term in line.split(":", 1)[1].split(",") if term.strip()]
            elif line.startswith("Source:"):
                current["source"] = line.split(":", 1)[1].strip() or "sourceless"
            elif line.startswith("Scope:"):
                current["scope"] = [scope.strip().strip("`") for scope in line.split(":", 1)[1].split(";") if scope.strip()]
            elif line.strip():
                current["meaning"] = (current["meaning"] + " " + line.strip()).strip()
    return entries


def has_source(entry: dict) -> bool:
    source = entry["source"].casefold()
    return bool(entry["meaning"] and source and not source.startswith("sourceless")
                and source not in {"none", "unknown", "-", "n/a"} and set(source) - {"-", ":"})


def read_glossaries(root: Path) -> list[dict]:
    return [entry for path in glossary_paths(root)
            for entry in glossary_entries(path.read_text(encoding="utf-8"), str(path))]
