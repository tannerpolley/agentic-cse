#!/usr/bin/env python3
"""Reject configured words from scientific prose."""

from __future__ import annotations

import argparse
import fnmatch
from pathlib import Path
import re
import tomllib

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


def split_table_row(line: str) -> list[str]:
    return [cell.strip().strip(chr(96)) for cell in line.strip().strip("|").split("|")]


def load_context_rules(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    for start, line in enumerate(lines):
        if split_table_row(line) == list(FIELDS):
            break
    else:
        raise ValueError(f"{path}: terminology table with {', '.join(FIELDS)} not found")

    rules: list[dict] = []
    for number, line in enumerate(lines[start + 2 :], start + 3):
        if not line.lstrip().startswith("|"):
            break
        cells = split_table_row(line)
        if len(cells) != len(FIELDS):
            raise ValueError(f"{path}:{number}: expected {len(FIELDS)} terminology fields")
        entry = dict(zip(FIELDS, cells))
        entry["Scope"] = [value.strip() for value in entry["Scope"].split(";") if value.strip()]
        entry["Exceptions"] = [
            value.strip() for value in entry["Exceptions"].split(";") if value.strip()
        ]
        rules.append(validate_rule(entry, f"{path}:{number}"))
    return rules


def scopes_overlap(left: list[str], right: list[str]) -> bool:
    def prefix(pattern: str) -> str:
        return re.split(r"[*?[]", pattern, maxsplit=1)[0]

    for first in left:
        for second in right:
            if first == second:
                return True
            first_prefix, second_prefix = prefix(first), prefix(second)
            if first_prefix.startswith(second_prefix) or second_prefix.startswith(first_prefix):
                return True
    return False


def reject_conflicts(rules: list[dict]) -> None:
    for index, first in enumerate(rules):
        for second in rules[index + 1 :]:
            if (
                first["Avoid"].casefold() == second["Avoid"].casefold()
                and scopes_overlap(first["Scope"], second["Scope"])
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


def sourced_terms(context: Path | None, relative: str) -> list[str]:
    if context is None:
        return []
    result = []
    in_glossary = False
    for line in context.read_text(encoding="utf-8").splitlines():
        cells = split_table_row(line)
        if cells == ["Term", "Meaning", "Source", "Scope"]:
            in_glossary = True
            continue
        if not in_glossary:
            continue
        if not line.lstrip().startswith("|"):
            in_glossary = False
            continue
        if len(cells) != 4:
            continue
        term, meaning, source, scope = cells
        if not meaning or not source or source.casefold().startswith("sourceless") or source.casefold() in {"none", "unknown", "-", "n/a"} or set(source) <= {"-", ":"}:
            continue
        if any(fnmatch.fnmatchcase(relative, pattern.strip()) for pattern in scope.split(";")):
            result.append(term)
    return result


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


def violations(paths: list[Path], *, context: Path | None = None,
               rules: list[dict] | None = None, forbidden: list[str] = (),
               root: Path | None = None) -> list[str]:
    root = root or Path.cwd()
    global_rules = banned_rules() + [
        {"Avoid": term, "Prefer": "precise scientific language", "qualifier": "", "source": "--forbid"}
        for term in forbidden
    ]
    failures = []
    for path in text_files(paths):
        if path.resolve() == BANNED.resolve():
            continue
        relative = relative_path(path, root)
        exceptions = sourced_terms(context, relative)
        active = [r for r in (rules or []) if any(fnmatch.fnmatchcase(relative, s) for s in r["Scope"])]
        text = path.read_text(encoding="utf-8")
        original_lines = text.splitlines()
        lines = dict(prose_lines(text))
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--forbid", action="append", default=[])
    parser.add_argument("--config", type=Path)
    parser.add_argument("--context", type=Path)
    args = parser.parse_args()

    try:
        rules = []
        if args.config:
            rules.extend(load_personal_rules(args.config))
        if args.context:
            rules.extend(load_context_rules(args.context))
        reject_conflicts(rules)
    except (OSError, tomllib.TOMLDecodeError, ValueError) as error:
        print(f"configuration error: {error}")
        return 2

    root = args.context.resolve().parents[2] if args.context else Path.cwd()
    try:
        failures = violations(args.paths, context=args.context, rules=rules,
                              forbidden=args.forbid, root=root)
    except (OSError, UnicodeError, ValueError) as error:
        print(f"configuration error: {error}")
        return 2

    if failures:
        print("\n".join(failures))
        return 1
    print(f"Prose check passed for {len(banned_rules())} plugin-wide and {len(rules)} scoped rule(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
