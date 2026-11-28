#!/usr/bin/env python3
"""Check scoped terminology and report advisory manuscript findings."""

from __future__ import annotations

import ast
import json
import zipfile
from xml.etree import ElementTree as ET
import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from bisect import bisect_right
import subprocess
import fnmatch
from pathlib import Path
import re
import tomllib

from cse_hook_common import CONTEXT, glossary_paths, has_source, markdown_tables, read_glossaries, split_scope

from manuscript_text import (
    DECLARATION, SECTION, group, hide, options, prepare_tex, tex_events, tex_sources, tex_visible,
)

TEXT_SUFFIXES = {".json", ".md", ".qmd", ".tex", ".toml", ".yaml", ".yml"}
PRECISE_PHRASES = {"schema": ["schema version"],
                   "context": ["hashed context files", "known context"]}
BANNED = Path(__file__).resolve().parents[2] / "BANNED.md"
if not BANNED.is_file():
    BANNED = Path(__file__).with_name("cse-BANNED.md")
FIELDS = ("Avoid", "Prefer", "Meaning", "Scope", "Exceptions", "Evidence")
# BANNED.md retains regression for fitting: a statistical qualifier before it or a
# fitted quantity after it marks that sense, unless a software test noun follows.
FITTING_BEFORE = re.compile(
    r"(?:statistical|parameters?|joint|coupled|linear|nonlinear|non-linear|least-squares"
    r"|weighted|orthogonal|ridge|bayesian|logistic|polynomial|multivariate|simultaneous)[\s-]+$", re.I)
FITTING_AFTER = re.compile(
    r"[\s-]+(?:parameters?|coefficients?|models?|fits?|analys[ie]s|estimation|estimates?|objectives?"
    r"|targets?|weights?|residuals?|figures?|campaigns?|stud(?:y|ies)|designs?|coordinates?|data"
    r"|observations?|based|against|onto)\b", re.I)
SOFTWARE_AFTER = re.compile(r"[\s-]+(?:tests?|suites?|checks?)\b", re.I)


def text_files(paths: list[Path]):
    for path in paths:
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
            yield path
        elif path.is_dir():
            yield from (
                item
                for item in path.rglob("*")
                if item.is_file() and item.suffix.lower() in TEXT_SUFFIXES
            )


def phrase_pattern(phrase: str) -> re.Pattern[str]:
    return re.compile(rf"(?<!\w){re.escape(phrase)}(?!\w)", re.IGNORECASE)


def validate_rule(entry: dict, source: str) -> dict:
    missing = [field for field in FIELDS if field not in entry]
    if missing:
        raise ValueError(f"{source}: missing field(s): {', '.join(missing)}")
    for field in ("Avoid", "Prefer", "Meaning", "Evidence"):
        if not isinstance(entry[field], str) or not entry[field].strip():
            raise ValueError(f"{source}: {field} must be a nonempty string")
    for field in ("Scope", "Exceptions"):
        if not isinstance(entry[field], list) or not all(
            isinstance(value, str) and value.strip() for value in entry[field]
        ):
            raise ValueError(f"{source}: {field} must be a string array")
    if not entry["Scope"]:
        raise ValueError(f"{source}: Scope must contain at least one path glob")
    return entry | {"source": source}


def load_personal_rules(path: Path) -> list[dict]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    entries = data.get("terminology", [])
    if not isinstance(entries, list):
        raise ValueError(f"{path}: terminology must be an array of tables")
    return [
        validate_rule(entry, f"{path}:terminology[{index}]")
        for index, entry in enumerate(entries, 1)
    ]


def project_rules(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rules = []
    for table in markdown_tables(path.read_text(encoding="utf-8")):
        if table["section"] != "Prose avoid rules":
            continue
        for row in table["rows"]:
            if len(row["cells"]) != len(table["headers"]):
                raise ValueError(f"{path}:{row['index'] + 1}: row does not match its table headings")
            names = {field.casefold(): field for field in FIELDS}
            entry = {names.get(header.casefold(), header): cell for header, cell in zip(table["headers"], row["cells"])}
            for field in ("Avoid", "Prefer"):
                if field in entry:
                    entry[field] = entry[field].strip("`")
            entry["Scope"] = split_scope(entry.get("Scope", ""))
            entry["Exceptions"] = [part.strip().strip("`") for part in entry.get("Exceptions", "").split(";") if part.strip()]
            entry["Evidence"] = entry.get("Evidence") or "sourceless"
            rules.append(validate_rule(entry, f"{path}:{row['index'] + 1}"))
    return rules


def glossary_rules(entries: list[dict]) -> list[dict]:
    return [{"Avoid": term, "Prefer": entry["term"], "Meaning": entry["meaning"],
             "Scope": entry["scope"], "Exceptions": [], "Evidence": entry["source"],
             "source": entry["locator"]}
            for entry in entries for term in entry["avoid"]]


def reject_conflicts(rules: list[dict]) -> None:
    """Check rules that actually overlap at the file being inspected."""
    for index, first in enumerate(rules):
        for second in rules[index + 1 :]:
            if (
                first["Avoid"].casefold() == second["Avoid"].casefold()
                and (first["Prefer"].casefold() != second["Prefer"].casefold()
                     or {value.casefold() for value in first["Exceptions"]}
                     != {value.casefold() for value in second["Exceptions"]})
            ):
                raise ValueError(
                    f"terminology conflict for {first['Avoid']!r}: "
                    f"{first['source']} and {second['source']}"
                )


def relative_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def occurrence_is_excepted(line: str, start: int, end: int, exceptions: list[str]) -> bool:
    return any(
        match.start() <= start and end <= match.end()
        for exception in exceptions
        for match in phrase_pattern(exception).finditer(line)
    )


def banned_rules(path: Path = BANNED) -> list[dict]:
    """Read the maintained rows, retaining qualifiers instead of banning substrings."""
    rules = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.startswith("| `") and not line.startswith("| a `"):
            continue
        cells = line.strip("|").split("|")
        if len(cells) != 2:
            raise ValueError(f"{path}:{number}: invalid banned-language row")
        terms = re.findall(r"`([^`]+)`", cells[0])
        for term in terms:
            rules.append({"Avoid": term, "Prefer": cells[1].strip(),
                          "qualifier": cells[0], "source": f"{path}:{number}"})
    if not rules:
        raise ValueError(f"{path}: no banned-language rows")
    return rules


def prose_lines(text: str):
    fence = None
    for number, line in enumerate(text.splitlines(), 1):
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker:
            if fence is None:
                fence = marker[1][0]
            elif marker[1][0] == fence:
                fence = None
            continue
        if fence or line.lstrip().startswith((">", "%")):
            continue
        # Preserve positions so diagnostics refer to the original line.
        # Link targets are filenames or URLs; the link text stays checked.
        line = re.sub(r"(\]\()([^)]*)", lambda m: m[1] + " " * len(m[2]), line)
        line = re.sub(r"^(\s{0,3}\[(?!\^)[^\]]+\]:)(.*)", lambda m: m[1] + " " * len(m[2]), line)
        line = re.sub(r'"[^"\n]*"|“[^”\n]*”', lambda m: " " * len(m[0]), line)
        line = re.sub(r"(?<!\w)'[^'\n]+'(?!\w)|‘[^’\n]*’", lambda m: " " * len(m[0]), line)
        line = re.sub(r"`([^`]+)`", lambda m: " " * len(m[0])
                      if re.fullmatch(r"[\w./:=()<>-]+", m[1])
                      or re.match(r"(?:python[\d.]*|bash|git|codex|uv|quarto|rg)\s", m[1])
                      else m[0], line)
        yield number, line


def violations(paths: list[Path], *, rules: list[dict] | None = None,
               forbidden: list[str] = (), root: Path | None = None,
               sources=None, expansions=None, changed=None) -> list[str]:
    root = root or Path.cwd()
    entries = read_glossaries(root)
    scientific_context = root / CONTEXT
    rules = glossary_rules(entries) + project_rules(scientific_context) + (rules or [])
    global_rules = banned_rules() + [
        {"Avoid": term, "Prefer": "precise scientific language", "qualifier": "", "source": "--forbid"}
        for term in forbidden
    ]
    failures = []
    # Vocabulary records configure the check; their term and avoid lists are not prose.
    rule_files = {path.resolve() for path in glossary_paths(root)} | {BANNED.resolve(), (root / "GLOSSARY-MAP.md").resolve()}
    for path in text_files(paths):
        if path.resolve() in rule_files:
            continue
        relative = relative_path(path, root)
        exceptions = [entry["term"] for entry in entries if has_source(entry)
                      and any(fnmatch.fnmatchcase(relative, scope) for scope in entry["scope"])]
        active = [r for r in rules if any(fnmatch.fnmatchcase(relative, s) for s in r["Scope"])]
        reject_conflicts(active)
        text = path.read_text(encoding="utf-8")
        original_lines = text.splitlines()
        if path.suffix.lower() == ".tex":
            if sources is None:
                prepared, macros = prepare_tex(text)
            else:
                resolved = path.resolve()
                prepared, macros = sources[resolved][0], expansions[resolved]
            checked = tex_visible(without_declarations(prepared, ".tex"), macros, math=True)
        else:
            checked = without_declarations(text, path.suffix.lower())
        lines = dict(prose_lines(checked))
        if path.resolve() == scientific_context.resolve():
            for table in markdown_tables(text):
                if table["section"] == "Prose avoid rules":
                    for row in table["rows"]:
                        lines.pop(row["index"] + 1, None)
        for number, line in lines.items():
            if changed is not None and not changed(path, number, number):
                continue
            for rule in global_rules + active:
                term = rule["Avoid"]
                for match in phrase_pattern(term).finditer(line):
                    if occurrence_is_excepted(
                        line, match.start(), match.end(),
                        exceptions + rule.get("Exceptions", []) + PRECISE_PHRASES.get(term, []),
                    ):
                        continue
                    tail = line[match.end():]
                    if re.match(r"`?\s*(?:means\b|:\s*\S)", tail, re.I):
                        continue
                    qualifier = rule.get("qualifier", "")
                    if "scientific result" in qualifier and not re.search(r"\b(result|success|passed|complete)\b", line, re.I):
                        continue
                    if term == "context" and re.search(r"(?:scientific|repository|task)\s+$", line[:match.start()], re.I):
                        continue
                    if term == "pipeline" and re.search(r"data\s+$", line[:match.start()], re.I):
                        continue
                    if term.startswith("regress"):
                        before = lines.get(number - 1, "") + " " + line[:match.start()]
                        after = tail + " " + lines.get(number + 1, "")
                        if not SOFTWARE_AFTER.match(after) and (
                            FITTING_BEFORE.search(before) or FITTING_AFTER.match(after)
                        ):
                            continue
                    failures.append(f"{path}:{number}: avoid {term!r} → {rule['Prefer']} ({rule['source']}): {original_lines[number - 1]}")
    return failures


IDENTIFIER_SUFFIXES = {".md", ".qmd", ".tex", ".py", ".pptx"}
IDENTIFIERS = {
    "issue/PR": r"(?i:\b(?:issue|pr)\s*#?\s*\d+\b)",
    "run/fit label": r"(?<![\w/])(?:F|A)\d+(?:[-–](?:[FA])?\d+)?(?![\w/])",
    "hash": r"(?i:\b(?:commit|sha-?256)(?:\s+(?:hash|prefix))?\s*[:=]?\s*[0-9a-f]{6,64}\b|(?<!\w)(?:[0-9a-f]{40}|[0-9a-f]{64})(?!\w))",
    "repository path": r"(?<![\w/:])(?:\.{1,2}/|/)?(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]*[A-Za-z0-9_-](?![\w/])",
}
# Code-style numbers in prose (scientific-writing.md#equations-quantities-and-units).
PRINT_FORM = re.compile(r"(?<![\w.])(?:0|[1-9]\d*)(?:\.\d+)?[eE][-+]?\d+(?![\w.])|\d\s*\*\s*\d|(?<![\w.])\d+(?:\.\d+)?[kM](?!\w)")
SUPERSCRIPT = str.maketrans("⁻⁰¹²³⁴⁵⁶⁷⁸⁹", "-0123456789")
# A magnitude written as mantissa × 10^exponent, E-notation, Unicode superscripts, or a long decimal.
MAGNITUDE = re.compile(
    r"(?<![\w.])(?:(?P<m>\d+(?:\.\d+)?)\s*(?:\\times|\\cdot|×|·)\s*)?10\s*"
    r"(?:\^\s*\{?\s*(?P<e>[-−]\s*\d+)|(?P<u>⁻[⁰¹²³⁴⁵⁶⁷⁸⁹]+))"
    r"|(?<![\w.])(?P<em>\d+(?:\.\d+)?)[eE](?P<ee>-\d+)(?![\w.])"
    r"|(?<![\w.])(?P<d>0\.0{5,}\d+)")
ROUNDOFF_CONTEXT = re.compile(r"(?i)\b(?:residual|toleran|numerical\s+error|round|converg|agree|differ|certificat)")
NUMERIC_VALUE = re.compile(
    r"(?<!\w)[+−-]?(?:10\s*\^\s*[+−-]?\s*\d+|(?:\d{1,3}(?:,\d{3})+|\d+|(?=\.\d))(?:\.\d+)?"
    r"(?:[eE][+−-]?\d+|\s*[×·]\s*10(?:[⁺⁻⁰¹²³⁴⁵⁶⁷⁸⁹]+|\s*\^\s*[+−-]?\s*\d+))?)(?!\w|\.\d)"
)
SENTENCE_END = re.compile(r"(?<=[.!?])[”’\"')\]]*(?:\s+|$)")
LINK_TARGET = r"(?:[A-Za-z][\w+.-]*://|www\.)\S+|\b10\.\d{4,9}/[^\s}]+"


def without_declarations(text, suffix):
    """Keep required declarations out of terminology enforcement."""
    if suffix == ".tex":
        heads = [(match, group(text, options(text, match.end()))) for match in SECTION.finditer(text)]
        text = hide(r"\\begin\{(funding|disclaimer|conflictsofinterest|competinginterests)\}.*?\\end\{\1\}", text, re.S)
    elif suffix in {".md", ".qmd"}:
        visible = dict(prose_lines(text))
        heads = []
        offset = 0
        for number, line in enumerate(text.splitlines(keepends=True), 1):
            if heading := re.match(r"^#{1,6}[ \t]+(.+)", visible.get(number, "")):
                heads.append((offset, (offset + heading.start(1), offset + heading.end(1))))
            offset += len(line)
        return hide_declaration_sections(text, heads)
    else:
        return text
    return hide_declaration_sections(text, [(match.start(), title) for match, title in heads])


def hide_declaration_sections(text, heads):
    for index, (start, title) in enumerate(heads):
        if title and DECLARATION.search(text[title[0]:title[1]]):
            end = heads[index + 1][0] if index + 1 < len(heads) else len(text)
            text = text[:start] + hide(r"[^\n]", text[start:end]) + text[end:]
    return text


def visible_lines(text, suffix, math=False, prose_only=False, macros=None):
    """Mask commands and metadata while retaining source line numbers."""
    if suffix == ".tex":
        yield from ((str(number), line) for number, line in enumerate(
            tex_visible(text, macros or {}, math, prose_only).splitlines(), 1))
        return
    text = hide(r"<!--.*?-->", text, re.S)
    if not math:
        text = hide(r"(?s)\$\$.*?\$\$|(?<!\\)\$[^$]*\$|\\\(.*?\\\)|\\\[.*?\\\]", text)
    if prose_only:
        text = hide(r"<table\b[^>]*>.*?</table\s*>", text, re.S | re.I)
        text = hide(r"(?m)^ {0,3}[^\n]*\|[^\n]*\n"
                    r" {0,3}\|?[ \t]*:?-+:?(?:[ \t]*\|[ \t]*:?-+:?)*[ \t]*\|?[ \t]*$"
                    r"(?:\n {0,3}[^\n]*\|[^\n]*)*", text)
    fence = None
    metadata = False
    caption = False
    for number, line in enumerate(text.splitlines(), 1):
        if number == 1 and line.strip() == "---":
            metadata = True
            continue
        if metadata and line.strip() in {"---", "..."}:
            metadata = caption = False
            continue
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker:
            fence = None if fence == marker[1][0] else marker[1][0]
            continue
        option = re.match(r"\s*#\|\s*(.*)", line)
        if metadata or option:
            field = re.match(r"\s*([\w-]+):\s*(.*)", option[1] if option else line)
            if field:
                caption = field[1] in {"title", "subtitle", "fig-cap", "tbl-cap", "fig-alt"}
                line = field[2] if caption else ""
            elif option and caption:
                line = option[1]
            elif not caption or not line.startswith((" ", "\t")):
                continue
        elif fence or line.startswith(("    ", "\t")):
            continue
        line = hide(r"`[^`]*(?:[A-Za-z_]\w*\(|\s=\s)[^`]*`", line)
        line = hide(r"`+(?:\{[rR]|\{python|python[\d.]*\s|bash\s|git\s|codex\s|uv\s|quarto\s|rg\s)[^`]*`+", line)
        if prose_only:
            line = hide(r"\[[^\]\n]*@[\w:.-]+[^\]\n]*\]|\[\d+(?:\s*[,–-]\s*\d+)*\](?!\()", line)
        line = hide(r"(?<=\])\([^)]*\)|(?<=\])\[[^]]*\]|^\s{0,3}\[(?!\^)[^]]+\]:.*|\{[^}]*#[^}]*\}|(?<!\w)@[\w:.-]+", line)
        yield str(number), line


def figure_text(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    def literals(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value, False
        if isinstance(node, (ast.List, ast.Tuple, ast.JoinedStr)):
            pieces = [literals(item) for item in (node.values if isinstance(node, ast.JoinedStr) else node.elts)]
            return ("" if isinstance(node, ast.JoinedStr) else " ").join(p[0] for p in pieces), any(p[1] for p in pieces)
        return " ", True
    for call in ast.walk(tree):
        if not isinstance(call, ast.Call):
            continue
        name = getattr(call.func, "attr", getattr(call.func, "id", ""))
        nodes = [kw.value for kw in call.keywords if kw.arg in {"xlabel", "ylabel", "title", "label"}
                 or (name == "legend" and kw.arg == "labels") or (name in {"text", "annotate"} and kw.arg in {"s", "text"})]
        position = 2 if name == "text" else 0
        if name in {"xlabel", "ylabel", "title", "suptitle", "set_xlabel", "set_ylabel", "set_title", "text", "annotate", "set_xticklabels", "set_yticklabels"} and len(call.args) > position:
            nodes.append(call.args[position])
        for node in nodes:
            text, dynamic = literals(node)
            yield str(node.lineno), text
            if dynamic:
                yield str(node.lineno), None


def slide_text(path):
    with zipfile.ZipFile(path) as archive:
        for part in sorted(archive.namelist()):
            if not re.fullmatch(r"ppt/slides/slide\d+\.xml", part):
                continue
            ns = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
            for number, paragraph in enumerate(ET.fromstring(archive.read(part)).iter(ns + "p"), 1):
                text = "".join(
                    "\n" if el.tag == ns + "br" else el.text or ""
                    for el in paragraph.iter() if el.tag in {ns + "t", ns + "br"})
                yield f"{part}:paragraph {number}", text


class EditorialStyle:
    """Read the document sources and machine-readable decisions from STYLE once."""

    def __init__(self, root, notices):
        self.root = root
        self.path = root / "docs/scientific/writing/STYLE.md"
        self.notices = notices
        self.sections = [((), [])]
        if self.path.is_file():
            for number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), 1):
                if line.startswith("## "):
                    self.sections.append(((), []))
                elif line.startswith("Sources:"):
                    self.sections[-1] = (self.scopes(line.partition(":")[2]), self.sections[-1][1])
                else:
                    self.sections[-1][1].append((number, line))

    def scopes(self, value):
        scopes = []
        for part in value.split(";"):
            part = part.strip().strip("`")
            if not part:
                continue
            tag = re.match(r"(?i)(main|supplement):\s*(.*)", part)
            role, path = (tag[1].lower(), tag[2].strip("`")) if tag else (None, part)
            if Path(path).is_absolute() or ".." in Path(path).parts:
                self.notices.append(f"{self.path}: incomplete scan: invalid approval path")
                return []
            scopes.append((role, path))
        return scopes

    def for_file(self, path, inherited=None):
        relative = relative_path(path, self.root)
        role = ("supplement" if re.search(
            r"(?i)(?:^|[/_.-])(?:supplements?|supplementary|supporting[-_ ]information|appendix|si)(?=$|[/_.-])",
            relative) else inherited)
        explicit_role = None
        labels, exemptions, limit = set(), set(), 250
        for sources, lines in self.sections:
            for index, (tag, pattern) in enumerate(sources):
                if fnmatch.fnmatchcase(relative, pattern):
                    explicit_role = tag or explicit_role
                    # STYLE lists the main source first; included files inherit the enclosing source's role.
                    if index and not role and path.suffix.lower() in {".tex", ".md", ".qmd"}:
                        role = "supplement"
                    break
            else:
                if sources:
                    continue
            for number, line in lines:
                cells = [part.strip() for part in line.strip().strip("|").split("|")]
                decision = cells[1] if len(cells) == 3 else line.strip()
                values = re.findall(r"`([^`]+)`", decision)
                if "Approved scientific labels:" in line or "Approved numerical values:" in line:
                    numeric = "Approved numerical values:" in line
                    prefix = "Approved numerical values:" if numeric else "Approved scientific labels:"
                    if len(cells) != 3 or not decision.startswith(prefix) or not cells[2] or not values:
                        kind = "numerical-value" if numeric else "scientific-label"
                        self.notices.append(f"{self.path}:{number}: incomplete scan: malformed {kind} approval")
                    elif sources and any(fnmatch.fnmatchcase(relative, scope) for _, scope in self.scopes(cells[0])):
                        (exemptions if numeric else labels).update(values)
                elif match := re.fullmatch(r"(?i)abstract(?: word)? limit:\s*([1-9]\d*)\s+words\.?", decision):
                    if len(cells) != 3 or (cells[2] and any(fnmatch.fnmatchcase(relative, scope) for _, scope in self.scopes(cells[0]))):
                        limit = int(match[1])
                elif sources and re.search(r"(?i)\b(pointer|external|brief)\b", line):
                    self.notices.append(f"{self.path}:{number}: incomplete scan: external editorial approval requires inspection")
        return (explicit_role or role or "main", labels,
                {compact_value(tex_visible(value, {}, math=True)) for value in exemptions}, limit)

def magnitude(match):
    if match["d"]:
        return float(match["d"])
    if match["em"]:
        return float(match["em"]) * 10 ** int(match["ee"])
    exponent = match["e"] or match["u"].translate(SUPERSCRIPT)
    return float(match["m"] or 1) * 10 ** int(re.sub(r"\s", "", exponent).replace("−", "-"))


@dataclass(frozen=True)
class Finding:
    path: Path
    location: str
    kind: str
    message: str
    end: int | None = None

    @property
    def is_advisory(self):
        return self.kind != "abstract-opener"

    def __str__(self):
        label = "warning" if self.is_advisory else "inspection"
        return f"{self.path}:{self.location}: {label}: {self.message}"

    def on_changed_lines(self, changed):
        if changed is None:
            return True
        if not self.location.isdecimal():
            return changed(self.path, 0, 0)
        return changed(self.path, int(self.location), self.end or int(self.location))


FITNESS = "numerical-testing.md#fitness-for-purpose"
WRITING = "scientific-writing.md#"


def numerical_warnings(path, lines, numeric_lines, exemptions):
    """Inspect raw print forms and small numerical values near roundoff language."""
    for location, line in lines:
        if line is None:
            continue
        line = hide(LINK_TARGET + r"|`[^`]*`", line)
        for match in PRINT_FORM.finditer(line):
            if compact_value(match[0]) in exemptions:
                continue
            yield Finding(path, location, "print-form",
                          f"print form {match[0]!r}: write the printed number ({WRITING}equations-quantities-and-units)")
    for location, line in numeric_lines:
        if line is None:
            continue
        line = hide(LINK_TARGET, line)
        for match in roundoff_values(line, exemptions):
            if not ROUNDOFF_CONTEXT.search(line[max(0, match.start() - 80):match.end() + 80]):
                continue
            value = re.sub(r"\{\s*(?=[-−])", "", match[0].strip())
            yield Finding(path, location, "roundoff",
                          f"roundoff-scale numerical detail '{value}' in a deliverable: "
                          "does it change a reported value, a conclusion or a decision? If not, move it to the record "
                          f"({FITNESS})")
            break


def compact_value(value):
    return re.sub(r"[\s{}]", "", value)


def roundoff_values(text, exempt):
    for match in MAGNITUDE.finditer(text):
        if compact_value(match[0]) not in exempt and 0 < magnitude(match) <= 1e-6:
            yield match


def density_warnings(path, lines):
    start = previous = count = 0
    for location, line in lines:
        number = int(location)
        line = hide(LINK_TARGET + r"|`[^`]*`", line)
        if number != previous + 1 or not line.strip():
            start = count = 0
        previous = number
        # shortcut: punctuation and source-line boundaries approximate sentences; inspect the rendered prose for abbreviations or generated text.
        for index, part in enumerate(SENTENCE_END.split(line)):
            if index:
                start = count = 0
            if not part.strip():
                continue
            start = start or number
            before = count
            count += sum(1 for _ in NUMERIC_VALUE.finditer(part))
            if before <= 4 < count:
                yield Finding(path, str(start), "sentence-density",
                              "numeric density: more than four numeric values in one sentence; "
                              "use the conditions table and result plot principle (scientific-writing.md#argument)", number)


def identifier_findings(paths, *, style, notices, sources=None, expansions=None, styles=None):
    files = (item for path in paths for item in (path.rglob("*") if path.is_dir() else [path]))
    for path in files:
        if not path.is_file() or path.suffix.lower() not in IDENTIFIER_SUFFIXES or path.resolve() == style.path.resolve():
            continue
        try:
            _, labels, exemptions, _ = styles[path] if styles is not None else style.for_file(path)
            suffix = path.suffix.lower()
            if suffix == ".pptx":
                lines = numeric_lines = list(slide_text(path))
            elif suffix == ".py":
                lines = numeric_lines = list(figure_text(path))
            else:
                if suffix == ".tex" and sources:
                    text = sources[path.resolve()][0]
                    macros = expansions[path.resolve()]
                elif suffix == ".tex":
                    text, macros = prepare_tex(path.read_text(encoding="utf-8"))
                else:
                    text, macros = path.read_text(encoding="utf-8"), {}
                lines = list(visible_lines(text, suffix, macros=macros))
                numeric_lines = visible_lines(text, suffix, math=True, macros=macros)
            for location, line in lines:
                if line is None:
                    notices.append(f"{path}:{location}: incomplete scan: dynamic figure label; inspect assembled figure")
                    continue
                line = hide(LINK_TARGET, line)
                for category, pattern in IDENTIFIERS.items():
                    for match in re.finditer(pattern, line):
                        value = match[0]
                        if category == "run/fit label" and value in labels:
                            continue
                        if category == "hash" and re.fullmatch(r"[0-9a-fA-F]+", value) and not (re.search(r"\d", value) and re.search(r"[a-f]", value, re.I)):
                            continue
                        if category == "repository path" and not looks_like_path(value):
                            continue
                        yield Finding(path, location, category.replace(" ", "-"),
                                      f"{category} {value!r} (writing-editorial.md#reader-facing-identifiers)")
            yield from numerical_warnings(path, lines, numeric_lines, exemptions)
            if suffix in {".md", ".qmd", ".tex"}:
                yield from density_warnings(path, visible_lines(text, suffix, prose_only=True, macros=macros))
        except (OSError, UnicodeError, ValueError, SyntaxError, zipfile.BadZipFile, ET.ParseError, RuntimeError) as error:
            notices.append(f"{path}: incomplete scan: {error}")


def looks_like_path(value):
    # A bare mixture or material name with slashes has no repository prefix or file extension.
    return value.startswith(("./", "../", "/", "analyses/", "docs/", "scripts/", "src/",
                             "tests/", "results/", "data/", "plugin/")) or Path(value).suffix.lower() in {
        ".py", ".tex", ".qmd", ".md", ".csv", ".tsv", ".json", ".yaml", ".yml", ".toml",
        ".parquet", ".npz", ".npy", ".pdf", ".png", ".svg", ".pptx", ".whl"
    }


def identifier_warnings(paths, *, root=None):
    """Keep the Stop hook's advisory-only, changed-file interface."""
    root = root or Path.cwd()
    notices = []
    style = EditorialStyle(root, notices)
    findings = list(identifier_findings(paths, style=style, notices=notices))
    return [*(str(finding) for finding in findings), *dict.fromkeys(notices)]


WORDS = re.compile(r"[^\W\d_]+(?:[’'-][^\W\d_]+)*")
CLAUSE_TOKEN = re.compile(NUMERIC_VALUE.pattern + "|" + WORDS.pattern)
# Match wording that calls for inspection of the numerical result record.
NON_RESULT = re.compile(r"\b(?:did not converge|not established|unconverged|cause unknown|provisional)\b", re.I)
# Use hedge words only in the final sentence of a section or caption.
HEDGE = re.compile(r"\b(?:however|nevertheless|only|may|might|could|subject to|except|"
                   r"caveat|limitation|remains? uncertain|should be interpreted with caution)\b", re.I)
# Review coverage terms in abstracts and conclusions, where they can broaden the headline claim.
CERTAINTY = re.compile(r"\b(?:every|all|confirmed|verified)\b", re.I)
CONCLUSIONS = re.compile(r"(?i)^(?:(?:summary|discussion) and )?conclusions?\b")


@dataclass(frozen=True)
class Passage:
    path: Path
    line: int
    text: str

    @property
    def end(self):
        return self.line + self.text.count("\n")

    def finding(self, kind, message, anchor):
        return Finding(self.path, str(self.line), kind, f"{message} ({anchor})", self.end)

    def sentences(self):
        # shortcut: punctuation splits sentences; inspect the assembled prose around abbreviations.
        start = 0
        boundaries = [(match.start() + len(match[0].rstrip()), match.end())
                      for match in SENTENCE_END.finditer(self.text)]
        for end, next_start in [*boundaries, (len(self.text), len(self.text))]:
            chunk = self.text[start:end]
            content = chunk.strip()
            if content:
                offset = start + len(chunk) - len(chunk.lstrip())
                yield Passage(self.path, self.line + self.text.count("\n", 0, offset), content)
            start = next_start


def tex_passages(path, sources, display, macros, stack=()):
    text, _, links, error = sources[path]
    if error or path in stack:
        return
    newlines = [match.end() for match in re.finditer("\n", text)]
    for kind, start, end, content in tex_events(text, links):
        if kind == "include":
            yield from tex_passages(content, sources, display, macros, (*stack, path))
        else:
            printed = tex_visible(text[start:end] if content is None else content, macros, math=True, prose_only=True)
            printed = hide(LINK_TARGET, printed)
            stripped = printed.strip()
            if stripped or kind.endswith(" abstract"):
                line = bisect_right(newlines, start) + 1 + printed[:len(printed) - len(printed.lstrip())].count("\n")
                yield kind, Passage(display[path], line, stripped)


def markdown_passages(path):
    # shortcut: headings and pipe tables cover manuscript Markdown; custom Quarto layouts need a rendered read.
    text = path.read_text(encoding="utf-8")
    for table in markdown_tables(text):
        for cells, line in [(table["headers"], table["start"] + 1),
                            *((row["cells"], row["index"] + 1) for row in table["rows"])]:
            for cell in cells:
                yield "cell", Passage(path, line, hide(LINK_TARGET, cell))
    paragraph = []
    start = previous = 0
    for loc, line in [*visible_lines(text, path.suffix.lower(), math=True, prose_only=True), ("0", "")]:
        number = int(loc)
        heading = re.match(r"^#{1,6}\s+(.*)", line)
        line = hide(LINK_TARGET + r"|`[^`]*`", line).strip()
        if paragraph and (number != previous + 1 or not line or heading):
            yield "paragraph", Passage(path, start, "\n".join(paragraph))
            paragraph = []
        if heading:
            yield "section", Passage(path, number, heading[1])
        elif line:
            if not paragraph:
                start = number
            paragraph.append(line)
        previous = number


def manuscript_findings(events, roles, styles, repeated):
    abstract = None
    section_end = None
    conclusions = False
    ending = lambda sentence: sentence.finding(
        "caveat-ending", "caveat ending: read the final sentence against the main finding",
        WRITING + "emphasis-in-proportion")
    for kind, passage in events:
        if kind in {"section", "begin abstract", "end abstract"}:
            if section_end and HEDGE.search(section_end.text):
                yield ending(section_end)
            section_end = None
            conclusions = kind == "section" and bool(CONCLUSIONS.match(passage.text))
            if kind == "end abstract" or (abstract is not None and kind == "section"):
                yield from abstract_findings(abstract, styles)
                abstract = None
            if kind == "begin abstract" or (kind == "section" and passage.text.casefold() == "abstract"):
                abstract = []
            continue
        words = len(WORDS.findall(passage.text))
        if kind in {"cell", "note", "caption"}:
            limit = 12 if kind == "cell" else 60
            label = {"cell": "table cell", "note": "table note", "caption": "caption"}[kind]
            if words > limit:
                yield passage.finding(label.replace(" ", "-") + "-length",
                                      f"{label} length: {words} words (limit {limit})",
                                      WRITING + "shared-article-requirements")
        elif kind == "paragraph":
            # Count printed quantities together across all sentences in each paragraph.
            numeric_text = passage.text
            for pattern in IDENTIFIERS.values():
                numeric_text = hide(pattern, numeric_text)
            values = sum(compact_value(value) not in styles[passage.path][2]
                         for value in NUMERIC_VALUE.findall(numeric_text))
            if words > 150 and roles[passage.path] == "main":
                yield passage.finding("paragraph-length", f"paragraph length: {words} words (limit 150)",
                                      WRITING + "argument")
            if values > 6:
                yield passage.finding("paragraph-density",
                                      f"paragraph density: {values} values in {words} words (over 6)",
                                      WRITING + "argument")
            if abstract is not None:
                abstract.append(passage)
        sentences = list(passage.sentences())
        if kind == "caption" and sentences and HEDGE.search(sentences[-1].text):
            yield ending(sentences[-1])
        if kind == "paragraph" and sentences and abstract is None:
            section_end = sentences[-1]
        for sentence in sentences:
            count = len(WORDS.findall(sentence.text))
            if count > 60 and kind != "cell":
                yield sentence.finding("long-sentence", f"long sentence: {count} words (limit 60)",
                                       WRITING + "scientific-prose")
            if match := NON_RESULT.search(sentence.text):
                yield sentence.finding("non-result", f"non-result wording {match[0]!r}: inspect the numerical evidence",
                                       "failure-triage.md#fix-before-a-negative-disposition")
            if (conclusions or abstract is not None) and (matches := CERTAINTY.findall(sentence.text)):
                terms = ", ".join(dict.fromkeys(term.lower() for term in matches))
                yield sentence.finding("certainty", f"certainty words: {terms}. Check coverage against the evidence",
                                       WRITING + "evidence-guard")
            # shortcut: exact, normalized clauses of at least eight words catch copy-paste, and miss paraphrases.
            if kind in {"paragraph", "caption", "note"}:
                for match in re.finditer(r"[^;:,]+", sentence.text):
                    clause = match[0].lstrip()
                    if len(WORDS.findall(clause)) >= 8:
                        key = " ".join(word.casefold() for word in CLAUSE_TOKEN.findall(clause))
                        offset = match.end() - len(clause)
                        repeated[key].setdefault(sentence.path, Passage(
                            sentence.path, sentence.line + sentence.text.count("\n", 0, offset), clause))
    if abstract is not None:
        yield from abstract_findings(abstract, styles)
    if section_end and HEDGE.search(section_end.text):
        yield ending(section_end)


def abstract_findings(paragraphs, styles):
    if not paragraphs:
        return
    first = paragraphs[0]
    limit = styles[first.path][3]
    words = sum(len(WORDS.findall(passage.text)) for passage in paragraphs)
    if words > limit:
        yield Finding(first.path, str(first.line), "abstract-length",
                      f"abstract length: {words} words (limit {limit}) ({WRITING}structure)",
                      max(p.end for p in paragraphs if p.path == first.path))
    opener = next(first.sentences())
    yield opener.finding("abstract-opener", "abstract opener: " + " ".join(opener.text.split()),
                         WRITING + "structure; manuscript-review.md#story-spine-read")
    for passage in paragraphs:
        for match in roundoff_values(passage.text, styles[passage.path][2]):
            line = str(passage.line + passage.text.count("\n", 0, match.start()))
            yield Finding(passage.path, line, "abstract-roundoff",
                          f"abstract roundoff: {' '.join(match[0].split())!r} ({WRITING}structure; {FITNESS})")


def git_lines(root, revision):
    def git(*args):
        result = subprocess.run(["git", "-C", str(root), "--literal-pathspecs", *args],
                                text=True, capture_output=True)
        if result.returncode:
            raise ValueError(result.stderr.strip())
        return result.stdout

    repository = Path(git("rev-parse", "--show-toplevel").strip())
    commit = git("rev-parse", "--verify", "--end-of-options", revision + "^{commit}").strip()
    tracked = set(git("ls-files", "--full-name", "-z").split("\0"))
    ranges = {}

    def changed(path, start, end):
        try:
            relative = path.resolve().relative_to(repository).as_posix()
        except ValueError:
            return False
        if relative not in tracked:
            return True
        if start == 0:
            return bool(git("diff", "--name-only", "-z", commit, "--", str(path.resolve())))
        if relative not in ranges:
            diff = git("diff", "--no-ext-diff", "--no-textconv", "--no-color", "--unified=0", commit, "--", str(path.resolve()))
            ranges[relative] = [(int(first), int(count or 1)) for first, count in
                                re.findall(r"(?m)^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", diff)]
        return any(count and first <= end and start < first + count for first, count in ranges[relative])

    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--forbid", action="append", default=[])
    parser.add_argument("--config", type=Path)
    parser.add_argument("--since", metavar="REV", help="report findings on lines changed since REV")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="project root containing GLOSSARY.md or GLOSSARY-MAP.md")
    parser.add_argument("--summary-json", action="store_true", help="print only the summary counts as JSON")
    args = parser.parse_args()

    notices = []
    try:
        rules = load_personal_rules(args.config) if args.config else []
        changed = git_lines(args.root, args.since) if args.since else None
        style = EditorialStyle(args.root, notices)
        paths = {}
        for arg in args.paths:
            for path in sorted(arg.rglob("*")) if arg.is_dir() else [arg]:
                if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES | IDENTIFIER_SUFFIXES:
                    paths.setdefault(path.resolve(), path)
        sources = tex_sources(path for path in paths if path.suffix.lower() == ".tex")
        for path, (_, _, _, error) in sources.items():
            if error:
                notices.append(f"{path}: incomplete scan: {error}")
            else:
                shown = Path(relative_path(path, Path.cwd()))
                paths.setdefault(path, shown)
        roles, styles = {}, {}

        def select(path, inherited=None):
            if path not in paths or paths[path] in styles:
                return
            shown = paths[path]
            styles[shown] = style.for_file(shown, inherited)
            roles[shown] = styles[shown][0]
            if path in sources:
                for child in sources[path][2].values():
                    select(child, roles[shown])

        children = {child for _, _, links, _ in sources.values() for child in links.values()}
        roots = [path for path in sources if path not in children]
        # Cyclic include graphs still receive one bounded scan.
        for path in roots:
            select(path)
        for path, shown in paths.items():
            if shown not in roles:
                if path in sources:
                    roots.append(path)
                select(path)
        expansions = {}
        documents = {}
        for path in roots:
            macros = {}
            seen = set()

            def collect(source):
                if source in seen:
                    return
                seen.add(source)
                _, definitions, links, _ = sources[source]
                macros.update(definitions)
                for child in links.values():
                    collect(child)

            # shortcut: collect macros per manuscript with forward references; ordered TeX redefinitions need a render.
            collect(path)
            documents[path] = macros
            for member in seen:
                expansions.setdefault(member, macros)
        failures = violations(list(paths.values()), rules=rules, forbidden=args.forbid, root=args.root,
                              sources=sources, expansions=expansions, changed=changed)
        findings = list(identifier_findings(list(paths.values()), style=style, notices=notices,
                                            sources=sources, expansions=expansions, styles=styles))
        repeated = defaultdict(dict)
        for path, macros in documents.items():
            findings.extend(manuscript_findings(tex_passages(path, sources, paths, macros), roles, styles, repeated))
        for path in paths.values():
            if path.suffix.lower() in {".md", ".qmd"} and path.resolve() != style.path.resolve():
                findings.extend(manuscript_findings(markdown_passages(path), roles, styles, repeated))
        for occurrences in repeated.values():
            if len(occurrences) >= 3:
                for passage in occurrences.values():
                    findings.append(passage.finding(
                        "repeated-clause", f"repeated clause in {len(occurrences)} files: {' '.join(passage.text.split())}",
                        WRITING + "fixing-a-review-finding"))
        abstract_roundoff = {(item.path, item.location) for item in findings if item.kind == "abstract-roundoff"}
        dense_paragraphs = defaultdict(list)
        for item in findings:
            if item.kind == "paragraph-density":
                dense_paragraphs[item.path].append((int(item.location), item.end))
        findings = [item for item in dict.fromkeys(findings) if item.on_changed_lines(changed)
                    and not (item.kind == "roundoff" and (item.path, item.location) in abstract_roundoff)
                    and not (item.kind == "sentence-density" and any(
                        start <= item.end <= end
                        for start, end in dense_paragraphs[item.path]))]
    except (OSError, UnicodeError, ValueError) as error:
        print(f"configuration error: {error}")
        return 2

    order = {path: index for index, path in enumerate(paths.values())}
    findings.sort(key=lambda item: (roles[item.path] == "supplement", order[item.path],
                                   int(item.location) if item.location.isdecimal() else 0))
    notices = list(dict.fromkeys(notices))
    advisories = [item for item in findings if item.is_advisory]
    kinds = Counter(item.kind for item in advisories)
    if args.summary_json:
        print(json.dumps({"kinds": kinds, "scan_notices": len(notices)}, sort_keys=True))
        return int(bool(failures))
    for message in [*findings, *notices, *failures]:
        print(message)
    files = Counter(relative_path(item.path, args.root) for item in advisories)
    ranks = Counter(roles[item.path] for item in advisories)
    kind_counts = ", ".join(f"{kind} {count}" for kind, count in sorted(kinds.items())) or "none"
    file_counts = ", ".join(f"{file} {count}" for file, count in files.items()) or "none"
    print(f"Summary: {len(advisories)} {'advisory' if len(advisories) == 1 else 'advisories'} "
          f"(main {ranks['main']}, supplement {ranks['supplement']}), "
          f"{len(failures)} terminology {'violation' if len(failures) == 1 else 'violations'}, "
          f"{len(notices)} scan {'notice' if len(notices) == 1 else 'notices'}. "
          f"Kinds: {kind_counts}. Files: {file_counts}.")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
