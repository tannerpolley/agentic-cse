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
