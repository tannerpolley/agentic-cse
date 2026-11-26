#!/usr/bin/env python3
"""Reject configured words from scientific prose."""

from __future__ import annotations

import ast
import zipfile
from xml.etree import ElementTree as ET
import argparse
import fnmatch
from pathlib import Path
import re
import tomllib

from cse_hook_common import CONTEXT, glossary_paths, has_source, markdown_tables, read_glossaries, split_scope

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
               forbidden: list[str] = (), root: Path | None = None) -> list[str]:
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
        lines = dict(prose_lines(text))
        if path.resolve() == scientific_context.resolve():
            for table in markdown_tables(text):
                if table["section"] == "Prose avoid rules":
                    for row in table["rows"]:
                        lines.pop(row["index"] + 1, None)
        for number, line in lines.items():
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


def hide(pattern, text, flags=0):
    return re.sub(pattern, lambda m: re.sub(r"[^\n]", " ", m[0]), text, flags=flags)


def visible_lines(text, suffix, math=False):
    """Bounded source extraction; masking retains source line numbers.

    math=True keeps math and quantity-macro arguments for the roundoff advisory."""
    text = hide(r"<!--.*?-->", text, re.S) if suffix != ".tex" else text
    if not math:
        text = hide(r"(?s)\$\$.*?\$\$|(?<!\\)\$[^$]*\$|\\\(.*?\\\)|\\\[.*?\\\]", text)
    fence = environment = None
    metadata = False
    caption = False
    for number, line in enumerate(text.splitlines(), 1):
        if suffix == ".tex":
            line = hide(r"(?<!\\)%.*", line)
            prefix = ""
            if environment:
                end = re.search(r"\\end\{" + re.escape(environment) + r"\}", line)
                if not end:
                    continue
                line, environment = line[end.end():], None
            begin = re.search(r"\\begin\{(verbatim\*?|lstlisting|minted|equation\*?|align\*?|gather\*?|displaymath|math)\}", line)
            if begin:
                prefix, environment = line[:begin.start()], begin[1]
                end = re.search(r"\\end\{" + re.escape(environment) + r"\}", line[begin.end():])
                line = prefix + (line[begin.end() + end.end():] if end else "")
                if end:
                    environment = None
            # shortcut: single-line arguments only; inspect assembled output for macros or multiline arguments.
            line = re.sub(r"\\[A-Za-z]*cite[A-Za-z]*\*?(?:\[([^]]*)\])?\{[^}]*\}", lambda m: m[1] or "", line)
            line = hide(r"\\(?:label|(?:eq|auto|page|[cC])?ref|[A-Za-z]*cite[A-Za-z]*|include(?:graphics)?|input|bibliography|usepackage|(?:re)?newcommand|providecommand)\*?(?:\[[^]]*\])*\{[^}]*\}(?:\[[^]]*\])?(?:\{[^}]*\})?", line)
            quantities = "" if math else "|si|SI|unit|num|qty|numrange|qtyrange|tablenum|ang"
            line = hide(r"\\(?:ce|ch" + quantities + r")(?:\[[^]]*\])*\{[^}]*\}(?:\{[^}]*\}){0,2}", line)
            line = hide(r"\\href\{[^}]*\}", line)
            line = hide(r"\\[A-Za-z]+\*?\{", line).replace("}", " ")
            line = line.replace(r"\#", "#").replace(r"\_", "_")
        else:
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


def scientific_approvals(root, path, warnings):
    style = root / "docs/scientific/writing/STYLE.md"
    approved, sources = set(), []
    if not style.is_file():
        return approved
    relative = relative_path(path, root)
    def matches(patterns):
        return any(fnmatch.fnmatchcase(relative, p) for p in patterns)
    def scopes(value):
        values = [p.strip().strip("`") for p in value.split(";") if p.strip()]
        if any(p.startswith("/") or ".." in Path(p).parts for p in values):
            warnings.append(f"{style}: incomplete scan: invalid approval path")
            return []
        return values
    for number, line in enumerate(style.read_text(encoding="utf-8").splitlines(), 1):
        if line.startswith("## "):
            sources = []
        if line.startswith("Sources:"):
            sources = scopes(line.partition(":")[2])
        if not matches(sources):
            continue
        if "Approved scientific labels:" in line:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) != 3 or not cells[1].startswith("Approved scientific labels:") or not cells[2] or not re.search(r"`[^`]+`", cells[1]):
                warnings.append(f"{style}:{number}: incomplete scan: malformed scientific-label approval")
            elif matches(scopes(cells[0])):
                approved.update(re.findall(r"`([^`]+)`", cells[1]))
        elif re.search(r"(?i)\b(pointer|external|brief)\b", line):
            warnings.append(f"{style}:{number}: incomplete scan: external editorial approval requires inspection")
    return approved


def magnitude(match):
    if match["d"]:
        return float(match["d"])
    if match["em"]:
        return float(match["em"]) * 10 ** int(match["ee"])
    exponent = match["e"] or match["u"].translate(SUPERSCRIPT)
    return float(match["m"] or 1) * 10 ** int(re.sub(r"\s", "", exponent).replace("−", "-"))


def numerical_warnings(path, lines, numeric_lines):
    """Advisories for code-style numbers and roundoff-scale detail; never failures."""
    for location, line in lines:
        if line is None:
            continue
        line = hide(r"(?:[A-Za-z][\w+.-]*://|www\.)\S+|\b10\.\d{4,9}/[^\s}]+|`[^`]*`", line)
        for match in PRINT_FORM.finditer(line):
            yield f"{path}:{location}: warning: print form {match[0]!r}: write the printed number (scientific-writing.md#equations-quantities-and-units)"
    for location, line in numeric_lines:
        if line is None:
            continue
        line = hide(r"(?:[A-Za-z][\w+.-]*://|www\.)\S+|\b10\.\d{4,9}/[^\s}]+", line)
        for match in MAGNITUDE.finditer(line):
            if 0 < magnitude(match) <= 1e-6 and ROUNDOFF_CONTEXT.search(line[max(0, match.start() - 80):match.end() + 80]):
                value = re.sub(r"\{\s*(?=[-−])", "", match[0].strip())
                yield (f"{path}:{location}: warning: roundoff-scale numerical detail '{value}' in a deliverable: "
                       "does it change a reported value, a conclusion or a decision? If not, move it to the record "
                       "(numerical-testing.md#fitness-for-purpose)")
                break


def identifier_warnings(paths, *, root=None):
    root = root or Path.cwd()
    warnings = []
    files = (item for path in paths for item in (path.rglob("*") if path.is_dir() else [path]))
    for path in files:
        if not path.is_file() or path.suffix.lower() not in IDENTIFIER_SUFFIXES or path.resolve() == (root / "docs/scientific/writing/STYLE.md").resolve():
            continue
        try:
            approved = scientific_approvals(root, path, warnings)
            suffix = path.suffix.lower()
            if suffix == ".pptx":
                lines = numeric_lines = list(slide_text(path))
            elif suffix == ".py":
                lines = numeric_lines = list(figure_text(path))
            else:
                text = path.read_text(encoding="utf-8")
                lines = list(visible_lines(text, suffix))
                numeric_lines = visible_lines(text, suffix, math=True)
            for location, line in lines:
                if line is None:
                    warnings.append(f"{path}:{location}: incomplete scan: dynamic figure label; inspect assembled figure")
                    continue
                line = hide(r"(?:[A-Za-z][\w+.-]*://|www\.)\S+|\b10\.\d{4,9}/[^\s}]+", line)
                for category, pattern in IDENTIFIERS.items():
                    for match in re.finditer(pattern, line):
                        value = match[0]
                        if category == "run/fit label" and value in approved:
                            continue
                        if category == "hash" and re.fullmatch(r"[0-9a-fA-F]+", value) and not (re.search(r"\d", value) and re.search(r"[a-f]", value, re.I)):
                            continue
                        if category == "repository path":
                            known_start = value.startswith((
                                "./", "../", "/", "analyses/", "docs/", "scripts/", "src/",
                                "tests/", "results/", "data/", "plugin/"))
                            known_suffix = Path(value).suffix in {
                                ".py", ".tex", ".qmd", ".md", ".csv", ".tsv", ".json", ".yaml",
                                ".yml", ".toml", ".parquet", ".npz", ".npy", ".pdf", ".png",
                                ".svg", ".pptx", ".whl"}
                            if not (known_start or known_suffix):
                                continue
                        warnings.append(f"{path}:{location}: warning: {category} {value!r} (scientific-writing.md#reader-facing-identifiers)")
            warnings.extend(numerical_warnings(path, lines, numeric_lines))
        except (OSError, UnicodeError, ValueError, SyntaxError, zipfile.BadZipFile, ET.ParseError, RuntimeError) as error:
            warnings.append(f"{path}: incomplete scan: {error}")
    return warnings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--forbid", action="append", default=[])
    parser.add_argument("--config", type=Path)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="project root containing GLOSSARY.md or GLOSSARY-MAP.md")
    args = parser.parse_args()

    try:
        rules = []
        if args.config:
            rules.extend(load_personal_rules(args.config))
    except (OSError, tomllib.TOMLDecodeError, ValueError) as error:
        print(f"configuration error: {error}")
        return 2

    try:
        failures = violations(args.paths, rules=rules, forbidden=args.forbid, root=args.root)
    except (OSError, UnicodeError, ValueError) as error:
        print(f"configuration error: {error}")
        return 2

    warnings = identifier_warnings(args.paths, root=args.root)
    if warnings:
        print("\n".join(warnings))
    if failures:
        print("\n".join(failures))
        return 1
    print("Advisories require inspection; terminology checks passed." if warnings else "Prose check passed for plugin-wide and scoped rules.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
