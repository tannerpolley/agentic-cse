from __future__ import annotations

import os
from pathlib import Path

from zotero_companion.config import (
    CompanionConfig,
    config_payload,
    discover_zotero_data_dir,
    load_config,
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


def test_proposed_config_records_library_wide_mathpix_consent(monkeypatch, tmp_path):
    from zotero_companion import config as module

    zotero = tmp_path / "Zotero"
    zotero.mkdir()
    monkeypatch.setattr(module, "discover_zotero_data_dir", lambda: zotero)

    proposed = module.proposed_config(corpus_root=tmp_path / "corpus")

    assert proposed.mathpix_library_consent is True
    assert "confidential" in proposed.denied_tags
