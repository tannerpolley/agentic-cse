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
