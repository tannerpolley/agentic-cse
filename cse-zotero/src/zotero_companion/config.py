"""User-owned configuration and installation contract for Zotero Companion."""

from __future__ import annotations

import configparser
import json
import os
import re
import stat
import tomllib
from dataclasses import dataclass
from pathlib import Path


PROTOCOL_VERSION = "1.0"
CAPABILITIES = (
    "better-bibtex-library-export-v1",
    "configured-local-corpus-v1",
    "exact-source-locators-v1",
    "mathpix-on-demand-v1",
    "project-views-v1",
    "zotero-linked-companion-v1",
    "zotero-local-api-v1",
)


class ConfigError(RuntimeError):
    """Raised when the user-owned Companion configuration is invalid."""


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

    @property
    def wiki_root(self) -> Path:
        return self.corpus_root / "wiki"

    @property
    def data_root(self) -> Path:
        return self.corpus_root / "data"


def proposed_config(*, corpus_root: Path | None = None) -> CompanionConfig:
    data_dir = discover_zotero_data_dir()
    if data_dir is None:
        raise ConfigError("Zotero data directory is unavailable")
    return CompanionConfig(
        corpus_root=(corpus_root or default_corpus_root()).expanduser().resolve(),
        zotero_data_dir=data_dir,
        bibliography_export=data_dir / "exports" / "references.bib",
        mathpix_library_consent=True,
    )


def load_config(path: Path | None = None, *, allow_proposed: bool = False) -> CompanionConfig:
    path = Path(path or default_config_path())
    if not path.is_file():
        if allow_proposed:
            return proposed_config()
        raise ConfigError(f"Companion configuration is missing: {path}; run `zotero-companion init --apply`")
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    paths = data.get("paths", {})
    mathpix = data.get("mathpix", {})
    required = ("corpus_root", "zotero_data_dir", "bibliography_export")
    missing = [name for name in required if not str(paths.get(name, "")).strip()]
    if missing:
        raise ConfigError(f"Companion configuration is missing paths: {', '.join(missing)}")
    return CompanionConfig(
        corpus_root=Path(paths["corpus_root"]).expanduser().resolve(),
        zotero_data_dir=Path(paths["zotero_data_dir"]).expanduser().resolve(),
        bibliography_export=Path(paths["bibliography_export"]).expanduser().resolve(),
        mathpix_library_consent=bool(mathpix.get("library_consent", False)),
        denied_tags=tuple(str(value) for value in mathpix.get("denied_tags", [])),
        denied_collections=tuple(str(value) for value in mathpix.get("denied_collections", [])),
    )


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
        "mathpix_library_consent": config.mathpix_library_consent,
        "denied_tags": list(config.denied_tags),
        "denied_collections": list(config.denied_collections),
    }


def write_config(config: CompanionConfig, path: Path | None = None) -> dict[str, object]:
    path = Path(path or default_config_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    config.corpus_root.mkdir(parents=True, exist_ok=True)
    config.wiki_root.mkdir(parents=True, exist_ok=True)
    config.data_root.mkdir(parents=True, exist_ok=True)
    text = (
        "version = 1\n\n"
        "[paths]\n"
        f'corpus_root = "{config.corpus_root}"\n'
        f'zotero_data_dir = "{config.zotero_data_dir}"\n'
        f'bibliography_export = "{config.bibliography_export}"\n\n'
        "[mathpix]\n"
        f"library_consent = {str(config.mathpix_library_consent).lower()}\n"
        f"denied_tags = {json.dumps(list(config.denied_tags))}\n"
        f"denied_collections = {json.dumps(list(config.denied_collections))}\n"
    )
    path.write_text(text, encoding="utf-8")
    if os.name != "nt":
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return config_payload(config, path, mode="apply")
