from __future__ import annotations

import json
import os
import sys
from dataclasses import replace
from pathlib import Path

from zotero_companion.config import (
    CompanionConfig,
    config_payload,
    discover_zotero_data_dir,
    load_config,
    proposed_config,
    write_config,
)


def test_discovers_custom_zotero_data_directory(tmp_path):
    profile = tmp_path / "profile"
    profile.mkdir()
    data_dir = tmp_path / "Zotero"
    data_dir.mkdir()
    (profile / "prefs.js").write_text(
        f'user_pref("extensions.zotero.dataDir", "{data_dir}");\n',
        encoding="utf-8",
    )

    assert discover_zotero_data_dir(profile) == data_dir.resolve()


def test_config_round_trip_and_private_permissions(tmp_path):
    config = CompanionConfig(
        corpus_root=tmp_path / "corpus",
        zotero_data_dir=tmp_path / "Zotero",
        bibliography_export=tmp_path / "Zotero" / "exports" / "references.bib",
        mathpix_library_consent=True,
        denied_tags=("confidential", "restricted"),
        denied_collections=("Client A",),
    )
    path = tmp_path / "config.toml"

    payload = write_config(config, path)
    loaded = load_config(path)

    assert payload["mode"] == "apply"
    assert loaded == config
    assert loaded.wiki_root.is_dir()
    assert loaded.data_root.is_dir()
    if os.name != "nt":
        assert path.stat().st_mode & 0o077 == 0


def test_config_payload_is_machine_readable(tmp_path):
    config = CompanionConfig(
        corpus_root=tmp_path / "corpus",
        zotero_data_dir=tmp_path / "Zotero",
        bibliography_export=tmp_path / "Zotero" / "exports" / "references.bib",
    )
    payload = config_payload(config, tmp_path / "config.toml", mode="dry-run")
    assert payload["protocol_version"] == "1.0"
    assert payload["data_root"].endswith("corpus/data")
    assert payload["bibliography_export"].endswith("Zotero/exports/references.bib")


def test_proposed_config_defaults_to_no_mathpix_consent(monkeypatch, tmp_path):
    from zotero_companion import config as module

    zotero = tmp_path / "Zotero"
    zotero.mkdir()
    monkeypatch.setattr(module, "discover_zotero_data_dir", lambda: zotero)

    proposed = module.proposed_config(corpus_root=tmp_path / "corpus")
    consented = module.proposed_config(corpus_root=tmp_path / "corpus", mathpix_library_consent=True)

    assert proposed.mathpix_library_consent is False
    assert consented.mathpix_library_consent is True
    assert "confidential" in proposed.denied_tags


def _existing(tmp_path):
    return CompanionConfig(
        corpus_root=(tmp_path / "corpus").resolve(),
        zotero_data_dir=(tmp_path / "Zotero").resolve(),
        bibliography_export=(tmp_path / "Zotero" / "exports" / "references.bib").resolve(),
        mathpix_library_consent=True,
        denied_tags=("confidential", "restricted"),
        denied_collections=("Client A",),
    )


def test_proposed_config_preserves_existing_settings(tmp_path):
    existing = _existing(tmp_path)

    assert proposed_config(existing=existing) == existing
    assert proposed_config(existing=existing, corpus_root=tmp_path / "other") == replace(
        existing, corpus_root=(tmp_path / "other").resolve()
    )
    assert proposed_config(existing=existing, mathpix_library_consent=False) == replace(
        existing, mathpix_library_consent=False
    )


def _init(monkeypatch, capsys, *arguments):
    from zotero_companion.cli import main

    monkeypatch.setattr(sys, "argv", ["cse-zotero", "init", "--json", *arguments])
    assert main() == 0
    return json.loads(capsys.readouterr().out)


def test_init_reconciles_existing_configuration_without_rewriting(monkeypatch, capsys, tmp_path):
    existing = _existing(tmp_path)
    path = tmp_path / "config.toml"
    write_config(existing, path)
    before = path.read_bytes()

    unchanged = _init(monkeypatch, capsys, "--config", str(path), "--apply")
    assert unchanged["mode"] == "unchanged"
    assert unchanged["changes"] == {}
    assert path.read_bytes() == before

    withdrawn = _init(monkeypatch, capsys, "--config", str(path), "--no-mathpix-consent")
    assert withdrawn["mode"] == "dry-run"
    assert withdrawn["changes"] == {"mathpix_library_consent": {"current": True, "proposed": False}}
    assert withdrawn["denied_collections"] == ["Client A"]
    assert path.read_bytes() == before

    applied = _init(monkeypatch, capsys, "--config", str(path), "--no-mathpix-consent", "--apply")
    assert applied["mode"] == "apply"
    assert load_config(path) == replace(existing, mathpix_library_consent=False)
