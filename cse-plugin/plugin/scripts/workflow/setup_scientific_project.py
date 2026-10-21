#!/usr/bin/env python3
"""Prepare or reconcile the root scientific-records layout."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Iterable

try:
    from .cse_hook_common import (
        AGENT_ROLE_DECLARATION, DECLARATION_LINE, HEADING, ROLE_VALUES,
        agent_role_state, glossary_entries, glossary_paths, has_source, read_glossaries,
        markdown_tables, repository_role, role_state, split_scope,
    )
except ImportError:
    from cse_hook_common import (
        AGENT_ROLE_DECLARATION, DECLARATION_LINE, HEADING, ROLE_VALUES,
        agent_role_state, glossary_entries, glossary_paths, has_source, read_glossaries,
        markdown_tables, repository_role, role_state, split_scope,
    )


ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "assets" / "workflow" / "project"
PROTOCOL_TEMPLATE = ROOT / "assets" / "workflow" / "protocol.md"
SKILL_ROUTING = ROOT / "assets" / "workflow" / "skill-routing.txt"
BLOCK_BEGIN = "<!-- CSE:BEGIN PROTOCOL -->"
BLOCK_END = "<!-- CSE:END PROTOCOL -->"
AGENT_ROLE_SECTION = re.compile(r"(?ms)^## Agent role[ \t]*\n.*?(?=^#{1,2}[ \t]|\Z)")
SOURCE_DATA_ADOPTION_SECTION = re.compile(r"(?ms)^## Source/data adoption[ \t]*\n.*?(?=^#{1,2}[ \t]|\Z)")
SOURCE_DATA_ADOPTION_DECLARATION = re.compile(r"(?mi)^source/data adoption:[ \t]*(none|zotero|project-data)[ \t]*$")
SOURCE_DATA_ADOPTION_VALUES = ("none", "zotero", "project-data")
SOURCE_DATA_ADOPTION_POINTER = "Use the source/data adoption recorded in `docs/scientific/CONTEXT.md`."
MANDATORY = ("README.md", "CONTEXT.md")
OPTIONAL = {
    "formulation": "formulation.md",
    "methods": "methods.md",
    "evidence": "evidence.md",
    "decisions": "decisions/README.md",
    "writing": "writing/STYLE.md",
    "writing-rules": "writing/RULES.md",
}
SKIP_PARTS = {".git", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
UNSOURCED_TERMS = ("certificate", "fingerprint", "admission", "typed failure", "claim boundary")
CALLER_SUFFIXES = {".md", ".qmd", ".tex", ".rst", ".yaml", ".yml", ".json", ".py", ".sh", ".cmake", ".cpp", ".h", ".hpp", ".js", ".toml"}
DOCUMENT_CLASS_RE = re.compile(rb"(?m)^[ \t]*\\documentclass\b")
# Exact unpopulated templates removed in #54; a modified template is a record.
LEGACY_TEMPLATE_BLOBS = {
    "7f473a595e439c0c8b232e0f02567c31162ab2db",
    "4f87c022fba114d0e5eda92e46077d573dbcad89",
    "478ff1b2d7cce85c314fe6e5cc3d6ea5a7a83090",
    "b9286a4093b3fd85bb45798a3c242423938ce86f",
}


def obsolete_template(path: Path) -> bool:
    if not {"docs", "scientific", "adr", "templates"} <= set(path.parts):
        return False
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest() in LEGACY_TEMPLATE_BLOBS


class SetupError(RuntimeError):
    pass


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
        capture_output=True, check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def relative(path: Path, repo: Path) -> str:
    return path.relative_to(repo).as_posix()


def readable_file(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        with path.open("rb") as stream:
            stream.read(1)
    except OSError:
        return False
    return True


def skip(path: Path, repo: Path) -> bool:
    return bool(set(path.relative_to(repo).parts) & SKIP_PARTS)


def repository_files(repo: Path) -> Iterable[Path]:
    listed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=repo, capture_output=True, check=False,
    )
    if listed.returncode == 0:
        for item in listed.stdout.split(b"\0"):
            if item:
                path = repo / item.decode(errors="surrogateescape")
                if path.is_file() and not skip(path, repo):
                    yield path
        return
    for directory, names, filenames in os.walk(repo):
        names[:] = [name for name in names if name not in SKIP_PARTS]
        for name in filenames:
            path = Path(directory) / name
            if not skip(path, repo):
                yield path


def install_file(source: Path, target: Path, *, preserve_existing: bool = False) -> None:
    if target.exists():
        if preserve_existing and target.is_file():
            return
        if not target.is_file() or target.read_bytes() != source.read_bytes():
            raise SetupError(f"refusing to overwrite unrecognized file: {target}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def canonical_pointer() -> str:
    return next(
        paragraph
        for paragraph in (ASSETS / "AGENTS.md").read_text(encoding="utf-8").split("\n\n")
        if "MUST use the installed CSE skills" in paragraph
    )


def replaceable_pointer(paragraph: str) -> bool:
    folded = " ".join(paragraph.split()).casefold()
    return re.fullmatch(
        r"use (?:the installed )?cse(?: skills?)? and read "
        r"docs/scientific/(?:readme|context)\.md(?: before [^.]+)?\.",
        folded,
    ) is not None


def validate_source_data_adoption(value: str) -> None:
    if value not in SOURCE_DATA_ADOPTION_VALUES:
        choices = ", ".join(SOURCE_DATA_ADOPTION_VALUES)
        raise SetupError(f"source/data adoption must be one of: {choices}")


def stored_source_data_adoption(text: str) -> str | None:
    matches = list(SOURCE_DATA_ADOPTION_DECLARATION.finditer(text))
    choices = {match.group(1).casefold() for match in matches}
    if len(matches) > 1 or len(choices) > 1:
        raise SetupError("docs/scientific/CONTEXT.md must declare one source/data adoption choice")
    return next(iter(choices), None)


def set_source_data_adoption(text: str, value: str) -> str:
    validate_source_data_adoption(value)
    text = SOURCE_DATA_ADOPTION_SECTION.sub("", text)
    text = SOURCE_DATA_ADOPTION_DECLARATION.sub("", text).strip()
    section = f"## Source/data adoption\n\nsource/data adoption: {value}\n"
    heading = re.search(r"(?m)^## Claim boundaries[ \t]*$", text)
    if heading:
        return text[:heading.start()].rstrip() + f"\n\n{section}\n" + text[heading.start():].lstrip()
    return text.rstrip() + f"\n\n{section}"


def render_protocol(repository_role_value: str, agent_role_value: str, responsibilities: str = "",
                    source_data_adoption: str | None = None) -> str:
    if source_data_adoption is not None:
        validate_source_data_adoption(source_data_adoption)
    text = PROTOCOL_TEMPLATE.read_text(encoding="utf-8").strip()
    text = text.replace("{agent_role}", agent_role_value).replace("{repository_role}", repository_role_value)
    routes = [line.strip() for line in SKILL_ROUTING.read_text(encoding="utf-8").splitlines() if line.strip()]
    text = text.replace("{skill_routing}", "\n".join(f"- {line}" for line in routes))
    text = text.replace("{responsibilities}", responsibilities.strip()) if responsibilities.strip() else text.replace("{responsibilities}\n\n", "")
    pointer = SOURCE_DATA_ADOPTION_POINTER if source_data_adoption not in {None, "none"} else ""
    text = text.replace("{source_data_adoption}", pointer) if pointer else text.replace("\n{source_data_adoption}\n", "")
    return f"{BLOCK_BEGIN}\n{text}\n{BLOCK_END}"


def role_first(block: str) -> bool:
    lines = [line.strip() for line in block.splitlines()[1:-1] if line.strip()]
    return len(lines) >= 2 and lines[0].startswith("## ") and lines[1].startswith("**Agent role:**")


def managed_block(text: str) -> tuple[str | None, str]:
    """Return (existing block or None, status) where status is missing|present|malformed."""
    begins = [m.start() for m in re.finditer(re.escape(BLOCK_BEGIN), text)]
    ends = [m.end() for m in re.finditer(re.escape(BLOCK_END), text)]
    if not begins and not ends:
        return None, "missing"
    if len(begins) != 1 or len(ends) != 1 or ends[0] < begins[0]:
        return None, "malformed"
    return text[begins[0]:ends[0]], "present"


def malformed_markers(agents: Path) -> bool:
    return agents.is_file() and managed_block(agents.read_text(encoding="utf-8"))[1] == "malformed"


def insert_block(before: str, block: str) -> str:
    """Insert the managed block after the title, removing the legacy CSE pointer paragraph."""
    paragraphs = [p for p in before.rstrip().split("\n\n") if p.strip()] if before.strip() else []
    pointer = canonical_pointer().strip()
    paragraphs = [p for p in paragraphs if not (replaceable_pointer(p) or p.strip() == pointer)]
    if paragraphs and re.match(r"#[ \t]", paragraphs[0]) and "\n" not in paragraphs[0].strip():
        paragraphs.insert(1, block)
    else:
        paragraphs.insert(0, block)
    return "\n\n".join(paragraphs) + "\n"


def routing_report(repo: Path, role: str | None = None, agent_role_value: str | None = None,
                   responsibilities: str | None = None,
                   source_data_adoption: str | None = None) -> dict:
    repo = repo.resolve()
    agents = repo / "AGENTS.md"
    if agents.exists() and not agents.is_file():
        raise SetupError(f"root guidance is not a file: {agents}")
    before = agents.read_text(encoding="utf-8") if agents.is_file() else ""
    context = repo / "docs/scientific/CONTEXT.md"
    context_text = context.read_text(encoding="utf-8", errors="replace") if context.is_file() else ""
    declared = agent_role_state(context_text)
    role = role or role_state(context_text)["role"]
    agent_role_value = agent_role_value or declared["role"]
    responsibilities = declared["responsibilities"] if responsibilities is None else responsibilities
    requested_adoption = source_data_adoption
    persisted_adoption = stored_source_data_adoption(context_text)
    source_data_adoption = persisted_adoption if source_data_adoption is None else source_data_adoption
    existing, status = managed_block(before)
    missing = []
    if role is None:
        missing.append("repository role (confirm --role or `repository role:` in docs/scientific/CONTEXT.md)")
    if agent_role_value is None:
        missing.append("agent role (supply --agent-role or `agent role:` in docs/scientific/CONTEXT.md)")
    if len(declared["roles"]) > 1:
        missing.append("one agent role (docs/scientific/CONTEXT.md declares several)")
    rendered_adoption = requested_adoption
    if rendered_adoption is None and existing is not None:
        rendered_adoption = "zotero" if SOURCE_DATA_ADOPTION_POINTER in existing.splitlines() else None
    rendered = (render_protocol(role, agent_role_value, responsibilities, rendered_adoption)
                if role and agent_role_value else None)
    action = "none"
    after = before
    if status == "malformed":
        missing.append("one managed CSE Protocol block (duplicate or unmatched markers need manual reconciliation)")
        action = "manual"
    elif rendered is None:
        if status == "missing":
            missing.append("managed CSE Protocol block")
    elif status == "missing":
        action = "create" if not before else "insert"
        after = insert_block(before or (ASSETS / "AGENTS.md").read_text(encoding="utf-8"), rendered)
    elif existing != rendered:
        action = "regenerate"
        after = before.replace(existing, rendered)
    if status == "present" and not role_first(existing):
        missing.append("agent role as the first instruction of the managed block")
    block_state = status if status != "present" else ("current" if existing == rendered else "stale")
    targets = {
        f"docs/scientific/{name}": readable_file(repo / "docs/scientific" / name)
        for name in MANDATORY
    }
    return {
        "satisfied": not missing and action == "none",
        "missing": missing,
        "action": action,
        "block": block_state,
        "repository_role": role,
        "agent_role": agent_role_value,
        "source_data_adoption": source_data_adoption,
        "targets": targets,
        "proposed": after,
        "diff": "".join(difflib.unified_diff(
            before.splitlines(keepends=True), after.splitlines(keepends=True),
            fromfile="AGENTS.md", tofile="AGENTS.md",
        )),
    }


def ensure_manifest_writable(path: Path) -> None:
    if path.exists():
        if not path.is_file() or not os.access(path, os.W_OK):
            raise SetupError(f"manifest destination is not writable: {path}")
        return
    ancestor = path.parent
    while not ancestor.exists():
        ancestor = ancestor.parent
    if not ancestor.is_dir() or not os.access(ancestor, os.W_OK):
        raise SetupError(f"manifest parent is not writable: {ancestor}")


def ensure_installable(source: Path, target: Path, *, preserve_existing: bool = False) -> None:
    if not target.exists() or preserve_existing and target.is_file():
        return
    if not target.is_file() or target.read_bytes() != source.read_bytes():
        raise SetupError(f"refusing to overwrite unrecognized file: {target}")


def tracked(paths: Iterable[Path], repo: Path) -> list[dict[str, str]]:
    return [
        {"path": relative(path, repo), "sha256": digest(path)}
        for path in sorted(paths)
    ]


GLOSSARY_LINK = "Project vocabulary: [GLOSSARY.md](../../GLOSSARY.md)."


def render_entry(entry: dict) -> str:
    text = f"**{entry['term']}**:\n{entry['meaning']}\n"
    if entry["avoid"]:
        text += f"_Avoid_: {', '.join(dict.fromkeys(entry['avoid']))}\n"
    text += f"Source: {entry['source']}\n"
    if entry["scope"] != ["*"]:
        text += "Scope: " + "; ".join(f"`{scope}`" for scope in entry["scope"]) + "\n"
    return text


def insert_section(text: str, title: str, content: str) -> str:
    if not content:
        return text
    heading = re.search(rf"(?m)^## {re.escape(title)}[ \t]*(?:\n|\Z)", text)
    if heading is None:
        text += f"\n## {title}\n"
        position = len(text)
    else:
        following = re.search(r"(?m)^#{1,2} ", text[heading.end():])
        position = heading.end() + following.start() if following else len(text)
    return text[:position] + ("\n" if text[:position].endswith("\n") else "\n\n") + content + "\n" + text[position:]


def extend_avoids(text: str, updates: dict[str, list[str]]) -> str:
    lines = text.splitlines(keepends=True)
    for entry in reversed(glossary_entries(text, "glossary")):
        start, end = entry["span"]
        additions = [term for term in updates.get(entry["term"].casefold(), [])
                     if term.casefold() not in {old.casefold() for old in entry["avoid"]}]
        extra = f"_Avoid_: {', '.join(dict.fromkeys(additions))}\n" if additions else ""
        if extra:
            position = end
            while position > start and not lines[position - 1].strip():
                position -= 1
            if position and not lines[position - 1].endswith("\n"):
                extra = "\n" + extra
            lines.insert(position, extra)
    return "".join(lines)


def migrate_glossary(repo: Path, contexts: list[Path]) -> dict:
    root_glossary = repo / "GLOSSARY.md"
    before = root_glossary.read_text(encoding="utf-8") if root_glossary.is_file() else ""
    entries = read_glossaries(repo)
    known = {entry["term"].casefold(): entry for entry in entries}
    texts = {path: path.read_text(encoding="utf-8") for path in contexts}
    additions = {}
    updates = {}
    removed = {path: set() for path in contexts}
    kept = []
    prose = []

    def keep(path: Path, row: dict, reason: str) -> None:
        kept.append({"path": relative(path, repo), "line": row["index"] + 1,
                     "row": row["text"].strip(), "reason": reason})

    tables = {path: markdown_tables(text) for path, text in texts.items()}
    avoids = []
    for path, records in tables.items():
        for table in records:
            headers = [name.casefold() for name in table["headers"]]
            required = {"term", "meaning"} if table["section"] == "Glossary" else {"avoid", "prefer", "meaning"}
            optional = {"source", "scope"} if table["section"] == "Glossary" else {"scope", "exceptions", "evidence"}
            table["exact"] = required <= set(headers) <= required | optional
            for row in table["rows"]:
                if table["section"] not in {"Glossary", "Avoid"}:
                    keep(path, row, "not a Glossary or Avoid table")
                    continue
                if len(row["cells"]) != len(headers) or len(set(headers)) != len(headers):
                    keep(path, row, "row does not match its table headings")
                    continue
                fields = dict(zip(headers, row["cells"]))
                if table["section"] == "Avoid":
                    if not all(fields.get(name) for name in required):
                        keep(path, row, "avoid rule is missing required columns")
                    else:
                        avoids.append((path, table, row, fields))
                    continue
                if not table["exact"]:
                    keep(path, row, "glossary columns cannot map exactly: " + ", ".join(table["headers"]))
                    continue
                term = fields["term"].strip("`")
                if not term or not fields["meaning"]:
                    keep(path, row, "term or definition is empty")
                    continue
                if fields["meaning"].startswith(METADATA_LABELS):
                    keep(path, row, "definition starts with a glossary metadata label")
                    continue
                entry = {"term": term, "meaning": fields["meaning"], "source": fields.get("source") or "sourceless",
                         "scope": split_scope(fields.get("scope", "")), "avoid": []}
                key = term.casefold()
                previous = known.get(key)
                if previous and any(previous[field] != entry[field] for field in ("meaning", "source", "scope")):
                    keep(path, row, "existing term has a different definition, source, or scope")
                    continue
                if not previous:
                    additions[key] = entry
                    known[key] = entry
                removed[path].add(row["index"])

    for path, table, row, fields in avoids:
        entry = known.get(fields["prefer"].strip("`").casefold())
        evidence = fields.get("evidence", "")
        reason = ""
        if not entry:
            reason = "preferred term is not in the glossary"
        elif fields.get("exceptions") or split_scope(fields.get("scope", "")) != entry["scope"]:
            reason = "rule has its own scope or exceptions"
        elif (not table["exact"] or fields["meaning"] != entry["meaning"] or evidence not in {"", "sourceless", entry["source"]}
              or "," in fields["avoid"]):
            reason = "rule has information a synonym line cannot hold"
        if reason:
            prose.append({"path": relative(path, repo), "row": row["text"].strip(), "reason": reason,
                          "table": table, "raw": row["text"]})
        else:
            key = entry["term"].casefold()
            if key in additions:
                additions[key]["avoid"].append(fields["avoid"].strip("`"))
            else:
                owner = Path(entry["locator"].rsplit(":", 1)[0])
                updates.setdefault(owner, {}).setdefault(key, []).append(fields["avoid"].strip("`"))
        removed[path].add(row["index"])

    for path, records in tables.items():
        lines = texts[path].splitlines(keepends=True)
        for table in records:
            if (table["section"] in {"Glossary", "Avoid"}
                    and (table["section"] == "Avoid" or table["exact"])
                    and all(row["index"] in removed[path] for row in table["rows"])):
                removed[path].update((table["start"], table["start"] + 1))
        migrated_headings = {table["heading"] for table in records
                             if table["section"] in {"Glossary", "Avoid"}
                             and any(row["index"] in removed[path] for row in table["rows"])}
        for index in migrated_headings:
            end = next((i for i in range(index + 1, len(lines)) if lines[i].startswith(("# ", "## "))), len(lines))
            if not any(lines[i].strip() and i not in removed[path] for i in range(index + 1, end)):
                removed[path].add(index)
        texts[path] = "".join(line for index, line in enumerate(lines) if index not in removed[path])
    updates = {relative(path, repo): extend_avoids(path.read_text(encoding="utf-8"), rules)
               for path, rules in updates.items()}
    after = updates.get("GLOSSARY.md", before)
    if additions:
        after = insert_section(after or "# Project vocabulary\n", "Language",
                               "\n".join(render_entry(entry) for entry in additions.values()))
    if after != before:
        updates["GLOSSARY.md"] = after
    return {"updates": updates, "text": after, "entries": [entry for entry in entries if not entry["locator"].startswith(f"{root_glossary}:")]
            + glossary_entries(after, str(root_glossary)), "contexts": texts, "kept": kept, "prose": prose}


def markdown_record(text: str) -> str:
    text = re.sub(r"^\\documentclass\{[^}]+\}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\\usepackage(?:\[[^]]*\])?\{[^}]+\}\s*", "", text, flags=re.MULTILINE)
    text = text.replace("\\begin{document}", "").replace("\\end{document}", "")
    text = re.sub(r"^\\section\{([^}]+)\}", r"# \1", text, flags=re.MULTILINE)
    return text.strip() + "\n"


def validate_role(role: str) -> None:
    if role not in ROLE_VALUES:
        raise SetupError("repository role must be analysis or tool")


def proposed_role(text: str) -> str | None:
    state = role_state(text)
    if state["role"] in ROLE_VALUES:
        return state["role"]
    legacy = state["legacy"]
    if not state["roles"] and len(legacy) == 1:
        return {"result": "analysis", "capability": "tool"}.get(legacy[0])
    return None


def canonical_context(text: str, role: str, agent_role_value: str | None = None,
                      responsibilities: str | None = None,
                      source_data_adoption: str | None = None) -> str:
    validate_role(role)
    if source_data_adoption is not None:
        if source_data_adoption != stored_source_data_adoption(text):
            text = set_source_data_adoption(text, source_data_adoption)
    text = DECLARATION_LINE.sub("", text).strip()
    if agent_role_value:
        declared = agent_role_state(text)
        body = responsibilities if responsibilities is not None else declared["responsibilities"]
        section = f"## Agent role\n\nagent role: {agent_role_value.strip()}\n" + (f"\n{body.strip()}\n" if body.strip() else "")
        if AGENT_ROLE_SECTION.search(text):
            text = AGENT_ROLE_SECTION.sub(lambda _: section + "\n", text, count=1).strip()
        else:
            text = AGENT_ROLE_DECLARATION.sub("", text)
            heading = HEADING.search(text, re.match(r"#[ \t][^\n]*\n?", text).end() if re.match(r"#[ \t]", text) else 0)
            text = (text[:heading.start()].rstrip() + "\n\n" + section + "\n" + text[heading.start():]) if heading else text.rstrip() + "\n\n" + section
    heading = re.search(r"(?m)^#[^#\n].*$", text)
    if heading:
        rest = text[heading.end():].lstrip("\n")
        text = text[:heading.end()] + f"\n\nrepository role: {role}\n\n{rest}"
    else:
        text = f"repository role: {role}\n\n{text}" if text else f"repository role: {role}"
    return text.strip() + "\n"


def latex_document_roots(repo: Path, files: Iterable[Path]) -> tuple[Path, ...]:
    scientific = repo / "docs/scientific"
    candidates = set()
    for path in files:
        if path.suffix.lower() != ".tex" or path.is_symlink() or not path.is_relative_to(scientific):
            continue
        suffix = path.relative_to(scientific)
        if len(suffix.parts) < 2 or suffix.parts[0] in {"latex", "adr"}:
            continue
        if path.name.casefold() == "main.tex" or DOCUMENT_CLASS_RE.search(path.read_bytes()):
            candidates.add(path.parent)
    roots = []
    for candidate in sorted(candidates, key=lambda path: (len(path.parts), str(path))):
        if not any(candidate.is_relative_to(root) for root in roots):
            roots.append(candidate)
    return tuple(roots)


def record_target(path: Path, repo: Path, document_roots: tuple[Path, ...] = ()) -> Path | None:
    rel = path.relative_to(repo)
    parts = rel.parts
    if parts in (("docs", "scientific", "README.md"), ("docs", "scientific", "CONTEXT.md")):
        return None
    if parts[-1] in {"CONTEXT.md", "CONTEXT-MAP.md", "GLOSSARY.md", "GLOSSARY-MAP.md"}:
        return None
    if any(path.is_relative_to(root) for root in document_roots):
        return repo / "docs/scientific/latex" / path.relative_to(repo / "docs/scientific")
    if "docs" in parts and "scientific" in parts:
        index = max(i for i, part in enumerate(parts) if part == "scientific")
        suffix = parts[index + 1:]
        if suffix[:1] == ("adr",):
            if suffix[-1] == "README.md":
                return repo / "docs/scientific/decisions/README.md"
            if "templates" in suffix and obsolete_template(path):
                return None
            return repo / "docs/scientific/decisions" / Path(*suffix[1:])
        if suffix and suffix[0] == "latex":
            return repo / "docs/scientific/latex" / Path(*suffix[1:])
        if len(suffix) == 1 and suffix[0] in {"formulation.tex", "methods.tex", "evidence.tex"}:
            return repo / "docs/scientific" / Path(suffix[0]).with_suffix(".md")
        if suffix and suffix[-1].endswith(".tex"):
            return repo / "docs/scientific/latex" / Path(*suffix)
        return repo / "docs/scientific" / Path(*suffix)
    if len(parts) >= 2 and parts[:2] == ("docs", "latex"):
        return repo / "docs/scientific/latex" / Path(*parts[2:])
    return None


METADATA_LABELS = ("Source:", "Scope:", "_Avoid_:")


def matt_format(text: str) -> bool:
    """Matt Pocock's domain glossary: a `## Language` section, even before its first term.

    Fenced examples are ignored, so a scientific context that shows the format is not Matt's.
    """
    text = re.sub(r"^```.*?^```[^\n]*$", "", text, flags=re.MULTILINE | re.DOTALL)
    return bool(re.search(r"^## Language\s*$", text, re.MULTILINE)) or bool(glossary_entries(text, ""))


def plan_reconciliation(repo: Path, role: str | None = None,
                        source_data_adoption: str | None = None) -> dict:
    repo = repo.resolve()
    if not repo.is_dir():
        raise SetupError(f"repository does not exist: {repo}")
    if role is not None:
        validate_role(role)
    if source_data_adoption is not None:
        validate_source_data_adoption(source_data_adoption)
    files = list(repository_files(repo))
    target = repo / "docs/scientific/CONTEXT.md"
    matt_upgrades = {relative(path, repo): relative(path.with_name(path.name.replace("CONTEXT", "GLOSSARY")), repo)
                     for path in files if path.name == "CONTEXT-MAP.md" or
                     (path.name == "CONTEXT.md" and path != target and matt_format(path.read_text(encoding="utf-8")))}
    contexts = sorted(path for path in files if path.name == "CONTEXT.md" and relative(path, repo) not in matt_upgrades)
    document_roots = latex_document_roots(repo, files)
    all_context_text = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in contexts)
    selected_role = role or proposed_role(all_context_text)
    persisted_adoption = stored_source_data_adoption(all_context_text)
    searchable = all_context_text + "\n" + "\n".join(
        relative(path, repo) for path in files
        if "docs" in path.relative_to(repo).parts
    )
    # The canonical scientific record wins when old tables repeat a term.
    ordered_contexts = sorted(contexts, key=lambda path: (path != target, str(path)))
    migration = migrate_glossary(repo, ordered_contexts)
    merged_glossary, entries = migration["text"], migration["entries"]
    kept_paths = {item["path"] for item in migration["kept"]}
    folded_search = searchable.casefold()
    sourced = {entry["term"].casefold() for entry in entries if has_source(entry)}
    terms = list(dict.fromkeys(
        [entry["term"] for entry in entries if not has_source(entry)]
        + [term for term in UNSOURCED_TERMS if term not in sourced and (
            all(word in folded_search for word in term.split())
            or term == "claim boundary" and "claim boundar" in folded_search
        )]
    ))
    merged = (migration["contexts"][target] if target.is_file()
              else (ASSETS / "CONTEXT.md").read_text(encoding="utf-8"))
    if not target.is_file() and agent_role_state(all_context_text)["role"]:
        merged = AGENT_ROLE_SECTION.sub("", merged)
    if GLOSSARY_LINK not in merged:
        heading = re.search(r"(?m)^## ", merged)
        position = heading.start() if heading else len(merged)
        merged = merged[:position].rstrip() + "\n\n" + GLOSSARY_LINK + "\n\n" + merged[position:]
    retained = []
    for path in contexts:
        if path == target or relative(path, repo) in kept_paths:
            continue
        content = DECLARATION_LINE.sub("", migration["contexts"][path]).strip()
        record = f"### `{relative(path, repo)}`\n\n{content}"
        if content and record not in merged:
            retained.append(record)
    if retained:
        merged += "\n## Retained source records\n\n" + "\n\n".join(retained) + "\n"
    prose_tables = {}
    for item in migration["prose"]:
        header = item["table"]["raw_header"]
        prose_tables[header] = prose_tables.get(header, "") + item["raw"].rstrip("\n") + "\n"
    merged = insert_section(merged, "Prose avoid rules", "\n".join(header + rows for header, rows in prose_tables.items()))
    if source_data_adoption is not None and source_data_adoption != persisted_adoption:
        merged = set_source_data_adoption(merged, source_data_adoption)
    elif persisted_adoption is not None and stored_source_data_adoption(merged) != persisted_adoption:
        merged = set_source_data_adoption(merged, persisted_adoption)
    merged = (canonical_context(merged, selected_role) if selected_role else
              DECLARATION_LINE.sub("", merged).strip() + "\n")
    moves = []
    merges = []
    deletes = []
    links = {}
    reserved = {relative(path, repo) for path in files}
    for path in files:
        destination = record_target(path, repo, document_roots)
        if destination is None:
            continue
        old = relative(path, repo)
        new = relative(destination, repo)
        if old == new:
            continue
        entry = {"source": old, "target": new}
        if path.suffix == ".tex" and destination.suffix == ".md":
            entry["conversion"] = "Markdown record"
        if new in reserved:
            merges.append(entry)
        else:
            moves.append(entry)
            reserved.add(new)
        links[old] = new
    for path in contexts:
        source = relative(path, repo)
        if path == target or source in kept_paths:
            continue
        merges.append({"source": source, "target": "docs/scientific/CONTEXT.md", "reason": "migrate vocabulary; retain scientific records"})
        links[source] = "docs/scientific/CONTEXT.md"
    for path in files:
        if path.name not in {"GLOSSARY.md", "GLOSSARY-MAP.md"} and relative(path, repo) not in matt_upgrades and obsolete_template(path):
            deletes.append({"path": relative(path, repo), "reason": "obsolete unpopulated decision template"})
    if not target.exists():
        moves.append({"source": "(new)", "target": "docs/scientific/CONTEXT.md", "reason": "mandatory record"})
    readme = repo / "docs/scientific/README.md"
    if not readme.exists() and "docs/scientific/README.md" not in reserved:
        moves.append({"source": "(asset)", "target": "docs/scientific/README.md", "reason": "mandatory record"})
    updates = []
    for path in files:
        if path == target or relative(path, repo) in matt_upgrades or path.name in {"GLOSSARY.md", "GLOSSARY-MAP.md"} or path.suffix.lower() not in CALLER_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        replacements = [(old, new) for old, new in links.items() if old in text]
        if replacements:
            updates.append({"path": relative(path, repo), "replacements": replacements})
    glossary = repo / "GLOSSARY.md"
    glossary_before = glossary.read_text(encoding="utf-8") if glossary.is_file() else ""
    glossary_update = merged_glossary != glossary_before
    affected = {"AGENTS.md", "docs/scientific/CONTEXT.md", "GLOSSARY.md", "GLOSSARY-MAP.md"}
    affected.update(relative(path, repo) for path in [*glossary_paths(repo), *contexts])
    for item in moves + merges:
        affected.add(item["target"])
        if not item["source"].startswith("("):
            affected.add(item["source"])
    affected.update(item["path"] for item in deletes + updates)
    return {
        "schema_version": 1,
        "repository": str(repo),
        "repository_role": selected_role,
        "agent_role": agent_role_state(all_context_text)["role"],
        "source_data_adoption": source_data_adoption or persisted_adoption,
        "role_state": role_state(all_context_text),
        "contexts": [relative(path, repo) for path in contexts],
        "sourceless_terms": terms,
        "glossaries": [relative(path, repo) for path in glossary_paths(repo)],
        "glossary_update": glossary_update,
        "merged_glossary": merged_glossary,
        "kept_rows": migration["kept"],
        "prose_rows": migration["prose"],
        "retained_context_updates": {relative(path, repo): migration["contexts"][path]
                                     for path in contexts if relative(path, repo) in kept_paths and path != target},
        "matt_upgrades": matt_upgrades,
        "glossary_updates": migration["updates"],
        "moves": moves,
        "merges": merges,
        "deletes": deletes,
        "updates": updates,
        "merged_context": merged,
        "source_hashes": {name: digest(repo / name) if (repo / name).is_file() else None
                          for name in sorted(affected)},
    }


def plan_text(plan: dict) -> str:
    role = plan.get("repository_role") or "unresolved"
    lines = [f"Reconciliation preview: {plan['repository']}", "", f"Repository role: {role}",
             f"Agent role: {plan.get('agent_role') or 'missing'}"]
    if plan.get("source_data_adoption") is not None:
        lines.append(f"Source/data adoption: {plan['source_data_adoption']}")
    legacy = plan.get("role_state", {}).get("legacy", [])
    roles = plan.get("role_state", {}).get("roles", [])
    if roles or legacy:
        lines.append("Role declarations: " + ", ".join([*roles, *[f"default deliverable: {value}" for value in legacy]]))
    if len(legacy) == 1 and legacy[0] in {"result", "capability"}:
        lines.append(f"Legacy role proposal: {legacy[0]} → {'analysis' if legacy[0] == 'result' else 'tool'}")
    if plan["glossaries"]:
        lines += ["", "Glossary files read:", *[f"- `{path}`" for path in plan["glossaries"]]]
    if plan["glossary_update"]:
        lines += ["", "Vocabulary migration into root `GLOSSARY.md`: preserve definitions and sources; add missing terms and exact synonyms.",
                  "", plan["merged_glossary"]]
    for old, new in plan["matt_upgrades"].items():
        lines += ["", f"Matt Pocock's skills 1.3 read `{Path(new).name}`; run `git mv {old} {new}`.",
                  "CSE leaves this Matt-owned file untouched."]
    for name, text in plan["glossary_updates"].items():
        if name != "GLOSSARY.md":
            lines += ["", f"Exact synonym additions to `{name}`:", text]
    for title, key in (("Rows kept in place", "kept_rows"), ("Rows moved to Prose avoid rules", "prose_rows")):
        if plan[key]:
            lines += ["", title + ":"]
            lines += [f"- `{item['path']}`: {item['row']} — {item['reason']}" for item in plan[key]]
    if plan["sourceless_terms"]:
        lines += ["", "Sourceless glossary terms:", *[f"- {term}" for term in plan["sourceless_terms"]]]
    for title, key in (("Moves", "moves"), ("Merges", "merges"), ("Deletes", "deletes"), ("Caller and link updates", "updates")):
        lines += ["", f"{title}:"]
        items = plan[key]
        if not items:
            lines.append("- none")
        for item in items:
            if key == "updates":
                replacements = "; ".join(f"`{old}` → `{new}`" for old, new in item["replacements"])
                lines.append(f"- `{item['path']}`: {replacements}")
            elif "source" in item:
                detail = f" ({item.get('reason') or item.get('conversion')})" if item.get("reason") or item.get("conversion") else ""
                lines.append(f"- `{item['source']}` → `{item['target']}`{detail}")
            else:
                lines.append(f"- `{item['path']}` ({item['reason']})")
    lines += ["", "No files were written by this preview."]
    return "\n".join(lines) + "\n"


def git_tracked(path: Path, repo: Path) -> bool:
    result = subprocess.run(["git", "ls-files", "--error-unmatch", relative(path, repo)], cwd=repo, capture_output=True, check=False)
    return result.returncode == 0


def move_path(source: Path, target: Path, repo: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if git_tracked(source, repo):
        result = subprocess.run(["git", "mv", str(source), str(target)], cwd=repo, capture_output=True, text=True, check=False)
        if result.returncode:
            raise SetupError(result.stderr.strip() or f"git mv failed: {source}")
    else:
        shutil.move(str(source), str(target))


def remove_path(path: Path, repo: Path) -> None:
    if git_tracked(path, repo):
        result = subprocess.run(["git", "rm", "-f", "--", relative(path, repo)], cwd=repo, capture_output=True, text=True, check=False)
        if result.returncode:
            raise SetupError(result.stderr.strip() or f"git rm failed: {path}")
    elif path.is_file():
        path.unlink()


def merge_file(source: Path, target: Path, repo: Path) -> None:
    if target.exists() and source.suffix.lower() == target.suffix.lower() and digest(source) == digest(target):
        remove_path(source, repo)
        return
    source_text = source.read_text(encoding="utf-8")
    if source.suffix == ".tex" and target.suffix == ".md":
        source_text = markdown_record(source_text)
    if target.exists():
        target_text = target.read_text(encoding="utf-8")
        if source_text.strip() not in target_text:
            target.write_text(target_text.rstrip() + f"\n\n## Retained from `{relative(source, repo)}`\n\n" + source_text.strip() + "\n", encoding="utf-8")
        remove_path(source, repo)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source_text, encoding="utf-8")
        remove_path(source, repo)


def validate_reconciliation_plan(repo: Path, plan: dict) -> None:
    for name, expected in plan["source_hashes"].items():
        path = repo / name
        if not path.resolve().is_relative_to(repo) or path.is_symlink():
            raise SetupError(f"reconciliation path escapes the repository or is a symlink: {name}")
        actual = digest(path) if path.is_file() else None
        if actual != expected:
            raise SetupError(f"record changed after preview; generate a new plan: {name}")
    if (repo / "GLOSSARY.md").exists() and not (repo / "GLOSSARY.md").is_file():
        raise SetupError("glossary destination is not a file: GLOSSARY.md")
    for item in plan["moves"]:
        if item["source"].startswith("("):
            continue
        source = repo / item["source"]
        target = repo / item["target"]
        if not source.is_file():
            raise SetupError(f"planned move source is missing: {source}")
        if target.exists():
            raise SetupError(f"planned move destination is occupied: {target}")
    planned_targets = {
        item["target"]: item["source"] for item in plan["moves"]
        if not item["source"].startswith("(")
    }
    for item in plan["merges"]:
        source = repo / item["source"]
        if not source.is_file():
            raise SetupError(f"planned merge source is missing: {source}")
        target = repo / item["target"]
        if target.exists() and not target.is_file():
            raise SetupError(f"planned merge destination is not a file: {target}")
        if source.name != "CONTEXT.md":
            comparison = item["target"] if target.exists() else planned_targets.get(item["target"])
            identical = (comparison is not None and source.suffix.lower() == target.suffix.lower()
                         and plan["source_hashes"][item["source"]] == plan["source_hashes"][comparison])
            if identical:
                continue
            if source.suffix.lower() not in CALLER_SUFFIXES or target.suffix.lower() not in CALLER_SUFFIXES:
                raise SetupError(f"manual merge required for non-text records: {source} -> {target}")
            markdown_merge = target.suffix.lower() == ".md" and (
                source.suffix.lower() == ".md" or item.get("conversion") == "Markdown record"
            )
            if comparison is not None and not markdown_merge:
                raise SetupError(f"manual merge required for differing non-Markdown records: {source} -> {target}")
        source.read_text(encoding="utf-8")
        if target.exists():
            target.read_text(encoding="utf-8")
    for item in plan["deletes"]:
        path = repo / item["path"]
        if path.exists() and not path.is_file():
            raise SetupError(f"planned deletion is not a file: {path}")


def require_agent_role(context_text: str, agent_role_value: str | None) -> str:
    resolved = agent_role_value or agent_role_state(context_text)["role"]
    if not resolved:
        raise SetupError("agent role is required: supply --agent-role or record `agent role:` in docs/scientific/CONTEXT.md")
    return resolved


def apply_reconciliation(repo: Path, plan: dict, role: str, agent_role_value: str | None = None,
                         responsibilities: str | None = None,
                         source_data_adoption: str | None = None) -> dict:
    repo = repo.resolve()
    validate_role(role)
    if plan.get("repository") != str(repo):
        raise SetupError("reconciliation plan belongs to another repository")
    validate_reconciliation_plan(repo, plan)
    if malformed_markers(repo / "AGENTS.md"):
        raise SetupError("root AGENTS.md has duplicate or unmatched CSE Protocol markers; reconcile it manually first")
    agent_role_value = require_agent_role(plan["merged_context"], agent_role_value)
    target_context = repo / "docs/scientific/CONTEXT.md"
    target_context.parent.mkdir(parents=True, exist_ok=True)
    new_context = canonical_context(plan["merged_context"], role, agent_role_value, responsibilities,
                                    source_data_adoption)
    if not target_context.is_file() or target_context.read_text(encoding="utf-8") != new_context:
        target_context.write_text(new_context, encoding="utf-8")
    for item in plan["moves"]:
        if item["source"] in {"(new)", "(asset)"}:
            source = ASSETS / ("CONTEXT.md" if item["target"].endswith("CONTEXT.md") else "README.md")
            if not (repo / item["target"]).exists():
                install_file(source, repo / item["target"])
            continue
        source = repo / item["source"]
        destination = repo / item["target"]
        if not source.exists():
            continue
        if item.get("conversion"):
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(markdown_record(source.read_text(encoding="utf-8", errors="replace")), encoding="utf-8")
            remove_path(source, repo)
        else:
            move_path(source, destination, repo)
    for name, text in plan["glossary_updates"].items():
        path = repo / name
        if not path.is_file() or path.read_text(encoding="utf-8") != text:
            path.write_text(text, encoding="utf-8")
    for name, text in plan["retained_context_updates"].items():
        if (repo / name).read_text(encoding="utf-8") != text:
            (repo / name).write_text(text, encoding="utf-8")
    for item in plan["merges"]:
        source = repo / item["source"]
        if source.exists():
            if source.name == "CONTEXT.md":
                remove_path(source, repo)
            else:
                merge_file(source, repo / item["target"], repo)
    for item in plan["deletes"]:
        path = repo / item["path"]
        if path.exists():
            remove_path(path, repo)
    links = {item["source"]: item["target"] for item in [*plan["moves"], *plan["merges"]] if item.get("source") and not item["source"].startswith("(")}
    for path in repository_files(repo):
        if relative(path, repo) in plan["matt_upgrades"] or path.name in {"GLOSSARY.md", "GLOSSARY-MAP.md"} or path.suffix.lower() not in CALLER_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        updated = text
        for old, new in sorted(links.items(), key=lambda item: -len(item[0])):
            updated = updated.replace(old, new)
        if path == target_context:
            for old, new in sorted(links.items(), key=lambda item: -len(item[0])):
                updated = updated.replace(Path(old).name, Path(new).name)
        if updated != text:
            path.write_text(updated, encoding="utf-8")
    report = routing_report(repo, role, source_data_adoption=source_data_adoption)
    if report["action"] != "none":
        (repo / "AGENTS.md").write_text(report["proposed"], encoding="utf-8")
    final_routing = routing_report(repo, role)
    if not final_routing["satisfied"] or not all(final_routing["targets"].values()):
        raise SetupError("root guidance or its scientific targets failed verification: " + "; ".join(final_routing["missing"]))
    if repository_role(target_context) != role:
        raise SetupError("reconciliation did not produce the confirmed repository role")
    applied_plan = {**plan, "repository_role": role, "agent_role": agent_role_value}
    return {"applied": True, "repository": str(repo), "plan": plan_text(applied_plan).replace("No files were written by this preview.", "Approved plan applied.")}


def prepare(repo: Path, analysis_id: str, input_path: Path, manifest: Path,
            optional: Iterable[str] = (), *, role: str, agent_role_value: str | None = None,
            responsibilities: str | None = None,
            source_data_adoption: str | None = None) -> dict:
    repo = repo.resolve()
    input_path = input_path.resolve()
    manifest = manifest.resolve()
    validate_role(role)
    if not repo.is_dir() or not input_path.is_file():
        raise SetupError("repository and retained input must exist")
    try:
        input_path.relative_to(repo)
    except ValueError as exc:
        raise SetupError("retained input must be inside the repository") from exc
    if not analysis_id or any(part in {"", ".", ".."} for part in Path(analysis_id).parts) or "/" in analysis_id or "\\" in analysis_id:
        raise SetupError("analysis id must be one safe relative path component")
    ensure_manifest_writable(manifest)
    selected = []
    for name in optional:
        if name not in OPTIONAL:
            raise SetupError(f"unknown optional record: {name}")
        if name not in selected:
            selected.append(name)
    agents = repo / "AGENTS.md"
    scientific = repo / "docs/scientific"
    analysis = repo / "analyses" / analysis_id
    snapshot = analysis / "inputs" / input_path.name
    provenance = analysis / "inputs/provenance.json"
    context_before = scientific / "CONTEXT.md"
    context_resolved = context_before.resolve()
    if context_before.is_symlink() or not context_resolved.is_relative_to(repo):
        raise SetupError("scientific context destination is a symlink or escapes the repository")
    context_text = (context_before.read_text(encoding="utf-8") if context_before.is_file()
                    else (ASSETS / "CONTEXT.md").read_text(encoding="utf-8"))
    agent_role_value = require_agent_role(context_text, agent_role_value)
    context_text = canonical_context(context_text, role, agent_role_value, responsibilities,
                                     source_data_adoption)
    if malformed_markers(agents):
        raise SetupError("root AGENTS.md has duplicate or unmatched CSE Protocol markers; reconcile it manually first")
    report = routing_report(repo, role, agent_role_value, agent_role_state(context_text)["responsibilities"],
                            source_data_adoption)
    for name in MANDATORY:
        ensure_installable(ASSETS / name, scientific / name, preserve_existing=name == "CONTEXT.md")
    for name in selected:
        ensure_installable(ASSETS / OPTIONAL[name], scientific / OPTIONAL[name], preserve_existing=True)
    ensure_installable(input_path, snapshot)
    value = {"schema_version": 1, "source": relative(input_path, repo), "sha256": digest(input_path)}
    expected = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if provenance.exists() and (not provenance.is_file() or provenance.read_text(encoding="utf-8") != expected):
        raise SetupError(f"refusing to overwrite unrecognized file: {provenance}")
    if report["action"] != "none":
        agents.parent.mkdir(parents=True, exist_ok=True)
        agents.write_text(report["proposed"], encoding="utf-8")
    generated = [agents]
    for name in MANDATORY:
        target = scientific / name
        if name == "CONTEXT.md":
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.is_file() or target.read_text(encoding="utf-8") != context_text:
                target.write_text(context_text, encoding="utf-8")
        else:
            install_file(ASSETS / name, target)
        generated.append(target)
    for name in selected:
        target = scientific / OPTIONAL[name]
        install_file(ASSETS / OPTIONAL[name], target, preserve_existing=True)
        generated.append(target)
    install_file(input_path, snapshot)
    generated.append(snapshot)
    provenance.parent.mkdir(parents=True, exist_ok=True)
    provenance.write_text(expected, encoding="utf-8")
    generated.append(provenance)
    final_routing = routing_report(repo, role)
    if not final_routing["satisfied"] or not all(final_routing["targets"].values()):
        raise SetupError("root guidance or its scientific targets failed verification: " + "; ".join(final_routing["missing"]))
    result = {
        "schema_version": 1, "cse_source_commit": source_commit(), "analysis_id": analysis_id,
        "input": relative(input_path, repo), "input_sha256": digest(input_path),
        "generated": tracked(generated, repo),
    }
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--check-routing", action="store_true")
    parser.add_argument("--reconcile", action="store_true")
    parser.add_argument("--approve", "--apply", dest="approve", action="store_true")
    parser.add_argument("--role", choices=sorted(ROLE_VALUES))
    parser.add_argument("--agent-role", help="confirmed scientific discipline and specialization")
    parser.add_argument("--responsibilities", help="one paragraph of project-specific responsibilities")
    parser.add_argument("--source-data-adoption", choices=SOURCE_DATA_ADOPTION_VALUES,
                        help="record none, Zotero-curated sources, or project data adoption")
    parser.add_argument("--analysis-id")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--optional", default="")
    args = parser.parse_args()
    if args.check_routing or args.reconcile:
        if args.approve and args.role is None:
            parser.error("--role is required with --approve/--apply")
        try:
            plan = plan_reconciliation(args.repo, args.role, args.source_data_adoption)
            if args.approve:
                print(apply_reconciliation(args.repo, plan, args.role, args.agent_role, args.responsibilities,
                                           args.source_data_adoption)["plan"], end="")
            else:
                print(plan_text(plan), end="")
            if args.check_routing:
                report = routing_report(args.repo, args.role, args.agent_role, args.responsibilities,
                                        args.source_data_adoption)
                print(f"Routing: {'satisfied' if report['satisfied'] else 'needs reconciliation'}")
                print(f"Managed CSE Protocol block: {report['block']}; agent role: {report['agent_role'] or 'missing'}")
                for item in report["missing"]:
                    print(f"missing: {item}")
                for path, present in report["targets"].items():
                    print(f"{path}: {'readable' if present else 'missing'}")
                if report["diff"]:
                    print(report["diff"], end="")
        except (OSError, SetupError, ValueError) as exc:
            parser.exit(1, f"reconciliation failed: {exc}\n")
        if args.check_routing:
            report = routing_report(args.repo, args.role, args.agent_role, args.responsibilities,
                                    args.source_data_adoption)
            return 0 if report["satisfied"] and all(report["targets"].values()) else 1
        return 0
    if args.analysis_id is None or args.input is None or args.manifest is None or args.role is None:
        parser.error("--analysis-id, --input, --manifest, and --role are required for Setup")
    input_path = args.input if args.input.is_absolute() else args.repo / args.input
    try:
        prepare(args.repo, args.analysis_id, input_path, args.manifest,
                [item for item in args.optional.split(",") if item], role=args.role,
                agent_role_value=args.agent_role, responsibilities=args.responsibilities,
                source_data_adoption=args.source_data_adoption)
    except (OSError, SetupError, ValueError) as exc:
        parser.exit(1, f"setup failed: {exc}\n")
    print(args.manifest.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
