from __future__ import annotations

import hashlib
import json
import sys

from zotero_companion.config import CompanionConfig, write_config
from zotero_companion.report import doctor_payload, summarize_items
from zotero_companion.wiki import index_wiki


def item(item_type, filename="", tags=()):
    return {
        "data": {
            "itemType": item_type,
            "filename": filename,
            "tags": [{"tag": tag, "type": tag_type} for tag, tag_type in tags],
        }
    }


def test_summarize_items_separates_markdown_and_tag_types():
    payload = summarize_items(
        [
            item("journalArticle", tags=[("status:to-read", 0)]),
            item("attachment", "paper.mmd", tags=[("publisher-keyword", 1)]),
            item("attachment", "paper.md"),
            item("attachment", "paper.pdf"),
        ]
    )

    assert payload["items"] == 4
    assert payload["attachments"] == 3
    assert payload["markdown_attachments"] == 2
    assert payload["markdown_extensions"] == {".mmd": 1, ".md": 1}
    assert payload["automatic_tag_assignments"] == 1
    assert payload["manual_tag_assignments"] == 1


def _ready_fixture(tmp_path):
    corpus = tmp_path / "corpus"
    config = CompanionConfig(
        corpus_root=corpus,
        zotero_data_dir=tmp_path / "Zotero",
        bibliography_export=tmp_path / "Zotero" / "exports" / "references.bib",
        mathpix_library_consent=False,
    )
    config_path = tmp_path / "config.toml"
    write_config(config, config_path)
    wiki = config.wiki_root
    (wiki / "manifest.json").write_text(
        json.dumps({"schema_version": 1, "item_count": 0, "records": []}),
        encoding="utf-8",
    )
    (wiki / "catalog.json").write_text(json.dumps({"items": []}), encoding="utf-8")
    (wiki / "projects").mkdir()
    evidence = wiki / "evidence" / "ABCD1234"
    evidence.mkdir(parents=True)
    companion = evidence / "notes.md"
    companion.write_text("# Evidence\n\nA retained passage.\n", encoding="utf-8")
    (evidence / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "files": [
                    {
                        "path": companion.name,
                        "format": "markdown",
                        "sha256": hashlib.sha256(companion.read_bytes()).hexdigest(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    index_wiki(wiki, records=[])
    table = config.data_root / "observations.csv"
    table.write_text("value\n1\n", encoding="utf-8")
    (config.data_root / "inventory.json").write_text(
        json.dumps(
            {
                "files": [
                    {
                        "path": table.name,
                        "sha256": hashlib.sha256(table.read_bytes()).hexdigest(),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    config.bibliography_export.parent.mkdir(parents=True)
    config.bibliography_export.write_text("@article{retained, title={Retained}}\n", encoding="utf-8")
    return config, config_path, companion, table


def _doctor(config, config_path, *, zotero_ok=False, better_bibtex_ok=False):
    return doctor_payload(
        config_path,
        config=config,
        zotero={"ok": zotero_ok, "error": "connection refused" if not zotero_ok else ""},
        better_bibtex={
            "ok": better_bibtex_ok,
            "error": "service unavailable" if not better_bibtex_ok else "",
        },
        mathpix={"mpx_on_path": False},
    )


def test_doctor_keeps_offline_readiness_separate_from_live_services(tmp_path):
    config, config_path, _, _ = _ready_fixture(tmp_path)

    absent_library = _doctor(config, config_path, better_bibtex_ok=True)
    absent_better_bibtex = _doctor(config, config_path, zotero_ok=True)

    assert absent_library["ok"] is False
    assert absent_library["readiness"]["zotero_local_api"]["ready"] is False
    assert absent_library["readiness"]["better_bibtex"]["ready"] is True
    assert absent_library["readiness"]["retained_corpus"]["ready"] is True
    assert absent_library["readiness"]["project_views"]["ready"] is True
    assert absent_library["readiness"]["project_views"]["projects"] == []
    assert absent_library["readiness"]["data"]["ready"] is True
    assert absent_library["readiness"]["bibliography_export"]["ready"] is True

    assert absent_better_bibtex["readiness"]["zotero_local_api"]["ready"] is True
    assert absent_better_bibtex["readiness"]["better_bibtex"]["ready"] is False
    assert absent_better_bibtex["readiness"]["retained_corpus"]["ready"] is True


def test_doctor_distinguishes_unconfigured_and_damaged_retained_state(tmp_path):
    config, config_path, companion, table = _ready_fixture(tmp_path)

    companion.write_text("changed evidence\n", encoding="utf-8")
    damaged_evidence = _doctor(config, config_path)
    assert damaged_evidence["readiness"]["retained_corpus"]["ready"] is False
    assert "hash mismatch" in damaged_evidence["readiness"]["retained_corpus"]["reason"]

    companion.write_text("# Evidence\n\nA retained passage.\n", encoding="utf-8")
    table.write_text("value\n2\n", encoding="utf-8")
    damaged_data = _doctor(config, config_path)
    assert damaged_data["readiness"]["retained_corpus"]["ready"] is True
    assert damaged_data["readiness"]["data"]["ready"] is False
    assert "data hash mismatch" in damaged_data["readiness"]["data"]["reason"]


def test_doctor_does_not_verify_supported_but_unconfigured_state(tmp_path):
    config_path = tmp_path / "missing.toml"
    payload = doctor_payload(
        config_path,
        config=None,
        configuration_error="",
        zotero={"ok": False, "error": "unavailable"},
        better_bibtex={"ok": False, "error": "unavailable"},
        mathpix={"mpx_on_path": True},
    )

    assert payload["readiness"]["configuration"]["supported"] is True
    assert payload["readiness"]["configuration"]["ready"] is False
    assert payload["readiness"]["mathpix"]["supported"] is True
    assert payload["readiness"]["mathpix"]["ready"] is False
    assert payload["readiness"]["mathpix"]["consent"]["recorded"] is False


def test_doctor_reports_invalid_configuration_as_json(monkeypatch, capsys, tmp_path):
    from zotero_companion import cli

    class UnavailableZotero:
        def get(self, *_args, **_kwargs):
            raise cli.LocalAPIError("unavailable")

    class UnavailableBetterBibTeX:
        def ready(self):
            raise cli.BetterBibTeXError("unavailable")

    config_path = tmp_path / "invalid.toml"
    config_path.write_text("[paths\n", encoding="utf-8")
    monkeypatch.setattr(cli, "ZoteroLocalAPI", UnavailableZotero)
    monkeypatch.setattr(cli, "BetterBibTeXClient", UnavailableBetterBibTeX)
    monkeypatch.setattr(sys, "argv", ["cse-zotero", "doctor", "--config", str(config_path), "--json"])

    assert cli.main() == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["configuration_valid"] is False
    assert payload["readiness"]["configuration"]["ready"] is False
    assert "Expected ']'" in payload["readiness"]["configuration"]["reason"]
