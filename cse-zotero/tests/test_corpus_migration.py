from __future__ import annotations

import pytest

from zotero_companion.config import CompanionConfig
from zotero_companion.corpus_migration import CorpusMigrationError, migrate_corpus


def _config(tmp_path):
    return CompanionConfig(
        corpus_root=tmp_path / "owned-corpus",
        zotero_data_dir=tmp_path / "Zotero",
        bibliography_export=tmp_path / "Zotero" / "exports" / "references.bib",
    )


def _source(tmp_path):
    root = tmp_path / "checkout"
    (root / "wiki" / "claims").mkdir(parents=True)
    (root / "wiki" / "claims" / "claim.md").write_text("source-linked\n", encoding="utf-8")
    (root / "data" / "domains" / "demo").mkdir(parents=True)
    (root / "data" / "domains" / "demo" / "records.csv").write_text("id\n1\n", encoding="utf-8")
    return root


def test_corpus_migration_dry_run_does_not_copy(tmp_path):
    root = _source(tmp_path)
    config = _config(tmp_path)

    result = migrate_corpus(root, config)

    assert result["mode"] == "dry-run"
    assert result["source_files"] == 2
    assert result["pending_files"] == 2
    assert not config.corpus_root.exists()


def test_corpus_migration_copies_and_verifies_without_removing_source(tmp_path):
    root = _source(tmp_path)
    config = _config(tmp_path)

    result = migrate_corpus(root, config, apply=True)

    assert result["copied_files"] == 2
    assert result["verified_files"] == 2
    assert result["source_removed"] is False
    assert (config.wiki_root / "claims" / "claim.md").read_text() == "source-linked\n"
    assert (root / "wiki" / "claims" / "claim.md").is_file()


def test_corpus_migration_refuses_different_destination_file(tmp_path):
    root = _source(tmp_path)
    config = _config(tmp_path)
    destination = config.wiki_root / "claims" / "claim.md"
    destination.parent.mkdir(parents=True)
    destination.write_text("different\n", encoding="utf-8")

    with pytest.raises(CorpusMigrationError, match="destination files differ"):
        migrate_corpus(root, config, apply=True)
