from __future__ import annotations

import pytest

from zotero_companion.config import CompanionConfig
from zotero_companion.mathpix_ops import MathpixOperationError, mathpix_conversion


class FakeAPI:
    def __init__(self, pdf, *, tags=(), markdown=False):
        self.pdf = pdf
        self.tags = tags
        self.markdown = markdown

    def get(self, path, params=None):
        if path.endswith("/children"):
            children = [
                {
                    "key": "PDF123",
                    "data": {"filename": self.pdf.name, "contentType": "application/pdf"},
                }
            ]
            if self.markdown:
                children.append(
                    {"key": "MD123", "data": {"filename": "paper.mmd", "contentType": "text/markdown"}}
                )
            return children
        return {"key": "PARENT1", "data": {"tags": [{"tag": tag} for tag in self.tags]}}

    def get_text(self, path, params=None):
        return self.pdf.as_uri()

    def collections(self):
        return []


def _config(tmp_path):
    return CompanionConfig(
        corpus_root=tmp_path / "corpus",
        zotero_data_dir=tmp_path / "Zotero",
        bibliography_export=tmp_path / "references.bib",
        mathpix_library_consent=True,
    )


def test_mathpix_is_dry_run_first_then_records_hashes(tmp_path):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-science")
    destination = tmp_path / "corpus/wiki/evidence/PARENT1/paper.mmd"
    api = FakeAPI(pdf)

    plan = mathpix_conversion("PARENT1", "PDF123", _config(tmp_path), destination=destination, api=api)
    assert plan["mode"] == "dry-run"
    assert plan["source_immutable"] is True
    assert not destination.exists()

    applied = mathpix_conversion(
        "PARENT1",
        "PDF123",
        _config(tmp_path),
        destination=destination,
        apply=True,
        api=api,
        converter=lambda _source, output: output.write_text("# extracted\n", encoding="utf-8"),
    )
    import json
    manifest = json.loads((destination.parent / "manifest.json").read_text())
    assert manifest["files"][0]["status"] == "pending_attachment"
    assert manifest["files"][0]["sha256"] == applied["destination_sha256"]
    assert applied["written"] is True
    assert applied["destination_sha256"]
    assert applied["zotero_mutation"] is False


def test_mathpix_respects_existing_companion_and_deny_tags(tmp_path):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-science")
    with pytest.raises(MathpixOperationError, match="Markdown child"):
        mathpix_conversion("PARENT1", "PDF123", _config(tmp_path), api=FakeAPI(pdf, markdown=True))
    with pytest.raises(MathpixOperationError, match="denied by Zotero tag"):
        mathpix_conversion("PARENT1", "PDF123", _config(tmp_path), api=FakeAPI(pdf, tags=("confidential",)))


def test_pending_bundle_repair_and_verification(tmp_path):
    import json
    from zotero_companion.mathpix_ops import repair_mathpix_bundle
    from zotero_companion.report import _offline_corpus
    from zotero_companion.wiki import index_wiki

    config = _config(tmp_path)
    wiki = config.wiki_root
    wiki.mkdir(parents=True)
    (wiki / 'manifest.json').write_text(json.dumps({'schema_version': 1, 'records': [], 'item_count': 0}))
    (wiki / 'catalog.json').write_text(json.dumps({'items': []}))
    index_wiki(wiki, records=[])
    pdf = tmp_path / 'paper.pdf'
    pdf.write_bytes(b'%PDF-science')
    bundle = wiki / 'evidence/PARENT1'
    bundle.mkdir(parents=True)
    transcription = bundle / 'paper.mmd'
    transcription.write_text('# retained transcription\n')
    api = FakeAPI(pdf)
    assert _offline_corpus(config)['ready'] is False
    plan = repair_mathpix_bundle('PARENT1', config, api=api)
    assert plan['mode'] == 'dry-run' and not (bundle / 'manifest.json').exists()
    with pytest.raises(MathpixOperationError, match='already exists'):
        repair_mathpix_bundle('PARENT1', config, api=FakeAPI(pdf, markdown=True))
    repair_mathpix_bundle('PARENT1', config, api=api, apply=True)
    status = _offline_corpus(config)
    assert status['ready'] is True
    assert status['pending_attachments'] == [{'zotero_key': 'PARENT1', 'path': 'wiki/evidence/PARENT1/paper.mmd', 'status': 'pending_attachment'}]
    transcription.write_text('corrupted')
    assert _offline_corpus(config)['ready'] is False
    transcription.unlink()
    assert _offline_corpus(config)['ready'] is False
    import hashlib
    transcription.write_text('# attached transcription')
    (bundle / 'manifest.json').write_text(json.dumps({'files': [{
        'path': transcription.name, 'zotero_attachment_key': 'MD123',
        'sha256': hashlib.sha256(transcription.read_bytes()).hexdigest(),
    }]}))
    assert _offline_corpus(config)['ready'] is True
    assert _offline_corpus(config)['pending_attachments'] == []
    (bundle / 'manifest.json').unlink()
    assert _offline_corpus(config)['ready'] is False
