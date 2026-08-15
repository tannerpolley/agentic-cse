from __future__ import annotations

import json

from zotero_companion.better_bibtex import BetterBibTeXClient, configure_export, export_plan


class FakeResponse:
    status = 200

    def __init__(self, result):
        self.result = result

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps({"jsonrpc": "2.0", "id": 1, "result": self.result}).encode()


def test_export_plan_is_dry_run_and_never_changes_consumers(tmp_path):
    destination = tmp_path / "exports" / "references.bib"
    payload = export_plan(destination)
    assert payload["mode"] == "dry-run"
    assert payload["consumers_changed"] is False
    assert not destination.parent.exists()


def test_configure_export_uses_supported_pull_export_and_omits_file_fields(tmp_path):
    calls = []

    def opener(request, timeout):
        payload = json.loads(request.data)
        calls.append((payload, timeout))
        if request.full_url.endswith("/better-bibtex/json-rpc"):
            return FakeResponse({"betterbibtex": "7.0", "zotero": "10.0"})
        assert request.full_url.endswith("/better-bibtex/export/library?/library.bibtex")
        assert payload == {"config": {"preferences": {"skipFields": "file"}}}
        return FakeTextResponse("@article{crank1947,\n  title = {Test}\n}\n")

    destination = tmp_path / "exports" / "references.bib"
    payload = configure_export(destination, BetterBibTeXClient(opener=opener))

    assert payload["mode"] == "apply"
    assert destination.parent.is_dir()
    assert payload["entry_count"] == 1
    assert payload["path_sanitization"]["status"] == "enforced"
    assert destination.read_text() == "@article{crank1947,\n  title = {Test}\n}\n"


class FakeTextResponse(FakeResponse):
    def read(self):
        return self.result.encode()


def test_configure_export_refuses_a_file_field(tmp_path):
    def opener(request, timeout):
        if request.full_url.endswith("/better-bibtex/json-rpc"):
            return FakeResponse({"betterbibtex": "7.0", "zotero": "10.0"})
        return FakeTextResponse("@article{x,\n  file = {/private/paper.pdf}\n}\n")

    from zotero_companion.better_bibtex import BetterBibTeXError
    import pytest

    destination = tmp_path / "references.bib"
    with pytest.raises(BetterBibTeXError, match="local file fields"):
        configure_export(destination, BetterBibTeXClient(opener=opener))
    assert not destination.exists()
