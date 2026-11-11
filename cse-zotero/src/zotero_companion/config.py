"""User-owned configuration and installation contract for CSE Zotero."""

from __future__ import annotations

import configparser
import hashlib
import json
import os
import re
import stat
import tempfile
import tomllib
from dataclasses import dataclass, replace
from pathlib import Path


PROTOCOL_VERSION = "1.0"
CAPABILITIES = (
    "better-bibtex-library-export-v1",
    "configured-local-corpus-v1",
    "exact-source-locators-v1",
    "mathpix-on-demand-v1",
    "project-libraries-v1",
    "project-views-v1",
    "zotero-linked-companion-v1",
    "zotero-local-api-v1",
)


class ConfigError(RuntimeError):
    """Raised when the user-owned CSE Zotero configuration is invalid."""


def default_config_path() -> Path:
    root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "zotero-companion" / "config.toml"


def default_corpus_root() -> Path:
    root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return root / "zotero-companion" / "corpus"


def discover_zotero_profile() -> Path | None:
    profiles = Path.home() / ".zotero" / "zotero" / "profiles.ini"
    if not profiles.is_file():
        return None
    parser = configparser.ConfigParser()
    parser.read(profiles, encoding="utf-8")
    sections = sorted(
        parser.sections(),
        key=lambda section: parser.getboolean(section, "Default", fallback=False),
        reverse=True,
    )
    for section in sections:
        value = parser.get(section, "Path", fallback="").strip()
        if not value:
            continue
        path = Path(value)
        if parser.getboolean(section, "IsRelative", fallback=True):
            path = profiles.parent / path
        if path.is_dir():
            return path.resolve()
    return None


def discover_zotero_data_dir(profile: Path | None = None) -> Path | None:
    profile = profile or discover_zotero_profile()
    if profile is None:
        candidate = Path.home() / "Zotero"
        return candidate if candidate.is_dir() else None
    prefs = profile / "prefs.js"
    if prefs.is_file():
        match = re.search(
            r'user_pref\("extensions\.zotero\.dataDir",\s*"([^"]+)"\);',
            prefs.read_text(encoding="utf-8", errors="replace"),
        )
        if match:
            return Path(match.group(1)).expanduser().resolve()
    candidate = Path.home() / "Zotero"
    return candidate if candidate.is_dir() else None


@dataclass(frozen=True)
class CompanionConfig:
    corpus_root: Path
    zotero_data_dir: Path
    bibliography_export: Path
    mathpix_library_consent: bool = False
    denied_tags: tuple[str, ...] = ("confidential", "proprietary", "restricted")
    denied_collections: tuple[str, ...] = ()
    vpn_connection: str | None = None

    @property
    def wiki_root(self) -> Path:
        return self.corpus_root / "wiki"

    @property
    def data_root(self) -> Path:
        return self.corpus_root / "data"


def proposed_config(
    *,
    corpus_root: Path | None = None,
    existing: CompanionConfig | None = None,
    mathpix_library_consent: bool | None = None,
) -> CompanionConfig:
    """Propose a configuration from the existing one, or discover a new one.

    Explicit arguments override retained values; everything else is preserved.
    A new configuration never infers Mathpix consent.
    """
    if existing is None:
        data_dir = discover_zotero_data_dir()
        if data_dir is None:
            raise ConfigError("Zotero data directory is unavailable")
        existing = CompanionConfig(
            corpus_root=default_corpus_root(),
            zotero_data_dir=data_dir,
            bibliography_export=data_dir / "exports" / "references.bib",
        )
    return replace(
        existing,
        corpus_root=(corpus_root or existing.corpus_root).expanduser().resolve(),
        mathpix_library_consent=(
            existing.mathpix_library_consent
            if mathpix_library_consent is None
            else mathpix_library_consent
        ),
    )


def _config_from_text(text: str) -> CompanionConfig:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Invalid CSE Zotero configuration: {exc}") from exc
    paths = data.get("paths", {})
    mathpix = data.get("mathpix", {})
    acquisition = data.get("acquisition", {})
    if not isinstance(acquisition, dict):
        raise ConfigError("CSE Zotero configuration [acquisition] must be a table")
    vpn_connection = acquisition.get("vpn_connection")
    if vpn_connection is not None and (not isinstance(vpn_connection, str) or not vpn_connection.strip()):
        raise ConfigError("acquisition.vpn_connection must be a nonempty string")
    if not isinstance(paths, dict):
        raise ConfigError("CSE Zotero configuration [paths] must be a table")
    if not isinstance(mathpix, dict):
        raise ConfigError("CSE Zotero configuration [mathpix] must be a table")
    required = ("corpus_root", "zotero_data_dir", "bibliography_export")
    missing = [name for name in required if not isinstance(paths.get(name), str) or not paths[name].strip()]
    if missing:
        raise ConfigError(f"CSE Zotero configuration is missing paths: {', '.join(missing)}")
    consent = mathpix.get("library_consent", False)
    if not isinstance(consent, bool):
        raise ConfigError("CSE Zotero configuration mathpix.library_consent must be a boolean")
    denied_tags = mathpix.get("denied_tags", [])
    denied_collections = mathpix.get("denied_collections", [])
    if not isinstance(denied_tags, list) or not all(isinstance(value, str) for value in denied_tags):
        raise ConfigError("CSE Zotero configuration mathpix.denied_tags must be an array of strings")
    if not isinstance(denied_collections, list) or not all(
        isinstance(value, str) for value in denied_collections
    ):
        raise ConfigError("CSE Zotero configuration mathpix.denied_collections must be an array of strings")
    return CompanionConfig(
        corpus_root=Path(paths["corpus_root"]).expanduser().resolve(),
        zotero_data_dir=Path(paths["zotero_data_dir"]).expanduser().resolve(),
        bibliography_export=Path(paths["bibliography_export"]).expanduser().resolve(),
        vpn_connection=vpn_connection,
        mathpix_library_consent=consent,
        denied_tags=tuple(denied_tags),
        denied_collections=tuple(denied_collections),
    )


def _read_config_snapshot(path: Path) -> tuple[CompanionConfig, bytes]:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ConfigError(f"CSE Zotero configuration is not UTF-8: {path}") from exc
    return _config_from_text(text), raw


def _triple_string_end(line: str, start: int, delimiter: str) -> int:
    while (position := line.find(delimiter, start)) >= 0:
        if delimiter == '"""':
            backslashes = 0
            index = position - 1
            while index >= 0 and line[index] == "\\":
                backslashes += 1
                index -= 1
            if backslashes % 2:
                start = position + len(delimiter)
                continue
        return position
    return -1


def _toml_structure_line(
    line: str, multiline: str | None
) -> tuple[str | None, str | None]:
    line = line.rstrip("\r\n")
    index = 0
    inside_multiline = multiline is not None
    while index < len(line):
        if multiline is not None:
            position = _triple_string_end(line, index, multiline)
            if position < 0:
                return None, multiline
            index = position + len(multiline)
            multiline = None
            continue
        if line[index] == "#":
            return (None if inside_multiline else line[:index]), None
        delimiter = line[index : index + 3]
        if delimiter in {'"""', "'''"}:
            inside_multiline = True
            position = _triple_string_end(line, index + 3, delimiter)
            if position < 0:
                return None, delimiter
            index = position + 3
            continue
        if line[index] == '"':
            index += 1
            while index < len(line):
                if line[index] == "\\":
                    index += 2
                elif line[index] == '"':
                    index += 1
                    break
                else:
                    index += 1
            continue
        if line[index] == "'":
            closing = line.find("'", index + 1)
            index = len(line) if closing < 0 else closing + 1
            continue
        index += 1
    return (None if inside_multiline else line), multiline


def _config_table_headers(text: str) -> tuple[list[tuple[str | None, int]], list[str | None]]:
    lines = text.splitlines(keepends=True)
    headers: list[tuple[str | None, int]] = []
    line_tables: list[str | None] = []
    table: str | None = None
    multiline: str | None = None
    array_depth = 0
    for index, line in enumerate(lines):
        visible, multiline = _toml_structure_line(line, multiline)
        if visible is None:
            line_tables.append(None)
            continue
        stripped = visible.strip()
        unquoted = re.sub(r'"(?:\\.|[^"\\])*"|\'[^\']*\'', '', stripped)
        if array_depth:
            array_depth += unquoted.count("[") - unquoted.count("]")
            line_tables.append(None)
            continue
        match = re.fullmatch(r"\[([A-Za-z0-9_-]+)\]", stripped)
        if match:
            table = match.group(1)
            headers.append((table, index))
        elif stripped.startswith("["):
            table = None
            headers.append((None, index))
        elif "=" in unquoted:
            array_depth = unquoted.count("[") - unquoted.count("]")
        line_tables.append(table)
    return headers, line_tables


def _set_config_value(
    text: str,
    section: str,
    key: str,
    value: str,
    *,
    value_kind: str,
    parsed: dict[str, object],
) -> str:
    lines = text.splitlines(keepends=True)
    headers, line_tables = _config_table_headers(text)
    section_headers = [index for name, index in headers if name == section]
    if len(section_headers) > 1:
        raise ConfigError(f"Cannot safely edit repeated [{section}] tables")
    if not section_headers:
        if section in parsed:
            raise ConfigError(f"Cannot safely edit non-table {section} configuration")
        if section != "mathpix":
            raise ConfigError(f"Cannot safely edit missing [{section}] table")
        newline = "\r\n" if "\r\n" in text else "\n"
        if text and not text.endswith(("\n", "\r")):
            text += newline
        if text and not text.endswith(newline * 2):
            text += newline
        return f"{text}[{section}]{newline}{key} = {value}{newline}"

    start = section_headers[0] + 1
    end = min((index for _, index in headers if index > section_headers[0]), default=len(lines))
    assignments = [
        index
        for index in range(start, end)
        if line_tables[index] == section
        and re.match(rf"^[ \t]*{re.escape(key)}[ \t]*=", lines[index])
    ]
    if len(assignments) > 1:
        raise ConfigError(f"Cannot safely edit repeated {section}.{key}")
    if assignments:
        index = assignments[0]
        value_pattern = r'"(?:\\.|[^"\\])*"' if value_kind == "string" else r"(?:true|false)"
        pattern = (
            rf"^([ \t]*{re.escape(key)}[ \t]*=[ \t]*)"
            + f"({value_pattern})"
            + r"([ \t]*(?:#.*)?)(\r\n|\r|\n)?$"
        )
        match = re.fullmatch(pattern, lines[index])
        if not match:
            raise ConfigError(f"Cannot safely edit unsupported {section}.{key} syntax")
        lines[index] = f"{match.group(1)}{value}{match.group(3)}{match.group(4) or ''}"
    else:
        values = parsed.get(section, {})
        if not isinstance(values, dict) or key in values:
            raise ConfigError(f"Cannot safely locate {section}.{key}")
        newline = "\r\n" if "\r\n" in text else "\n"
        if end and not lines[end - 1].endswith(("\n", "\r")):
            lines[end - 1] += newline
        lines.insert(end, f"{key} = {value}{newline}")
    return "".join(lines)


def _reconcile_config_text(
    text: str,
    current: CompanionConfig,
    proposed: CompanionConfig,
) -> str:
    try:
        parsed = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Invalid CSE Zotero configuration: {exc}") from exc
    if current.corpus_root != proposed.corpus_root:
        text = _set_config_value(
            text,
            "paths",
            "corpus_root",
            json.dumps(str(proposed.corpus_root)),
            value_kind="string",
            parsed=parsed,
        )
    if current.mathpix_library_consent != proposed.mathpix_library_consent:
        text = _set_config_value(
            text,
            "mathpix",
            "library_consent",
            str(proposed.mathpix_library_consent).lower(),
            value_kind="boolean",
            parsed=parsed,
        )
    if _config_from_text(text) != proposed:
        raise ConfigError("CSE Zotero configuration could not be reconciled without losing settings")
    return text


def load_config(path: Path | None = None, *, allow_proposed: bool = False) -> CompanionConfig:
    path = Path(path or default_config_path())
    if not path.is_file():
        if allow_proposed:
            return proposed_config()
        raise ConfigError(f"CSE Zotero configuration is missing: {path}; review `cse-zotero init --json`, then apply explicit corpus and Mathpix choices")
    return _read_config_snapshot(path)[0]


def config_payload(config: CompanionConfig, path: Path, *, mode: str) -> dict[str, object]:
    return {
        "ok": True,
        "mode": mode,
        "protocol_version": PROTOCOL_VERSION,
        "config_path": str(path),
        "corpus_root": str(config.corpus_root),
        "wiki_root": str(config.wiki_root),
        "data_root": str(config.data_root),
        "zotero_data_dir": str(config.zotero_data_dir),
        "bibliography_export": str(config.bibliography_export),
        "vpn_connection": config.vpn_connection,
        "mathpix_library_consent": config.mathpix_library_consent,
        "denied_tags": list(config.denied_tags),
        "denied_collections": list(config.denied_collections),
    }


def _atomic_write_config(
    path: Path, text: str, *, expected_sha256: str | None
) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(text.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        if os.name != "nt":
            temporary.chmod(stat.S_IRUSR | stat.S_IWUSR)
        if expected_sha256 is None:
            os.link(temporary, path)
        else:
            if path.is_symlink() or not path.is_file():
                raise ConfigError("CSE Zotero configuration changed since preview; rerun init --json")
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha256:
                raise ConfigError("CSE Zotero configuration changed since preview; rerun init --json")
            os.replace(temporary, path)
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def write_config(
    config: CompanionConfig,
    path: Path | None = None,
    *,
    expected_sha256: str | None = None,
) -> dict[str, object]:
    path = Path(path or default_config_path())
    exists = os.path.lexists(path)
    if path.is_symlink():
        raise ConfigError(f"Cannot safely update symlink configuration: {path}")
    if exists:
        if expected_sha256 is None:
            raise ConfigError("Updating an existing configuration requires its init dry-run preview token")
        if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
            raise ConfigError("Invalid init preview token; expected a lowercase SHA-256 value")
        current, raw = _read_config_snapshot(path)
        if hashlib.sha256(raw).hexdigest() != expected_sha256:
            raise ConfigError("CSE Zotero configuration changed since preview; rerun init --json")
        text = _reconcile_config_text(raw.decode("utf-8"), current, config)
    else:
        if expected_sha256 is not None:
            raise ConfigError("CSE Zotero configuration disappeared since preview")
        text = (
            "version = 1\n\n"
            "[paths]\n"
            f"corpus_root = {json.dumps(str(config.corpus_root))}\n"
            f"zotero_data_dir = {json.dumps(str(config.zotero_data_dir))}\n"
            f"bibliography_export = {json.dumps(str(config.bibliography_export))}\n\n"
            "[mathpix]\n"
            f"library_consent = {str(config.mathpix_library_consent).lower()}\n"
            f"denied_tags = {json.dumps(list(config.denied_tags))}\n"
            f"denied_collections = {json.dumps(list(config.denied_collections))}\n"
        )
    if not exists and config.vpn_connection is not None:
        text += f"\n[acquisition]\nvpn_connection = {json.dumps(config.vpn_connection)}\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    config.corpus_root.mkdir(parents=True, exist_ok=True)
    config.wiki_root.mkdir(parents=True, exist_ok=True)
    config.data_root.mkdir(parents=True, exist_ok=True)
    _atomic_write_config(path, text, expected_sha256=expected_sha256)
    return config_payload(config, path, mode="apply")
