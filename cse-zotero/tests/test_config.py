from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from zotero_companion.config import (
    CompanionConfig,
    ConfigError,
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

    applied = _init(
        monkeypatch,
        capsys,
        "--config",
        str(path),
        "--no-mathpix-consent",
        "--apply",
        "--preview-sha256",
        withdrawn["preview_sha256"],
    )
    assert applied["mode"] == "apply"
    assert load_config(path) == replace(existing, mathpix_library_consent=False)


def test_fresh_init_requires_explicit_corpus_and_consent(monkeypatch, capsys, tmp_path):
    from zotero_companion import config as module

    zotero = tmp_path / "Zotero"
    zotero.mkdir()
    monkeypatch.setattr(module, "discover_zotero_data_dir", lambda: zotero)
    path = tmp_path / "config.toml"
    corpus = tmp_path / "corpus"

    preview = _init(monkeypatch, capsys, "--config", str(path))
    assert preview["mode"] == "dry-run"
    for choices in ((), ("--corpus-root", str(corpus)), ("--no-mathpix-consent",)):
        with pytest.raises(SystemExit) as failure:
            _init(monkeypatch, capsys, "--config", str(path), *choices, "--apply")
        assert failure.value.code == 2
        assert not path.exists()

    applied = _init(
        monkeypatch, capsys, "--config", str(path),
        "--corpus-root", str(corpus), "--no-mathpix-consent", "--apply",
    )
    assert applied["mode"] == "apply"
    assert load_config(path).corpus_root == corpus.resolve()
    assert load_config(path).mathpix_library_consent is False


def test_init_update_preserves_unknown_toml_settings_and_comments(monkeypatch, capsys, tmp_path):
    existing = _existing(tmp_path)
    path = tmp_path / "config.toml"
    write_config(existing, path)
    original = path.read_text(encoding="utf-8")
    original = original.replace(
        "[paths]\n",
        "[paths]\n# keep this comment\nproject_alias = \"MEA\" # user setting\n",
    )
    original = original.replace(
        "[mathpix]\n",
        "[mathpix]\n# keep consent note\npolicy_extension = \"manual-review\"\n",
    )
    original += "\n[external]\nowner = \"researcher\"\n"
    path.write_text(original, encoding="utf-8")
    before = path.read_bytes()
    corpus = str(tmp_path / "new-corpus")

    preview = _init(monkeypatch, capsys, "--config", str(path), "--corpus-root", corpus)
    token = preview["preview_sha256"]
    assert token == hashlib.sha256(before).hexdigest()
    assert path.read_bytes() == before

    _init(
        monkeypatch,
        capsys,
        "--config",
        str(path),
        "--corpus-root",
        corpus,
        "--apply",
        "--preview-sha256",
        token,
    )

    updated = path.read_text(encoding="utf-8")
    assert "# keep this comment\nproject_alias = \"MEA\" # user setting" in updated
    assert "# keep consent note\npolicy_extension = \"manual-review\"" in updated
    assert "[external]\nowner = \"researcher\"" in updated
    assert load_config(path).corpus_root == (tmp_path / "new-corpus").resolve()


def test_init_preserves_multiline_array_in_unknown_setting(monkeypatch, capsys, tmp_path):
    existing = _existing(tmp_path)
    path = tmp_path / "config.toml"
    write_config(existing, path)
    original = path.read_text(encoding="utf-8").replace(
        "[paths]\n",
        "[paths]\ncustom_matrix = [\n  [1, 2],\n  [3, 4],\n]\n",
    )
    path.write_text(original, encoding="utf-8")
    corpus = str(tmp_path / "new-corpus")
    preview = _init(monkeypatch, capsys, "--config", str(path), "--corpus-root", corpus)
    _init(
        monkeypatch, capsys, "--config", str(path), "--corpus-root", corpus,
        "--preview-sha256", preview["preview_sha256"], "--apply",
    )
    assert "custom_matrix = [\n  [1, 2],\n  [3, 4],\n]" in path.read_text(encoding="utf-8")
    assert load_config(path).corpus_root == Path(corpus).resolve()


def test_init_apply_requires_the_matching_preview_for_existing_config(monkeypatch, capsys, tmp_path):
    existing = _existing(tmp_path)
    path = tmp_path / "config.toml"
    write_config(existing, path)
    original = path.read_bytes()
    corpus = tmp_path / "new-corpus"

    preview = _init(monkeypatch, capsys, "--config", str(path), "--corpus-root", str(corpus))
    token = preview["preview_sha256"]
    assert token == hashlib.sha256(original).hexdigest()
    assert path.read_bytes() == original

    with pytest.raises(SystemExit) as missing_token:
        _init(monkeypatch, capsys, "--config", str(path), "--corpus-root", str(corpus), "--apply")
    assert missing_token.value.code == 2
    assert path.read_bytes() == original

    changed = original + b"\n# changed after preview\n"
    path.write_bytes(changed)
    with pytest.raises(SystemExit) as stale_token:
        _init(
            monkeypatch,
            capsys,
            "--config",
            str(path),
            "--corpus-root",
            str(corpus),
            "--apply",
            "--preview-sha256",
            token,
        )
    assert stale_token.value.code == 2
    assert path.read_bytes() == changed


def test_init_interrupted_replace_keeps_existing_config_private(monkeypatch, capsys, tmp_path):
    from zotero_companion import config as config_module

    existing = _existing(tmp_path)
    path = tmp_path / "config.toml"
    write_config(existing, path)
    original = path.read_bytes()
    permissions = path.stat().st_mode & 0o777
    corpus = str(tmp_path / "new-corpus")
    preview = _init(monkeypatch, capsys, "--config", str(path), "--corpus-root", corpus)

    def interrupted_replace(*_args):
        raise OSError("simulated replacement interruption")

    monkeypatch.setattr(config_module.os, "replace", interrupted_replace)
    with pytest.raises(SystemExit) as failure:
        _init(
            monkeypatch,
            capsys,
            "--config",
            str(path),
            "--corpus-root",
            corpus,
            "--apply",
            "--preview-sha256",
            preview["preview_sha256"],
        )

    assert failure.value.code == 2
    assert path.read_bytes() == original
    assert path.stat().st_mode & 0o777 == permissions == 0o600
    assert list(tmp_path.glob(".config.toml.*")) == []



def test_init_fresh_apply_never_clobbers_a_config_created_after_check(monkeypatch, tmp_path):
    from zotero_companion import config as config_module

    config = _existing(tmp_path)
    path = tmp_path / "config.toml"
    competitor = b"user-created config\n"
    real_link = config_module.os.link

    def race_create(source, destination):
        Path(destination).write_bytes(competitor)
        return real_link(source, destination)

    monkeypatch.setattr(config_module.os, "link", race_create)
    with pytest.raises(FileExistsError):
        write_config(config, path)

    assert path.read_bytes() == competitor
    assert list(tmp_path.glob(".config.toml.*")) == []


def test_init_refuses_to_edit_unsupported_toml_structure(tmp_path):
    config = _existing(tmp_path)
    path = tmp_path / "config.toml"
    path.write_text(
        "version = 1\n"
        f"paths.corpus_root = {json.dumps(str(tmp_path / 'corpus'))}\n"
        f"paths.zotero_data_dir = {json.dumps(str(tmp_path / 'Zotero'))}\n"
        f"paths.bibliography_export = {json.dumps(str(tmp_path / 'Zotero/exports/references.bib'))}\n"
        "\n[mathpix]\nlibrary_consent = true\n"
        'denied_tags = ["confidential", "restricted"]\n'
        'denied_collections = ["Client A"]\n',
        encoding="utf-8",
    )
    original = path.read_bytes()

    with pytest.raises(ConfigError, match="Cannot safely edit non-table paths"):
        write_config(
            replace(config, corpus_root=tmp_path / "new-corpus"),
            path,
            expected_sha256=hashlib.sha256(original).hexdigest(),
        )

    assert path.read_bytes() == original


@pytest.mark.parametrize('email', [None, 'contact@example.org'])
@pytest.mark.parametrize('vpn', [None, 'Institution VPN'])
def test_acquisition_settings_survive_init_path_and_consent_changes(tmp_path, email, vpn):
    config = replace(_existing(tmp_path), vpn_connection=vpn, contact_email=email)
    path = tmp_path / 'config.toml'
    write_config(config, path)
    retained = load_config(path)
    assert retained.vpn_connection == vpn
    assert retained.contact_email == email
    assert config_payload(retained, path, mode='dry-run')['contact_email'] == email
    proposed = proposed_config(existing=retained, corpus_root=tmp_path / 'new-corpus', mathpix_library_consent=False)
    write_config(proposed, path, expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    assert load_config(path) == proposed
    assert load_config(path).vpn_connection == vpn
    assert load_config(path).contact_email == email


@pytest.mark.parametrize('value', ['""', '"   "', '42', 'false', '[]', '{}'])
def test_contact_email_rejects_empty_and_non_string_values(tmp_path, value):
    path = tmp_path / 'config.toml'
    write_config(_existing(tmp_path), path)
    with path.open('a') as handle:
        handle.write('\n[acquisition]\ncontact_email = ' + value + '\n')
    with pytest.raises(ConfigError, match='acquisition.contact_email must be a nonempty string'):
        load_config(path)
